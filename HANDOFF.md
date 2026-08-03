# Morning Handoff

## Finished

- Tagged protected main as `v0.2.0rc3` and published the wheel and source distribution through the protected PyPI environment.
- Installed the public package outside the checkout, generated a source-free project, and built the retained image from PyPI.
- Applied the reviewed image-only plan: all three Cloud Run jobs now use digest `sha256:67c7050ca59a0ccdc4e72163b4d5309380275b78a41738204c84b06b140e36d5`.
- Completed Salesforce first ingestion and replay successfully.
- Restored Greenhouse and HubSpot schedules to tracked enabled state; Salesforce remains intentionally paused.

## Try It

```bash
uv tool install --force "dander-platform==0.2.0rc3"
dander --version
```

## Checks

- Protected publication run `30811104703` succeeded; public PyPI provides both rc3 wheel and sdist.
- First Salesforce run `dander-salesforce-accounts-pcsvr` and replay `dander-salesforce-accounts-dn4xj` succeeded without retries.
- Both runs extracted 13 accounts, built one model, passed four assertions, and published one metadata asset.
- Raw and modeled tables remain 13 rows with 13 distinct IDs; the canonical watermark did not regress.
- Lease released, no staging residue remains, all three alerts are enabled, and final Terraform plan reported `No changes.`

## Decisions

- Treat rc2 as failed acceptance and rc3 as the corrected candidate.
- Keep Salesforce scheduled execution paused while its manual proof is evaluated.
- Preserve the tracked daily Greenhouse and HubSpot operator-soak schedules.

## Remaining

- Observe one Greenhouse and one HubSpot execution on rc3 as the bounded candidate smoke.
- If both remain clean, decide whether to promote the unchanged runtime to final `0.2.0`.
- Continue the existing 30-day operator-soak issue on the newest accepted version.

## Review First

- `CHANGELOG.md`
- `src/dander/runtime.py`
- `tests/test_runtime.py`
