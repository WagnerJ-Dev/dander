# Python Conventions

Primary application language. Read alongside `01-security.md` and `02-engineering.md`.

## Toolchain (pinned)

- **Python 3.12+**.
- **uv** for env + dependency management (`uv sync`, `uv run`). Lockfile committed.
- **Ruff** for both linting and formatting (replaces black + flake8 + isort). `ruff check`, `ruff format`.
- **mypy** in strict mode (or pyright) — the codebase is fully type-annotated.
- **pytest** for tests.
- CI runs: `ruff check` → `ruff format --check` → `mypy` → `pytest`. All must pass.

## Code style (PEP 8 + house rules)

- 4-space indent, ~100-char lines (Ruff-enforced), snake_case functions/vars, PascalCase classes,
  UPPER_SNAKE constants.
- **Type-annotate everything** — all params, returns, and non-trivial locals. No bare `Any` without
  a comment justifying it.
- Prefer `pathlib` over `os.path`; f-strings over `%`/`.format`; comprehensions over manual loops
  when readable.
- **Pydantic v2** models for all config objects and external payloads (validation at the boundary).
  `@dataclass(frozen=True)` for internal value objects.
- Small pure functions; push side effects (I/O, network) to the edges. Dependency-inject clients
  so tests can mock them.
- Explicit exceptions with context; never bare `except:`. Never log secrets/PII.
- No mutable default args. No module-level side effects on import.

## Structure

- One class/concept per module where reasonable; group by domain (`security/`, `ingestion/`,
  `writer/`, `transform/`), not by type.
- Abstractions as `Protocol` or `ABC` (see `02-engineering.md`); concretes implement them.
- `if __name__ == "__main__":` only in intended entrypoints; prefer a `cli` module + `argparse`/`typer`.

## Documentation

- **Google-style docstrings** on every public module, class, and function:

  ```python
  def cast_field(value: object, target: BqType) -> object:
      """Cast a source value to a BigQuery-compatible Python value.

      Args:
          value: Raw value from the source payload.
          target: The resolved BigQuery type for this field.

      Returns:
          The value coerced to `target`'s Python representation.

      Raises:
          CastError: If `value` cannot be represented as `target`.
      """
  ```

- Document **why**, not what the code obviously does. Note invariants, units, and edge cases.
- Public interfaces (`Protocol`/`ABC`) carry the contract in their docstring; implementations
  don't repeat it, they note deviations.
- Keep a module-level docstring stating the module's responsibility.
- READMEs per top-level package explaining its role and how it plugs into the module map in
  `00-project-overview.md`.
