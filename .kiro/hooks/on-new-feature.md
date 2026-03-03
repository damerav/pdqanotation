# Hook: on-new-feature

**Trigger:** When a new feature branch is created or a new capability is requested
**Type:** Advisory (checklist surfaced to the developer/agent before implementation begins)

## Purpose

This hook ensures that every new feature is properly scoped, designed, and implemented consistently with the existing architecture before any code is written.

## Pre-Implementation Checklist

### 1. Requirements Alignment

Before writing any code, verify the new feature against `.kiro/specs/requirements.md`:

- Does this feature satisfy an existing requirement, or does it add a new one?
- If it adds a new requirement, append it to `requirements.md` with a new `REQ-*` identifier before proceeding.
- Does the feature conflict with any existing requirement? If so, flag the conflict and resolve it before proceeding.

### 2. Design Impact Assessment

Review `.kiro/specs/design.md` and answer the following:

- Which existing components are affected? (List specific files)
- Does this feature require a new Lambda function, or can it be added to an existing one?
- Does this feature require a new S3 prefix or data model?
- Does this feature require new IAM permissions? If so, add them to `annotator_stack.py` following the least-privilege pattern.
- Does this feature require a new API Gateway route? If so, add it to the API Gateway section of `design.md`.

### 3. MCP Integration Check

Review `.kiro/skills/mcp-integration.md` and check whether any of the 8 planned MCP servers would be a better implementation approach than custom code. Specifically:

- **Link validation** → Use Linkinator MCP instead of custom HTTP checking code
- **Browser automation** → Use Playwright MCP instead of extending `screenshot_generator.py`
- **Brand/compliance review** → Use Bedrock Knowledge Bases MCP instead of hardcoding rules in the system prompt
- **Metrics and alerting** → Use CloudWatch MCP instead of custom logging

### 4. Bedrock Prompt Design (if applicable)

If the feature involves a new Bedrock call:

- Specify the model: Haiku for fast/cheap classification tasks, Sonnet for deep analysis tasks.
- Define the expected JSON output schema before writing the prompt.
- Add a `_validate_response()` function to handle malformed JSON.
- Add a fallback that returns a safe default if the Bedrock call fails.
- Estimate the token cost: Haiku ~$0.00025/1K input tokens; Sonnet ~$0.003/1K input tokens.

### 5. Test Plan

Before writing implementation code, write the test cases first (TDD approach):

- Unit test for the new module in `backend/tests/`
- Integration test that mocks the Bedrock/S3/SES calls
- Edge cases: empty input, malformed HTML, Bedrock timeout, S3 permission error

### 6. Documentation Update

After implementation, update the following:

- `README.md` — Add the new feature to the feature list
- `.kiro/specs/requirements.md` — Mark the requirement as implemented
- `.kiro/specs/design.md` — Add the new component to the architecture section
- `CHANGELOG.md` — Add an entry under the current version

## Agent Instructions

When a user requests a new feature, run through this checklist before writing any code. Present the impact assessment to the user and confirm the approach before proceeding. If the feature is better served by an MCP integration from the roadmap, recommend that path first.
