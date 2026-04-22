"""Parse terraform plan -json output into a structured PlanSummary."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Fragments that indicate IAM / privilege-related resource types
_IAM_TYPE_FRAGMENTS = ("iam", "policy", "role", "permission", "binding", "member")

# CIDRs that indicate fully-open network exposure
_OPEN_CIDRS = {"0.0.0.0/0", "::/0"}


@dataclass
class ResourceChange:
    address: str
    resource_type: str
    actions: list[str]
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    after_sensitive: dict[str, Any]


@dataclass
class PlanSummary:
    terraform_version: str
    resource_changes: list[ResourceChange]
    add_count: int = 0
    change_count: int = 0
    destroy_count: int = 0
    replace_count: int = 0
    iam_changes: list[str] = field(default_factory=list)
    open_egress: list[str] = field(default_factory=list)
    open_ingress: list[str] = field(default_factory=list)
    sensitive_outputs: list[str] = field(default_factory=list)


def parse_plan(data: dict[str, Any]) -> PlanSummary:
    terraform_version = data.get("terraform_version", "unknown")
    changes: list[ResourceChange] = []
    add_count = change_count = destroy_count = replace_count = 0
    iam_changes: list[str] = []
    open_egress: list[str] = []
    open_ingress: list[str] = []

    for rc in data.get("resource_changes", []):
        change = rc.get("change", {})
        actions: list[str] = change.get("actions", ["no-op"])

        if actions in (["no-op"], ["read"]):
            continue

        address = rc.get("address", "")
        resource_type = rc.get("type", "")
        before = change.get("before")
        after = change.get("after") or {}
        after_sensitive = change.get("after_sensitive") or {}

        rc_obj = ResourceChange(
            address=address,
            resource_type=resource_type,
            actions=actions,
            before=before,
            after=after,
            after_sensitive=after_sensitive,
        )
        changes.append(rc_obj)

        # Count by action type
        action_set = set(actions)
        if action_set == {"create"}:
            add_count += 1
        elif action_set == {"update"}:
            change_count += 1
        elif action_set == {"delete"}:
            destroy_count += 1
        elif action_set == {"delete", "create"}:
            replace_count += 1

        # IAM / privilege signal
        if any(frag in resource_type.lower() for frag in _IAM_TYPE_FRAGMENTS):
            iam_changes.append(address)

        # Network exposure
        _check_network_exposure(rc_obj, open_egress, open_ingress)

    # Sensitive output changes
    sensitive_outputs: list[str] = []
    for name, out in data.get("output_changes", {}).items():
        if out.get("change", {}).get("after_sensitive"):
            sensitive_outputs.append(name)

    return PlanSummary(
        terraform_version=terraform_version,
        resource_changes=changes,
        add_count=add_count,
        change_count=change_count,
        destroy_count=destroy_count,
        replace_count=replace_count,
        iam_changes=iam_changes,
        open_egress=open_egress,
        open_ingress=open_ingress,
        sensitive_outputs=sensitive_outputs,
    )


def _check_network_exposure(
    rc: ResourceChange,
    open_egress: list[str],
    open_ingress: list[str],
) -> None:
    if not rc.after:
        return

    rtype = rc.resource_type

    # AWS security group (inline rules)
    if rtype == "aws_security_group":
        for rule in rc.after.get("ingress", []) or []:
            if _has_open_cidr(rule):
                open_ingress.append(rc.address)
                break
        for rule in rc.after.get("egress", []) or []:
            if _has_open_cidr(rule):
                open_egress.append(rc.address)
                break

    # AWS security group standalone rule
    elif rtype == "aws_security_group_rule":
        direction = rc.after.get("type", "")
        if _has_open_cidr(rc.after):
            if direction == "ingress":
                open_ingress.append(rc.address)
            elif direction == "egress":
                open_egress.append(rc.address)

    # GCP compute firewall
    elif rtype == "google_compute_firewall":
        source_ranges = rc.after.get("source_ranges", []) or []
        if any(r in _OPEN_CIDRS for r in source_ranges):
            open_ingress.append(rc.address)


def _has_open_cidr(rule: dict[str, Any]) -> bool:
    cidrs = rule.get("cidr_blocks", []) or []
    ipv6 = rule.get("ipv6_cidr_blocks", []) or []
    return any(c in _OPEN_CIDRS for c in cidrs + ipv6)
