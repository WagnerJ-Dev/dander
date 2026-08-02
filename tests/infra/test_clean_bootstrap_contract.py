"""Contracts required for a first-run bootstrap in an empty GCP project."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_stage_zero_enables_cloud_resource_manager_before_platform_plan() -> None:
    stage_zero = (ROOT / "infra/bootstrap-admin/main.tf").read_text()

    assert '"cloudresourcemanager.googleapis.com"' in stage_zero


def test_cost_guard_defers_project_lookup_until_required_apis_are_enabled() -> None:
    cost_guard = (ROOT / "infra/modules/cost-guard/main.tf").read_text()
    project_lookup = cost_guard.split('data "google_project" "current"', maxsplit=1)[1]
    project_lookup = project_lookup.split("resource ", maxsplit=1)[0]

    assert "depends_on = [google_project_service.required]" in project_lookup


def test_cost_guard_grants_the_documented_billing_budget_publisher() -> None:
    cost_guard = (ROOT / "infra/modules/cost-guard/main.tf").read_text()

    assert "serviceAccount:billing-budget-alert@system.gserviceaccount.com" in cost_guard
    assert "billing-budget-alerts@system.gserviceaccount.com" not in cost_guard


def test_budget_resource_passes_the_bare_billing_account_id() -> None:
    cost_guard = (ROOT / "infra/modules/cost-guard/main.tf").read_text()
    budget = cost_guard.split('resource "google_billing_budget" "project"', maxsplit=1)[1]

    assert "billing_account = var.billing_account_id" in budget
    assert 'billing_account = "billingAccounts/${var.billing_account_id}"' not in budget


def test_cost_guard_waits_for_first_run_function_identities() -> None:
    cost_guard = (ROOT / "infra/modules/cost-guard/main.tf").read_text()
    wait = cost_guard.split('resource "time_sleep" "function_identity_propagation"', maxsplit=1)[
        1
    ].split('resource "google_cloudfunctions2_function"', maxsplit=1)[0]
    function = cost_guard.split(
        'resource "google_cloudfunctions2_function" "stop_billing"', maxsplit=1
    )[1].split('resource "google_billing_budget"', maxsplit=1)[0]

    assert 'create_duration = "120s"' in wait
    assert "google_service_account.builder" in wait
    assert "google_service_account.function" in wait
    assert "google_project_iam_member.builder" in wait
    assert "google_project_service.required" in wait
    assert "time_sleep.function_identity_propagation" in function
