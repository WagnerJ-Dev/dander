# Morning Handoff

## Finished

- Generated an API-v1 Dander connector-plugin scaffold for __DISPLAY_NAME__.

## Try It

```bash
uv sync --extra dev
uv run pytest
```

## Checks

- Not run yet; generated code must be validated before publication.

## Decisions

- Start with Dander's bounded generic REST source and one synthetic record endpoint.

## Remaining

- Replace the placeholder API contract, schema, fixtures, documentation, and support claims.
- Add authentication and secret references through Dander core when the provider requires them.
- Validate against a simulator and then one narrow real account before claiming provider support.

## Review First

- `src/__PACKAGE_NAME__/plugin.py`
- `src/__PACKAGE_NAME__/templates/__PLUGIN_ID__.example.yaml`
- `tests/test_plugin.py`
