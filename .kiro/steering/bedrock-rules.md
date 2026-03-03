# Agent Steering: AWS Bedrock Usage Rules

**Project:** Email Campaign Annotator
**Applies to:** All files in `backend/docker/` that invoke AWS Bedrock

---

## Overview

This project uses AWS Bedrock as the AI backbone for two distinct pipeline stages. These rules govern how the agent should write, review, and modify any code that calls Bedrock. Strict adherence to these rules ensures cost predictability, output reliability, and graceful failure handling.

---

## Model Selection Policy

The project uses exactly two Bedrock models. No other models may be introduced without updating the CDK IAM policy and the cost estimate in `README.md`.

| Model | Constant | Use Case | Rationale |
|---|---|---|---|
| `anthropic.claude-3-haiku-20240307-v1:0` | `MODEL_ID` in `bedrock_classifier.py` | Link classification | Fast (< 2 s), cheap ($0.00025/1K input tokens), sufficient for structured JSON output from a short prompt |
| `anthropic.claude-3-sonnet-20240229-v1:0` | `REVIEW_MODEL` in `bedrock_reviewer.py` | Email quality review | More capable reasoning required for nuanced quality assessment across 6 categories |

**Rule:** Never use Claude 3 Opus or any other model in this pipeline. The cost difference is not justified for this use case. If a more capable model is genuinely required, document the justification in `design.md` and update the CDK IAM policy.

---

## Prompt Engineering Standards

### System Prompt Requirements

Every Bedrock call must include a `system` prompt that:

1. Defines the model's role precisely (e.g., "You are an email marketing analyst.")
2. Specifies the exact JSON output schema with field names, types, and valid values
3. Instructs the model to return JSON only — no preamble, no explanation, no markdown fences
4. Includes at least one example of a valid output for the most complex case

```python
# Correct system prompt pattern
SYSTEM = """You are an email marketing analyst. Classify each hyperlink from an HTML email campaign.
For every link return:
- label: short human-readable label (e.g. "Header Logo", "Primary CTA", "Unsubscribe")
- include: true for user-facing content links; false for font stylesheets, tracking pixels, or duplicates
Return ONLY a JSON object: {"links": [{"label": "...", "include": true/false}, ...]}
One entry per input link, same order."""
```

### Temperature Settings

The classifier (`bedrock_classifier.py`) uses the default temperature (0.7) because some creative label generation is acceptable. The reviewer (`bedrock_reviewer.py`) must use `"temperature": 0.1` to produce consistent, deterministic structured output. Never set temperature above 0.3 for any call that returns structured JSON.

### Token Limits

The classifier is limited to `max_tokens: 1024` because the output is a compact JSON array. The reviewer is limited to `max_tokens: 4096` to allow for detailed issue descriptions. Do not increase these limits without verifying the Lambda timeout is still sufficient.

### Input Truncation

The reviewer truncates the HTML input to 8,000 characters (`html_content[:8000]`). This limit balances context quality against token cost and latency. Do not remove this truncation. If a more complete HTML review is needed in a future version, consider chunking the HTML and making multiple calls.

---

## Response Validation Requirements

Every Bedrock response must be validated before use. The following pattern is mandatory:

```python
try:
    resp = bedrock.invoke_model(modelId=MODEL_ID, body=body)
    raw = json.loads(resp["body"].read())["content"][0]["text"]
    # Strip accidental markdown code fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw)
    return _validate_result(result)
except Exception as e:
    print(f"[WARN] Bedrock call failed: {e}")
    return _fallback_result()
```

The `_validate_result()` function must:
- Apply `setdefault()` for every required field
- Recompute derived fields (e.g., `issue_counts`) from the actual data rather than trusting the model's count
- Never raise an exception — always return a valid object

The `_fallback_result()` function must return a complete object with safe defaults that allows the pipeline to continue without the AI output.

---

## Cost Monitoring

At the current usage estimate of 100 campaigns/month, the Bedrock cost is approximately:

| Model | Avg input tokens | Avg output tokens | Cost per call | Monthly cost (100 calls) |
|---|---|---|---|---|
| Claude 3 Haiku (classifier) | ~800 | ~200 | ~$0.0003 | ~$0.03 |
| Claude 3 Sonnet (reviewer) | ~3,000 | ~1,500 | ~$0.014 | ~$1.40 |
| **Total** | | | | **~$1.43** |

If monthly Bedrock costs exceed $10, investigate whether the HTML truncation limit has been increased or whether the models have been changed. Add a CloudWatch metric for Bedrock invocation count as part of the Sprint 2 CloudWatch MCP integration.

---

## IAM Policy Alignment

The CDK stack grants `bedrock:InvokeModel` only on the two specific model ARNs. When adding a new Bedrock call, always update `annotator_stack.py` to add the new model ARN to the IAM policy. Never use a wildcard (`*`) resource for Bedrock permissions.

```python
# Correct IAM pattern — specific model ARNs only
processor_fn.add_to_role_policy(iam.PolicyStatement(
    sid="BedrockInvokeModels",
    actions=["bedrock:InvokeModel"],
    resources=[
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
    ],
))
```

---

## Future Bedrock Integrations (MCP Roadmap)

The following Bedrock capabilities are planned for future sprints. When implementing them, follow the same standards defined in this document.

**Sprint 1 — Bedrock Knowledge Bases MCP:** Augment the reviewer's system prompt with retrieved chunks from a knowledge base containing brand guidelines, approved claims, and regulatory documents. The retrieved context is injected into the user message before the HTML sample.

**Sprint 3 — Bedrock Data Automation MCP:** Pass the rendered desktop and mobile screenshots to Bedrock's multimodal capability for a visual review pass. This detects contrast failures, broken image layouts, and small tap targets that are not visible in the HTML source.
