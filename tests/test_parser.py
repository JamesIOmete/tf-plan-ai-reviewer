"""Tests for reviewer.parser.

The sample_plan.json fixture is a sanitized terraform plan -json output
for the UC06 inventory-diff-smoke use case from multicloud-sa-toolkit
(https://github.com/JamesIOmete/multicloud-sa-toolkit).
It creates: 1 VPC, 1 subnet, 1 security group (egress-only open to 0.0.0.0/0).
"""
import json
from pathlib import Path

import pytest

from reviewer.parser import parse_plan, PlanSummary

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return json.load(f)


class TestParsePlan:
    def test_create_counts(self):
        summary = parse_plan(load_fixture("sample_plan.json"))
        assert summary.add_count == 3
        assert summary.change_count == 0
        assert summary.destroy_count == 0
        assert summary.replace_count == 0

    def test_detects_open_egress(self):
        summary = parse_plan(load_fixture("sample_plan.json"))
        assert "aws_security_group.uc06" in summary.open_egress

    def test_no_open_ingress(self):
        summary = parse_plan(load_fixture("sample_plan.json"))
        assert summary.open_ingress == []

    def test_no_iam_changes(self):
        summary = parse_plan(load_fixture("sample_plan.json"))
        assert summary.iam_changes == []

    def test_no_sensitive_outputs(self):
        summary = parse_plan(load_fixture("sample_plan.json"))
        assert summary.sensitive_outputs == []

    def test_terraform_version(self):
        summary = parse_plan(load_fixture("sample_plan.json"))
        assert summary.terraform_version == "1.6.0"

    def test_resource_change_addresses(self):
        summary = parse_plan(load_fixture("sample_plan.json"))
        addresses = {rc.address for rc in summary.resource_changes}
        assert addresses == {"aws_vpc.uc06", "aws_subnet.uc06", "aws_security_group.uc06"}

    def test_noop_resources_excluded(self):
        """Resources with no-op actions must not appear in resource_changes."""
        data = load_fixture("sample_plan.json")
        data["resource_changes"].append({
            "address": "aws_vpc.other",
            "type": "aws_vpc",
            "change": {"actions": ["no-op"], "before": {}, "after": {}, "after_sensitive": {}},
        })
        summary = parse_plan(data)
        addresses = {rc.address for rc in summary.resource_changes}
        assert "aws_vpc.other" not in addresses
