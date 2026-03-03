# Skill: AWS CDK Infrastructure Management

**Skill ID:** aws-cdk-infrastructure
**Applies to:** `infrastructure/annotator_stack.py`, `infrastructure/app.py`
**Last updated:** March 03, 2026

---

## Overview

This skill defines the patterns and standards for managing the AWS CDK infrastructure stack. All AWS resources for the Email Campaign Annotator are defined in a single CDK stack (`EmailAnnotatorStack`). This skill is the authoritative reference for adding, modifying, or removing AWS resources.

---

## Skill 1: Adding a New Lambda Function

When a new Lambda function is needed (e.g., for the Sprint 2 SQS consumer), follow this pattern in `annotator_stack.py`:

```python
# Pattern for a new ZIP-deployed Lambda (lightweight, < 50 MB)
new_fn = lambda_.Function(
    self, "NewFunctionLogicalId",          # Logical ID: PascalCase, unique in stack
    function_name="email-annotator-new-fn", # Physical name: kebab-case
    runtime=lambda_.Runtime.PYTHON_3_12,
    handler="new_handler.lambda_handler",
    code=lambda_.Code.from_asset("../backend/lambda"),
    memory_size=128,
    timeout=Duration.seconds(30),
    environment={
        "S3_BUCKET": bucket.bucket_name,
        # Add only the env vars this function actually needs
    },
)

# Pattern for a new Docker-deployed Lambda (heavy dependencies)
new_docker_fn = lambda_.DockerImageFunction(
    self, "NewDockerFunctionLogicalId",
    function_name="email-annotator-new-docker-fn",
    code=lambda_.DockerImageCode.from_image_asset("../backend/new-docker/"),
    memory_size=1024,
    timeout=Duration.minutes(3),
    environment={
        "S3_BUCKET": bucket.bucket_name,
    },
)
```

After adding a new function, always:
1. Grant the minimum required S3 permissions (`grant_read`, `grant_read_write`, or `grant_put`)
2. Add specific IAM policy statements for Bedrock, SES, or other services
3. Add the function as an API Gateway integration if it needs an HTTP endpoint
4. Add the function's logical ID to the CDK outputs if its ARN is needed externally

---

## Skill 2: Adding a New API Gateway Route

```python
# Pattern for a new authenticated API route
new_resource = api.root.add_resource("new-endpoint")
new_resource.add_method(
    "POST",                                    # HTTP method
    apigw.LambdaIntegration(new_fn),          # Lambda integration
    **auth_opts                                # Always include auth_opts for protected routes
)

# Pattern for a public route (no auth — use sparingly)
public_resource = api.root.add_resource("health")
public_resource.add_method(
    "GET",
    apigw.LambdaIntegration(health_fn),
    # No auth_opts — this route is intentionally public
)
```

**Important:** CORS preflight (`OPTIONS`) is handled automatically by the `default_cors_preflight_options` on the `RestApi` construct. Do not add `OPTIONS` methods manually.

---

## Skill 3: Adding a New S3 Prefix

The S3 bucket uses a single bucket with logical prefixes. When adding a new data type, define the prefix as a constant in `handler.py` and document it in `design.md`.

```python
# In handler.py — define prefix constants at module level
UPLOADS_PREFIX = "uploads"
PDFS_PREFIX = "pdfs"
HISTORY_PREFIX = "history"
NEW_DATA_PREFIX = "new-data"  # Add new prefixes here
```

If the new prefix requires a lifecycle policy (e.g., auto-delete after N days), add it to the bucket definition in `annotator_stack.py`:

```python
bucket = s3.Bucket(
    self, "EmailAnnotatorBucket",
    lifecycle_rules=[
        s3.LifecycleRule(
            prefix="pdfs/",
            expiration=Duration.days(7),
        ),
        s3.LifecycleRule(
            prefix="new-data/",
            expiration=Duration.days(30),  # Add new lifecycle rules here
        ),
    ],
)
```

---

## Skill 4: Adding Bedrock Permissions for a New Model

When a new Bedrock model is needed (e.g., Claude 3 Opus for a high-stakes review), update the IAM policy in `annotator_stack.py`:

```python
processor_fn.add_to_role_policy(iam.PolicyStatement(
    sid="BedrockInvokeModels",
    actions=["bedrock:InvokeModel"],
    resources=[
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-opus-20240229-v1:0",  # new
    ],
))
```

Also update the cost estimate in `README.md` and the model selection table in `.kiro/steering/bedrock-rules.md`.

---

## Skill 5: CDK Stack Outputs

All values needed to configure the frontend (`aws-config.js`) or external systems must be exported as CDK stack outputs. The current outputs are:

| Output Key | Value | Used By |
|---|---|---|
| `UserPoolId` | Cognito User Pool ID | `aws-config.js` |
| `UserPoolClientId` | Cognito App Client ID | `aws-config.js` |
| `ApiEndpoint` | API Gateway base URL | `aws-config.js` |
| `BucketName` | S3 bucket name | `post-deploy` hook |

When adding a new output, use PascalCase for the key and provide a description:

```python
CfnOutput(self, "NewOutputKey",
    value=new_resource.some_attribute,
    description="Human-readable description of what this value is used for",
)
```

---

## Skill 6: Deployment Commands Reference

```bash
# First-time setup
cd infrastructure
pip install -r requirements.txt
cdk bootstrap aws://ACCOUNT_ID/REGION

# Deploy (creates or updates all resources)
cdk deploy --parameters SesFromEmail=noreply@yourdomain.com

# Preview changes without deploying
cdk diff

# View the generated CloudFormation template
cdk synth

# Destroy all resources (CAUTION: deletes all data)
cdk destroy

# Add a new user after deployment
aws cognito-idp admin-create-user \
  --user-pool-id POOL_ID \
  --username user@example.com \
  --user-attributes Name=email,Value=user@example.com \
  --temporary-password TempPass123!

# Force a user's password (skip temporary password flow)
aws cognito-idp admin-set-user-password \
  --user-pool-id POOL_ID \
  --username user@example.com \
  --password PermanentPass123! \
  --permanent
```
