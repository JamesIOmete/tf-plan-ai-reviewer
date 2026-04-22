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

    with open(args.plan) as f:
        plan_data = json.load(f)

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
