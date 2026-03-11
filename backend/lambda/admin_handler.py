"""Admin Lambda handler for user management via Cognito."""
import json
import os
import boto3
from botocore.exceptions import ClientError

cognito = boto3.client("cognito-idp")
USER_POOL_ID = os.environ["USER_POOL_ID"]


def lambda_handler(event: dict, context) -> dict:
    """Route admin requests to the appropriate handler."""
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
    groups = claims.get("cognito:groups", "")

    # SEC: Only admin group members can access this endpoint
    if "admin" not in groups:
        return _resp(403, {"error": "Forbidden — admin access required."})

    method = event.get("httpMethod", "")
    path = event.get("path", "")

    if path.endswith("/admin/users") and method == "GET":
        return _list_users()
    elif path.endswith("/admin/users") and method == "POST":
        return _create_user(event)
    elif path.endswith("/admin/users") and method == "DELETE":
        return _delete_user(event)
    elif path.endswith("/admin/users/role") and method == "POST":
        return _set_role(event)

    return _resp(404, {"error": "Not found"})


def _list_users() -> dict:
    """List all users in the Cognito User Pool with their group memberships."""
    try:
        users = []
        params: dict = {"UserPoolId": USER_POOL_ID, "Limit": 60}
        while True:
            resp = cognito.list_users(**params)
            for u in resp.get("Users", []):
                attrs = {a["Name"]: a["Value"] for a in u.get("Attributes", [])}
                # Get groups for this user
                grp_resp = cognito.admin_list_groups_for_user(
                    UserPoolId=USER_POOL_ID, Username=u["Username"],
                )
                group_names = [g["GroupName"] for g in grp_resp.get("Groups", [])]
                users.append({
                    "username": u["Username"],
                    "email": attrs.get("email", ""),
                    "status": u["UserStatus"],
                    "enabled": u["Enabled"],
                    "created": u["UserCreateDate"].isoformat(),
                    "groups": group_names,
                    "role": "admin" if "admin" in group_names else "user",
                })
            token = resp.get("PaginationToken")
            if not token:
                break
            params["PaginationToken"] = token

        return _resp(200, {"users": users})
    except ClientError as e:
        return _resp(500, {"error": str(e)})


def _create_user(event: dict) -> dict:
    """Create a new Cognito user and assign them to a group."""
    body = json.loads(event.get("body", "{}"))
    email = body.get("email", "").strip()
    role = body.get("role", "user")
    temp_password = body.get("temp_password", "Welcome@123")

    if not email:
        return _resp(400, {"error": "email is required."})
    if role not in ("admin", "user"):
        return _resp(400, {"error": "role must be 'admin' or 'user'."})

    try:
        cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            TemporaryPassword=temp_password,
            DesiredDeliveryMediums=["EMAIL"],
        )
        cognito.admin_add_user_to_group(
            UserPoolId=USER_POOL_ID, Username=email, GroupName=role,
        )
        return _resp(201, {"message": f"User {email} created with role '{role}'."})
    except cognito.exceptions.UsernameExistsException:
        return _resp(409, {"error": f"User {email} already exists."})
    except ClientError as e:
        return _resp(500, {"error": str(e)})


def _delete_user(event: dict) -> dict:
    """Delete a Cognito user."""
    body = json.loads(event.get("body", "{}"))
    username = body.get("username", "").strip()

    if not username:
        return _resp(400, {"error": "username is required."})

    try:
        cognito.admin_delete_user(
            UserPoolId=USER_POOL_ID, Username=username,
        )
        return _resp(200, {"message": f"User {username} deleted."})
    except cognito.exceptions.UserNotFoundException:
        return _resp(404, {"error": f"User {username} not found."})
    except ClientError as e:
        return _resp(500, {"error": str(e)})


def _set_role(event: dict) -> dict:
    """Change a user's role by updating their group membership."""
    body = json.loads(event.get("body", "{}"))
    username = body.get("username", "").strip()
    new_role = body.get("role", "").strip()

    if not username or new_role not in ("admin", "user"):
        return _resp(400, {"error": "username and role ('admin'/'user') required."})

    old_role = "user" if new_role == "admin" else "admin"

    try:
        # Remove from old group (ignore if not a member)
        try:
            cognito.admin_remove_user_from_group(
                UserPoolId=USER_POOL_ID, Username=username, GroupName=old_role,
            )
        except ClientError:
            pass

        cognito.admin_add_user_to_group(
            UserPoolId=USER_POOL_ID, Username=username, GroupName=new_role,
        )
        return _resp(200, {"message": f"{username} role set to '{new_role}'."})
    except ClientError as e:
        return _resp(500, {"error": str(e)})


def _resp(code: int, body: dict) -> dict:
    """Build an API Gateway proxy response."""
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
        },
        "body": json.dumps(body),
    }
