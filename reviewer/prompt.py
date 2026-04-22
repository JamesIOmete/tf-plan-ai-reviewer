"""Build LLM messages from a PlanSummary."""
from __future__ import annotations

from reviewer.parser import PlanSummary

_SYSTEM = """\
You are a senior cloud infrastructure security reviewer with expertise in Terraform, AWS, Azure, and GCP.
You review Terraform plan summaries and produce concise, actionable feedback for a pull request comment.

Your output must be plain markdown (no outer code fences wrapping the entire response).
Structure your response as follows:

1. **Verdict** — one of: PASS, WARN, BLOCK
   - PASS: no notable risks, safe to merge
   - WARN: risks present but not critical; reviewer attention recommended
   - BLOCK: destructive or high-privilege changes that must be confirmed by a human before merge

2. **Summary** — 2-4 sentences in plain English describing what changes and why it matters

3. **Risk Findings** — bullet list; each item states the resource, the risk, and severity (LOW/MEDIUM/HIGH)
   - Omit this section entirely if there are no findings

4. **Recommendations** — optional, 1-3 actionable suggestions if relevant

Be concise. Do not repeat the full resource list — focus on what matters for a reviewer."""


def build_messages(summary: PlanSummary) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _format_plan_context(summary)},
    ]


def _format_plan_context(s: PlanSummary) -> str:
    lines = [
        f"Terraform version: {s.terraform_version}",
        f"Changes: +{s.add_count} create, ~{s.change_count} update, -{s.destroy_count} destroy, ±{s.replace_count} replace",
        "",
    ]

    if s.resource_changes:
        lines.append("Resource changes:")
        for rc in s.resource_changes:
            lines.append(f"  [{'/'.join(rc.actions)}] {rc.address} ({rc.resource_type})")
        lines.append("")

    if s.iam_changes:
        lines.append("IAM / policy changes detected (elevated privilege risk):")
        for addr in s.iam_changes:
            lines.append(f"  - {addr}")
        lines.append("")

    if s.open_ingress:
        lines.append("Open ingress (0.0.0.0/0 or ::/0) on:")
        for addr in s.open_ingress:
            lines.append(f"  - {addr}")
        lines.append("")

    if s.open_egress:
        lines.append("Open egress (0.0.0.0/0 or ::/0) on:")
        for addr in s.open_egress:
            lines.append(f"  - {addr}")
        lines.append("")

    if s.sensitive_outputs:
        lines.append("Sensitive outputs being set or changed:")
        for name in s.sensitive_outputs:
            lines.append(f"  - {name}")
        lines.append("")

    if s.destroy_count > 0 or s.replace_count > 0:
        lines.append(
            f"⚠️  Destructive operations: {s.destroy_count} destroy, {s.replace_count} replace"
        )

    return "\n".join(lines)
