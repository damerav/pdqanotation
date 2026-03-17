# Email Campaign Annotator — Context State

**Last updated:** March 16, 2026  
**Last commit:** `296e3ec` on `main`

---

## AWS Resources

| Resource | Identifier |
|---|---|
| Amplify App | `d2ie3k1k9zhei3` — https://main.d2ie3k1k9zhei3.amplifyapp.com |
| API Gateway | https://1nhy7n8lld.execute-api.us-east-1.amazonaws.com/prod |
| Cognito User Pool | `us-east-1_suz5riOk5` |
| Cognito Client ID | `6a8c3m92724vrj80kbgpe47gjd` |
| S3 Bucket | `emailannotatorstack-annotatorbucket45bbae1a-ihmajdqplmoc` |
| Processor Lambda | `EmailAnnotatorStack-ProcessorFn54060268-T8kwYhwyuAo2` |
| Jobs Lambda | `EmailAnnotatorStack-JobsFnB0FBB63A-0ma7SMKuTg3J` |
| Admin Lambda | `EmailAnnotatorStack-AdminFn81E922BC-rtrSzs0S5FnT` |
| EC2 Screenshot Service | `http://54.81.69.58:5000` (instance `i-09dcba1dd8a68b267`) |
| SES Status | Sandbox mode — only verified emails can receive |

## Cognito Users & Groups

| Username | Email | Groups | Status |
|---|---|---|---|
| testuser | damerav@gmail.com | admin | CONFIRMED |

Groups created: `admin`, `user`

## Deployment Notes

- Amplify is NOT connected to GitHub (manual zip deploys required)
- To deploy frontend: `npm run build` in `frontend/`, zip `dist/`, upload via `aws amplify create-deployment` + `start-deployment`
- CDK deploys from `infrastructure/` dir: `cdk deploy --require-approval never -c sesFromEmail=damerav@gmail.com`
- SES is in sandbox — new recipient emails must be verified via `aws ses verify-email-identity`
- EC2 access via EC2 Instance Connect: generate temp key, push with `aws ec2-instance-connect send-ssh-public-key`, SSH within 60 seconds

## What's Working

- Full annotation pipeline: upload HTML → parse → classify (Bedrock) → review (Bedrock) → screenshot (EC2) → annotate → PDF → S3 → SES email
- Auth: Cognito login with username/email
- Admin panel: user management (create, delete, toggle role)
- History: role-based (admins see all jobs, users see only their own)
- Nav shows "Admin" tab + "Admin Role" badge for admin users
- CORS restricted to Amplify domain (API Gateway + S3 + Lambda response headers)
- EC2 screenshot service updated with `right_x` bounding box data

## Resolved Issues (this session)

- CORS locked down from `*` to `https://main.d2ie3k1k9zhei3.amplifyapp.com` (SEC-18)
- EC2 screenshot service updated with `right_x` field via EC2 Instance Connect
- CDK stack redeployed with all CORS + Lambda code changes

## Remaining TODO

- **SES production access** — Must be requested via AWS Console (SES → Account dashboard → Request production access). Use case: "Transactional email for internal pharma marketing team, ~100 emails/month."
- **Amplify GitHub connection** — Recreate app via AWS Console with GitHub OAuth to enable auto-deploy on push.
