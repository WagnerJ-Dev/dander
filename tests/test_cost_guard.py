"""Billing kill-switch tests for DANDER-23."""

from __future__ import annotations

from dataclasses import dataclass

from infra.functions.stop_billing.handler import handle_budget_notification


@dataclass
class _BillingInfo:
    billing_enabled: bool


class _Client:
    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self.updated: list[tuple[str, dict[str, str]]] = []

    def get_project_billing_info(self, *, name: str) -> _BillingInfo:
        assert name == "projects/dander-sbx-unit"
        return _BillingInfo(self._enabled)

    def update_project_billing_info(
        self,
        *,
        name: str,
        project_billing_info: dict[str, str],
    ) -> object:
        self.updated.append((name, project_billing_info))
        return object()


def _payload(*, cost: float = 5.0, name: str = "dander-sbx-cap") -> dict[str, object]:
    return {
        "budgetDisplayName": name,
        "costAmount": cost,
        "budgetAmount": 5.0,
    }


def test_simulation_never_changes_billing() -> None:
    client = _Client()

    result = handle_budget_notification(
        _payload(cost=6.0),
        project_id="dander-sbx-unit",
        expected_budget_name="dander-sbx-cap",
        simulate=True,
        client=client,
    )

    assert result == "simulated-disable"
    assert client.updated == []


def test_live_guard_disables_at_budget_threshold() -> None:
    client = _Client()

    result = handle_budget_notification(
        _payload(),
        project_id="dander-sbx-unit",
        expected_budget_name="dander-sbx-cap",
        simulate=False,
        client=client,
    )

    assert result == "billing-disabled"
    assert client.updated == [("projects/dander-sbx-unit", {"billing_account_name": ""})]


def test_guard_is_idempotent_when_billing_is_already_disabled() -> None:
    client = _Client(enabled=False)

    result = handle_budget_notification(
        _payload(cost=6.0),
        project_id="dander-sbx-unit",
        expected_budget_name="dander-sbx-cap",
        simulate=False,
        client=client,
    )

    assert result == "already-disabled"
    assert client.updated == []


def test_guard_ignores_unrelated_or_under_budget_notifications() -> None:
    client = _Client()

    results = [
        handle_budget_notification(
            _payload(name="another-budget"),
            project_id="dander-sbx-unit",
            expected_budget_name="dander-sbx-cap",
            simulate=False,
            client=client,
        ),
        handle_budget_notification(
            _payload(cost=4.99),
            project_id="dander-sbx-unit",
            expected_budget_name="dander-sbx-cap",
            simulate=False,
            client=client,
        ),
        handle_budget_notification(
            {},
            project_id="dander-sbx-unit",
            expected_budget_name="dander-sbx-cap",
            simulate=False,
            client=client,
        ),
        handle_budget_notification(
            _payload(cost=float("nan")),
            project_id="dander-sbx-unit",
            expected_budget_name="dander-sbx-cap",
            simulate=False,
            client=client,
        ),
    ]

    assert results == ["ignored", "within-budget", "ignored", "ignored"]
    assert client.updated == []
