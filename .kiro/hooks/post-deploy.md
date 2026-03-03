# Hook: post-deploy

**Trigger:** After every successful `cdk deploy` or Amplify deployment
**Type:** Non-blocking (runs asynchronously; failures generate a warning, not a rollback)

## Purpose

This hook validates that the deployed system is healthy and all integrations are functioning correctly. It runs a lightweight smoke test against the live API endpoints and verifies that all AWS service dependencies are reachable.

## Steps

### Step 1 — CDK Output Capture

After `cdk deploy` completes, capture and store the stack outputs in a local `.deploy-outputs.json` file for use by subsequent steps.

```bash
aws cloudformation describe-stacks \
  --stack-name EmailAnnotatorStack \
  --query "Stacks[0].Outputs" \
  --output json > .deploy-outputs.json
```

### Step 2 — API Gateway Health Check

Send an unauthenticated `OPTIONS` request to the API endpoint to verify CORS preflight is responding correctly.

```bash
API_ENDPOINT=$(cat .deploy-outputs.json | jq -r '.[] | select(.OutputKey=="ApiEndpoint") | .OutputValue')
curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$API_ENDPOINT/process" \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: POST"
# Expected: 200
```

**On failure:** Log a warning: "API Gateway CORS preflight failed. Check API Gateway CORS configuration."

### Step 3 — Cognito User Pool Verification

Verify that the Cognito User Pool exists and self-registration is disabled.

```bash
USER_POOL_ID=$(cat .deploy-outputs.json | jq -r '.[] | select(.OutputKey=="UserPoolId") | .OutputValue')
aws cognito-idp describe-user-pool \
  --user-pool-id "$USER_POOL_ID" \
  --query "UserPool.AdminCreateUserConfig.AllowAdminCreateUserOnly"
# Expected: true
```

**On failure:** Log a critical warning: "Cognito self-registration may be enabled. Verify AdminCreateUserConfig immediately."

### Step 4 — S3 Bucket Access Verification

Verify that the S3 bucket exists, has public access blocked, and versioning is enabled.

```bash
BUCKET=$(cat .deploy-outputs.json | jq -r '.[] | select(.OutputKey=="BucketName") | .OutputValue')
aws s3api get-public-access-block --bucket "$BUCKET"
aws s3api get-bucket-versioning --bucket "$BUCKET"
```

**On failure:** Log a warning with the specific misconfiguration.

### Step 5 — Bedrock Model Availability Check

Verify that both required Bedrock models are accessible in the deployed region.

```bash
aws bedrock get-foundation-model \
  --model-identifier anthropic.claude-3-haiku-20240307-v1:0 \
  --query "modelDetails.modelLifecycle.status"
# Expected: "ACTIVE"

aws bedrock get-foundation-model \
  --model-identifier anthropic.claude-3-sonnet-20240229-v1:0 \
  --query "modelDetails.modelLifecycle.status"
# Expected: "ACTIVE"
```

**On failure:** Log a critical warning: "Bedrock model not available. Enable model access in the Bedrock console."

### Step 6 — SES Sender Verification Check

Verify that the configured SES sender email address is verified and not in sandbox mode.

```bash
SES_FROM=$(aws lambda get-function-configuration \
  --function-name EmailAnnotatorStack-ProcessorFn \
  --query "Environment.Variables.SES_FROM_EMAIL" --output text)
aws ses get-identity-verification-attributes \
  --identities "$SES_FROM" \
  --query "VerificationAttributes.*.VerificationStatus"
# Expected: "Success"
```

**On failure:** Log a warning: "SES sender address not verified. Emails will not be delivered."

### Step 7 — Update aws-config.js Reminder

After a successful deployment, display a reminder to update the frontend configuration if the CDK outputs have changed.

```
⚠️  REMINDER: If UserPoolId, UserPoolClientId, or ApiEndpoint changed,
    update frontend/src/utils/aws-config.js and redeploy the Amplify app.
```

## Agent Instructions

After any infrastructure change, run through these validation steps in order. If Step 3 (Cognito self-registration) or Step 5 (Bedrock availability) fails, treat it as a blocking issue and do not proceed until resolved. For all other failures, log the warning and continue.
