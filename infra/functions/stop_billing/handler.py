"""Core cost-guard behavior, isolated from the Cloud Functions framework."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Protocol

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")


class BillingInfo(Protocol):
    """Billing status returned by the Cloud Billing client."""

    billing_enabled: bool


class BillingClient(Protocol):
    """Small Cloud Billing client surface used by the kill switch."""

    def get_project_billing_info(self, *, name: str) -> BillingInfo:
        """Return project billing status."""

    def update_project_billing_info(
        self,
        *,
        name: str,
        project_billing_info: dict[str, str],
    ) -> object:
        """Update a project's billing association."""


def handle_budget_notification(
    payload: object,
    *,
    project_id: str,
    expected_budget_name: str,
    simulate: bool,
    client: BillingClient,
) -> str:
    """Evaluate one budget update and optionally unlink project billing."""
    if not _PROJECT_ID.fullmatch(project_id):
        raise ValueError(f"Invalid project id: {project_id!r}")
    if not isinstance(payload, dict) or payload.get("budgetDisplayName") != expected_budget_name:
        return "ignored"

    try:
        cost = Decimal(str(payload["costAmount"]))
        budget = Decimal(str(payload["budgetAmount"]))
    except (InvalidOperation, KeyError, ValueError):
        return "ignored"
    if not cost.is_finite() or not budget.is_finite() or budget <= 0:
        return "ignored"
    if cost < budget:
        return "within-budget"
    if simulate:
        return "simulated-disable"

    project_name = f"projects/{project_id}"
    if not client.get_project_billing_info(name=project_name).billing_enabled:
        return "already-disabled"
    client.update_project_billing_info(
        name=project_name,
        project_billing_info={"billing_account_name": ""},
    )
    return "billing-disabled"
