# tf-plan-ai-reviewer

A GitHub Actions composite action that runs an AI review of a `terraform plan -json` output and posts a structured **PASS / WARN / BLOCK** verdict as a pull request comment.

Built to demonstrate AI-augmented IaC workflows. See also: [multicloud-sa-toolkit](https://github.com/JamesIOmete/multicloud-sa-toolkit) — the multi-cloud Terraform toolkit this reviewer was designed to complement. The fixture data in `tests/fixtures/` is drawn from that toolkit's UC06 plan output.

---

## How it works

```
terraform plan -json > plan.json
        │
        ▼
reviewer/parser.py     ← extracts resource changes, risk signals (IAM, open CIDRs, destroys)
        │
        ▼
reviewer/prompt.py     ← builds a structured LLM prompt from the parsed summary
        │
        ▼
reviewer/llm.py        ← calls OpenAI or Azure OpenAI
        │
        ▼
reviewer/formatter.py  ← renders a markdown PR comment with verdict + change table
        │
        ▼
GitHub PR comment
```

The reviewer is intentionally narrow: it takes plan JSON, produces a comment, and gets out of the way. It augments human review — it does not replace it.

---

## Quick start

Add this step to your repository's workflow **after** `terraform plan`:

```yaml
jobs:
  tf-plan-review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Terraform Init and Plan
        run: |
          terraform init
          terraform plan -json > plan.json
        working-directory: ./terraform

      - name: AI Plan Review
        uses: JamesIOmete/tf-plan-ai-reviewer@v1
        with:
          plan-json-path: terraform/plan.json   # workspace-relative
          openai-api-key: ${{ secrets.OPENAI_API_KEY }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

## Example PR comment

> ## 🤖 Terraform Plan AI Review
>
> **Verdict: ⚠️ WARN**
>
> | Action | Count |
> |--------|-------|
> | ➕ Create  | 3 |
> | 🔄 Update  | 0 |
> | 💥 Destroy | 0 |
> | ♻️ Replace  | 0 |
>
> ---
>
> **Summary:** This plan creates 3 new AWS resources — a VPC, a subnet, and a security group. No destructive changes are present.
>
> **Risk Findings:**
> - `WARN` — `aws_security_group.uc06`: egress permits all traffic to `0.0.0.0/0` on all protocols. This is a common default but confirm it is intentional.
>
> **Recommendations:**
> - Consider restricting egress to known destinations if this workload has a fixed outbound target.

---

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `plan-json-path` | Yes | — | Workspace-relative path to `terraform plan -json` output |
| `openai-api-key` | No* | — | OpenAI API key |
| `azure-openai-endpoint` | No* | — | Azure OpenAI endpoint URL |
| `azure-openai-key` | No* | — | Azure OpenAI API key |
| `azure-openai-deployment` | No | `gpt-4o` | Azure OpenAI deployment name |
| `model` | No | `gpt-4o` | Model name (OpenAI) |
| `github-token` | Yes | `${{ github.token }}` | Token for posting PR comment |

\* One of `openai-api-key` or the `azure-openai-*` pair must be provided.

---

## Running locally

```bash
pip install -r requirements.txt
terraform plan -json > plan.json
python -m reviewer.review --plan plan.json
```

To write the review to a file instead:

```bash
python -m reviewer.review --plan plan.json --output review.md
```

---

## Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## Design rationale

Terraform plan review is a step that engineers routinely skip or skim under time pressure. An AI reviewer catches patterns humans miss at speed: unexpected destroys, IAM privilege escalations, broadly-open security groups, and sensitive value exposure. It surfaces risk signals with enough context to make a human decision easy — not to automate that decision away.

The choice to implement this as a GitHub Actions composite action means it integrates into any Terraform repository with a single `uses:` line and no infrastructure to maintain.

---

## License

MIT
