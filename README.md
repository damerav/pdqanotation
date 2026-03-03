# Email Annotator — AWS Amplify + Bedrock

Automated email campaign annotated PDF generator.
Upload an HTML email → get a fully annotated PDF in your inbox within ~60 seconds.

## Stack

| Layer | Service |
|---|---|
| Hosting + CI/CD | AWS Amplify |
| Auth | Amazon Cognito (via Amplify Auth) |
| API | Amazon API Gateway (via Amplify API) |
| Processing | AWS Lambda (container image, 3 GB RAM, 5 min) |
| AI Classification | AWS Bedrock — Claude 3 Haiku |
| Storage | Amazon S3 (via Amplify Storage) |
| Email Delivery | Amazon SES |

## Project Structure

```
email-annotator/
├── amplify.yml              # Amplify build spec
├── frontend/                # React + Vite web app
│   └── src/
│       ├── App.jsx          # Shell + Authenticator
│       ├── pages/
│       │   ├── UploadPage.jsx
│       │   └── HistoryPage.jsx
│       └── utils/
│           └── aws-config.js
├── backend/
│   ├── docker/              # Lambda container image
│   │   ├── Dockerfile
│   │   ├── handler.py       # Main processor
│   │   ├── html_parser.py
│   │   ├── bedrock_classifier.py
│   │   ├── screenshot_generator.py
│   │   ├── image_annotator.py
│   │   └── pdf_builder.py
│   └── lambda/
│       └── jobs_handler.py  # GET /jobs history
└── infrastructure/          # AWS CDK (Python)
    ├── app.py
    ├── annotator_stack.py
    └── requirements.txt
```

## Quick Start

See the full Solution Document for step-by-step deployment instructions.
