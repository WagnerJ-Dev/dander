"""Cloud Run function entrypoint for the Dander billing kill switch."""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import TYPE_CHECKING, Any

import functions_framework
from google.cloud import billing_v1
from handler import handle_budget_notification

if TYPE_CHECKING:
    from cloudevents.http import CloudEvent

_LOGGER = logging.getLogger(__name__)


@functions_framework.cloud_event
def stop_billing(cloud_event: CloudEvent) -> None:
    """Handle one Pub/Sub budget update."""
    try:
        encoded = cloud_event.data["message"]["data"]
        payload: Any = json.loads(base64.b64decode(encoded).decode("utf-8"))
        result = handle_budget_notification(
            payload,
            project_id=os.environ["TARGET_PROJECT_ID"],
            expected_budget_name=os.environ["EXPECTED_BUDGET_NAME"],
            simulate=os.environ.get("SIMULATE_DEACTIVATION", "true").lower() == "true",
            client=billing_v1.CloudBillingClient(),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        _LOGGER.exception("invalid_budget_notification")
        return
    _LOGGER.warning("cost_guard_result=%s", result)
