# Repository certification (BusinesAIOS)

This repo ships with a lightweight, stdlib-only certification gate to prevent architectural drift.

What it enforces (hard rules)
- **Network isolation:** real network clients / SDKs must live only under `runtime/_internal/`.

What it observes (soft diagnostics)
- **Warnings:** conservative, actionable risks that *may* fail CI when strict mode is enabled.
  - Example: an unusually large module (“god-module”).
- **Signals:** informational diagnostics that never fail CI.
  - Example: emerging "god-object" surface, rising cyclomatic complexity, or potential policy density.

The philosophy is intentional:
- **Hard rules stay hard.**
- **Soft risks stay visible** without turning CI into noise.

## Modes

### Warn-only (default)

Local development uses warn-only by default:

```bash
python scripts/certify_repo.py --root .
```

### Strict (CI)

CI enforces strict mode via environment variables:

- `CI=1` or `GITHUB_ACTIONS=1` in most pipelines
- or explicitly `BUSINESAIOS_CERT_STRICT=1`

You can enable strict locally:

```bash
BUSINESAIOS_CERT_STRICT=1 python scripts/certify_repo.py --root .
```

Strict mode behavior
- **violations** → fail
- **warnings** → fail
- **signals** → never fail

The strict CI enforcement is implemented by:
- `tests/test_repo_certification_ci_strict.py`
