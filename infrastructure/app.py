import aws_cdk as cdk
from annotator_stack import EmailAnnotatorStack

app = cdk.App()

EmailAnnotatorStack(
    app, "EmailAnnotatorStack",
    ses_from_email=app.node.try_get_context("sesFromEmail") or "noreply@yourdomain.com",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)

app.synth()
