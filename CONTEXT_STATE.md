# Email Campaign Annotator — Context State

**Last updated:** March 11, 2026  
**Last commit:** `f09fb6d` on `main`

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
| EC2 Screenshot Service | `http://54.81.69.58:5000` |
| SES Status | Sandbox mode — only verified emails can receive |

## Cognito Users & Groups

| Username | Email | Groups | Status |
|---|---|---|---|
| testuser | damerav@gmail.com | admin | CONFIRMED |

Groups created: `admin`, `user`

## Deployment Notes

- Amplify is NOT connected to GitHub (manual zip deploys required)
- To deploy frontend: `npm run build` in `frontend/`, zip `dist/`, upload via `aws amplify create-deployment` + `start-deployment`
- CDK deploys from `infrastructure/` dir: `cdk deploy --parameters sesFromEmail=damerav@gmail.com`
- SES is in sandbox — new recipient emails must be verified via `aws ses verify-email-identity`

## What's Working

- Full annotation pipeline: upload HTML → parse → classify (Bedrock) → review (Bedrock) → screenshot (EC2) → annotate → PDF → S3 → SES email
- Auth: Cognito login with username/email
- Admin panel: user management (create, delete, toggle role)
- History: role-based (admins see all jobs, users see only their own)
- Nav shows "Admin" tab + "Admin Role" badge for admin users

## Known Issues / TODO

- **Amplify not connected to GitHub** — auto-deploy on push doesn't work. Need to recreate app via AWS Console with GitHub OAuth to enable this.
- **EC2 screenshot service** — `screenshot_service.py` and `userdata.sh` have updated code for `right_x` bounding box data, but EC2 instance hasn't been updated (no SSM agent, no SSH key). Lambda annotator falls back to estimated position when `right_x` is missing.
- **Badge positioning** — annotation badges use estimated content width `(width + 600) / 2 + gap` when EC2 doesn't provide `right_x`. Once EC2 is updated, badges will use actual content edge.
- **SES sandbox** — production access not enabled. Each new recipient email needs manual verification.
- **CORS** — currently allows all origins (`*`). Before production, restrict to Amplify domain (SEC-18).
