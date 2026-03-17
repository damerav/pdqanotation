# Email Campaign Annotator — Context State

**Last updated:** March 16, 2026  
**Last commit:** `ec676af` on `main`

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
| testuser | damerav@gmail.com | admin, user | CONFIRMED |
| ksimas | ksimas@pdqcommunications.com | admin | FORCE_CHANGE_PASSWORD |
| tgarvey | tgarvey@pdqcommunications.com | admin | FORCE_CHANGE_PASSWORD |

Groups created: `admin`, `user`

## Deployment Notes

- Amplify is NOT connected to GitHub (manual zip deploys required)
- To deploy frontend: `npm run build` in `frontend/`, zip `dist/`, upload via `aws amplify create-deployment` + `start-deployment`
- CDK deploys from `infrastructure/` dir: `cdk deploy --require-approval never -c sesFromEmail=damerav@gmail.com`
- SES is in sandbox — new recipient emails must be verified via `aws ses verify-email-identity`
- EC2 access via EC2 Instance Connect: generate temp key (no passphrase), push with `aws ec2-instance-connect send-ssh-public-key`, SSH within 60 seconds. One command per SSH session.

## What's Working

- Full annotation pipeline: upload HTML → parse → classify (Bedrock) → review (Bedrock) → screenshot (EC2) → annotate → PDF → S3 → SES email
- Auth: Cognito login with username/email
- Admin panel: user management (create with username/first name/last name/email, delete, toggle role)
- Admin table: proper layout with inline actions, PENDING status badge, name column
- History: role-based (admins see all jobs, users see only their own)
- Nav shows "Admin" tab + "Admin Role" badge for admin users
- CORS restricted to Amplify domain (API Gateway + S3 + Lambda response headers)
- EC2 screenshot service updated with `right_x` bounding box data

## Resolved Issues (this session)

- Redeployed frontend to Amplify (admin panel was missing from live site)
- Fixed `testuser` admin group membership (was removed during CDK redeploy)
- Fixed Cognito "Username cannot be email format" error — admin create user now uses separate username field
- Added Username, First Name, Last Name fields to admin create user form
- Added Username and Name columns to admin user table
- Backend `_list_users` now returns `first_name`/`last_name` from Cognito `given_name`/`family_name` attributes
- Fixed admin table layout: proper spacing, inline action buttons, horizontal scroll, PENDING status badge

## Remaining TODO

- **SES production access** — Must be requested via AWS Console (SES → Account dashboard → Request production access). Use case: "Transactional email for internal pharma marketing team, ~100 emails/month."
- **Amplify GitHub connection** — Recreate app via AWS Console with GitHub OAuth to enable auto-deploy on push.
- **New users (ksimas, tgarvey)** — Still in FORCE_CHANGE_PASSWORD status. They need to log in and set a new password. Their emails also need to be verified in SES (sandbox mode) before they can receive PDFs.
