# Agent Guidance

## Command approvals
- Ask before any `terraform apply`, `gh workflow run`, or cloud-CLI commands (`aws`, `az`, `gcloud`).
- Ask before any command that writes outside the repo or requires network access (except `pip install`).
- After important code changes and testing, offer to push updates to GitHub with a clear commit message. If approved, run `git add`, `git commit`, and `git push`.

## Validation defaults
- Do not run tests or validation unless explicitly requested.
- If asked to validate, run: `pytest tests/ -v`

## Credentials
- Do not read, modify, echo, or log any API keys, tokens, or secrets.
- `OPENAI_API_KEY`, `AZURE_OPENAI_KEY`, and `GITHUB_TOKEN` are secrets — never print them.

## State
- Do not commit `plan.json`, `*.tfplan`, or any `out/` directory content.
