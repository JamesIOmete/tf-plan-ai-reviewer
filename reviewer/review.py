"""CLI entrypoint for the Terraform Plan AI Reviewer."""
from __future__ import annotations

import argparse
import json
import os
import sys

from reviewer.parser import parse_plan
from reviewer.prompt import build_messages
from reviewer.llm import call_llm
from reviewer.formatter import format_comment


def post_github_comment(body: str) -> None:
    import requests

    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    pr_number = os.environ.get("PR_NUMBER", "")

    if not token or not repo or not pr_number:
        raise EnvironmentError(
            "GITHUB_TOKEN, GITHUB_REPOSITORY, and PR_NUMBER must all be set to post a comment."
        )

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.post(url, headers=headers, json={"body": body}, timeout=30)
    resp.raise_for_status()


def load_plan(path: str) -> dict:
    """
    Load a Terraform plan JSON file.

    terraform plan -json emits NDJSON — one JSON object per line, each with
    a "type" field. We extract the line where type == "plan" which contains
    the full plan data (resource_changes, output_changes, terraform_version)
    that the parser expects.

    Falls back to standard json.load() for single-object JSON files (e.g.
    terraform show -json output), so the tool works with both formats.
    """
    with open(path) as f:
        raw = f.read().strip()

    # Detect NDJSON: multiple lines each starting with '{'
    lines = [l.strip() for l in raw.splitlines() if l.strip()]

    if len(lines) > 1:
        # NDJSON format — find the "plan" type object
        for line in lines:
            try:
                obj = json.loads(line)
                if obj.get("type") == "plan":
                    return obj
            except json.JSONDecodeError:
                continue

        # Fallback: try the last non-empty line
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError:
            pass

        raise ValueError(
            "Could not find a 'type': 'plan' object in the NDJSON stream. "
            "Ensure the plan file was produced by: terraform plan -json"
        )

    # Single JSON object
    return json.loads(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI review of a Terraform plan")
    parser.add_argument("--plan", required=True, help="Path to terraform plan -json output")
    parser.add_argument(
        "--post-comment",
        action="store_true",
        help="Post the review as a GitHub PR comment",
    )
    parser.add_argument("--output", help="Write review markdown to this file instead of stdout")
    args = parser.parse_args(argv)

    plan_data = load_plan(args.plan)

    summary = parse_plan(plan_data)
    messages = build_messages(summary)
    raw_review = call_llm(messages)
    comment_body = format_comment(raw_review, summary)

    if args.post_comment:
        post_github_comment(comment_body)
        print("Review posted as PR comment.")
    elif args.output:
        with open(args.output, "w") as f:
            f.write(comment_body)
        print(f"Review written to {args.output}")
    else:
        print(comment_body)

    return 0


if __name__ == "__main__":
    sys.exit(main())
