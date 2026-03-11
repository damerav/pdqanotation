import json
import os
import boto3

s3 = boto3.client("s3")
BUCKET = os.environ["S3_BUCKET"]


def lambda_handler(event, context):
    # Extract the caller's email from the Cognito JWT claims
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
    user_email = claims.get("email", "")
    groups = claims.get("cognito:groups", "")

    if not user_email:
        return _resp(401, {"error": "Unauthorized"})

    is_admin = "admin" in groups

    try:
        jobs = []
        if is_admin:
            # Admin sees all jobs across all users
            prefix = "history/"
        else:
            # Regular user sees only their own jobs
            prefix = f"history/{user_email}/"

        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                body = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read()
                jobs.append(json.loads(body))

        # Sort newest first
        jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
        return _resp(200, {"jobs": jobs})

    except Exception as e:
        return _resp(500, {"error": str(e)})


def _resp(code, body):
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
        },
        "body": json.dumps(body),
    }
