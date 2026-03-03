from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_ecr_assets as ecr_assets,
)
from constructs import Construct


class EmailAnnotatorStack(Stack):
    def __init__(self, scope: Construct, construct_id: str,
                 ses_from_email: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── 1. S3 bucket ────────────────────────────────────────────────────
        bucket = s3.Bucket(
            self, "AnnotatorBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.PUT],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3600,
                ),
            ],
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="expire-pdfs-7-days",
                    prefix="pdfs/",
                    expiration=Duration.days(7),
                ),
                s3.LifecycleRule(
                    id="expire-uploads-1-day",
                    prefix="uploads/",
                    expiration=Duration.days(1),
                ),
            ],
        )

        # ── 2. Cognito User Pool ─────────────────────────────────────────────
        user_pool = cognito.UserPool(
            self, "UserPoolV2",
            self_sign_up_enabled=False,   # admin-only invites for 5–10 users
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )

        user_pool_client = user_pool.add_client(
            "WebClient",
            auth_flows=cognito.AuthFlow(user_srp=True),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(implicit_code_grant=True),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE,
                ],
            ),
        )

        # ── 3. Lambda — Processor (container image) ──────────────────────────
        docker_image = ecr_assets.DockerImageAsset(
            self, "ProcessorImage",
            directory="../backend/docker",
        )

        processor_fn = lambda_.DockerImageFunction(
            self, "ProcessorFn",
            code=lambda_.DockerImageCode.from_ecr(
                docker_image.repository,
                tag_or_digest=docker_image.image_tag,
            ),
            memory_size=3008,
            timeout=Duration.minutes(5),
            environment={
                "S3_BUCKET": bucket.bucket_name,
                "SES_FROM_EMAIL": ses_from_email,
                "PLAYWRIGHT_BROWSERS_PATH": "/opt/pw-browsers",
            },
        )

        bucket.grant_read_write(processor_fn)

        # Bedrock permissions — both models used in the pipeline:
        #   Claude 3 Haiku  → fast link classification (bedrock_classifier.py)
        #   Claude 3 Sonnet → comprehensive email quality review (bedrock_reviewer.py)
        processor_fn.add_to_role_policy(iam.PolicyStatement(
            sid="BedrockInvokeModels",
            actions=["bedrock:InvokeModel"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0",
                f"arn:aws:bedrock:us-east-1:{self.account}:inference-profile/us.anthropic.*",
            ],
        ))

        processor_fn.add_to_role_policy(iam.PolicyStatement(
            sid="SESsendEmail",
            actions=["ses:SendEmail", "ses:SendRawEmail"],
            resources=["*"],
        ))

        # ── 4. Lambda — Jobs history (lightweight zip deployment) ────────────
        jobs_fn = lambda_.Function(
            self, "JobsFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="jobs_handler.lambda_handler",
            code=lambda_.Code.from_asset("../backend/lambda"),
            environment={"S3_BUCKET": bucket.bucket_name},
            timeout=Duration.seconds(15),
        )
        bucket.grant_read(jobs_fn)

        # ── 5. API Gateway with Cognito authorizer ───────────────────────────
        api = apigw.RestApi(
            self, "AnnotatorApi",
            rest_api_name="EmailAnnotatorAPI",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Authorization", "Content-Type"],
            ),
        )

        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "CognitoAuth",
            cognito_user_pools=[user_pool],
        )
        auth_opts = dict(
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # POST /process — triggers full pipeline (parse → classify → review → screenshot → PDF → SES)
        process_res = api.root.add_resource("process")
        process_res.add_method("POST", apigw.LambdaIntegration(processor_fn), **auth_opts)

        # POST /upload-url — generates pre-signed S3 URL for images ZIP upload
        upload_url_res = api.root.add_resource("upload-url")
        upload_url_res.add_method(
            "POST", apigw.LambdaIntegration(processor_fn), **auth_opts,
        )

        # GET /jobs — returns job history for the authenticated user
        jobs_res = api.root.add_resource("jobs")
        jobs_res.add_method("GET", apigw.LambdaIntegration(jobs_fn), **auth_opts)

        # ── 6. Outputs ────────────────────────────────────────────────────────
        CfnOutput(self, "UserPoolId",       value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "ApiEndpoint",      value=api.url)
        CfnOutput(self, "BucketName",       value=bucket.bucket_name)
