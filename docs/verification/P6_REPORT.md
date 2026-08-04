# LIME Ref Postgres MCP — P6 Ship Report

**Date:** 2026-08-04  
**Package:** `lime_ref_postgres_mcp` `0.1.0`  
**Path:** `Marketing/lime-postgres-mcp/` (package-only)  
**Tier:** PRIME · `adoption_mode: greenfield`  
**Status:** P6 complete — package-local CI hardened + SBOM LIVE  
**Next:** optional extract-to-own-repo; keep `prime_check` green  
**Report standard:** [README.md](./README.md)  
**Evidence task id:** `p6-ci-green`

---

## What landed

| Area | Paths | Role |
|------|-------|------|
| SBOM gate | `scripts/prime_check/steps/security.py` `sbom` | CycloneDX 1.5 from `uv export --frozen` → `reports/sbom.cdx.json` |
| Registry | `scripts/prime_check/registry.py` | `sbom` LIVE after `dependency-audit` |
| Config | `scripts/prime_check.config.yaml` | removed `sbom` skip |
| Workflow | `.github/workflows/prime_check.yml` | permissions, concurrency, timeout, uv cache, `--frozen`, SBOM artifact |
| Pin | `.python-version` | `3.12` |
| Deps layout | `pyproject.toml` | single `optional-dependencies.dev` (dropped duplicate dependency-group) |
| ADR | `docs/adr/ADR-002-…` | `sbom` → LIVE since P6 |

**Unchanged on purpose:** `ssrf-gate` SKIPPED; no monorepo root job; no `/health`; ConsoleSink untouched; local SSOT remains `uv run python -m scripts.prime_check`.

---

## Implementation walkthrough

### `sbom` step

1. `uv export --frozen --no-dev --no-hashes --no-annotate` (direct `uv`, not `uv run`).
2. Parse `name==version` lines (strip markers); skip editable `-e .`.
3. Emit CycloneDX 1.5 JSON with metadata.component = `lime-ref-postgres-mcp@0.1.0`.
4. Write `reports/sbom.cdx.json` (gitignored); assert non-empty + package name present.

### Workflow harden (extract-as-root)

1. `permissions: contents: read`
2. `concurrency` cancel-in-progress
3. `timeout-minutes: 45` (pip-audit + Testcontainers)
4. `setup-uv` cache on `uv.lock`
5. `uv sync --frozen --all-extras`
6. Exact `uv run python -m scripts.prime_check` (ci-parity)
7. Upload `reports/sbom.cdx.json` artifact
8. Comment: Docker required for integration inside prime_check

---

## Naming & readability

- Step id `sbom` matches ADR-002 / AGENT-5 catalog.
- Artifact path `reports/sbom.cdx.json` is the single operator-facing file.

---

## Function size & complexity

| File | Notes |
|------|-------|
| `security.sbom` | ~90 LOC parse+write; no new deps |
| Workflow | single job — local≡CI SSOT |

---

## Deliberate simplicity

- No Syft/Docker image SBOM (no Dockerfile).
- No monorepo root CI bridge (isolation law).
- No CodeQL / Scorecard / multi-Python matrix (B07).
- No second test job that bypasses `prime_check`.

---

## Maintainability (1-year view)

| Touch | Where |
|-------|--------|
| Version bump | update root_version in `sbom` or read from pyproject |
| Extract repo | nested workflow becomes root Actions as-is |
| New skip flips | ADR-002 only when surface appears |

### Quality rubric

| Dimension | Score | Evidence |
|-----------|-------|----------|
| Readability | Strong | One SBOM file + one workflow |
| Naming | Strong | Catalog step id |
| Small functions | OK | Single envelope step |
| No over-engineering | Strong | stdlib JSON CDX; no new tooling dep |
| Year-ahead | Strong | Frozen sync fails on lock drift |

---

## Test matrix

| ID | How |
|----|-----|
| sbom PASS | `prime_check --only sbom` / full suite |
| ci-parity | workflow still contains exact run string |
| Full gates | `uv run python -m scripts.prime_check` exit 0 |

---

## Out of scope

| Item | Why |
|------|-----|
| Monorepo `.github` job | package isolation |
| `gitleaks-history` | flip = extract-own-repo |
| WebhookSink / ssrf / health | showcase N/A |
| PyPI publish / SLSA | not P6 |

---

## Verification commands

```text
uv sync --frozen --all-extras
uv run python -m scripts.prime_check
```

**Observed:** `sbom` PASS; `prime_check` exit 0; coverage 100%.

---

## Evidence (sealed)

```text
PRIME-VERIFY-EVIDENCE
task: p6-ci-green
tier: PRIME
adoption_mode: greenfield
package: lime_ref_postgres_mcp
sbom: LIVE
prime_check: exit 0
coverage_line: 100.00%
coverage_branch: 100.00%
next_mandatory_task: extract-own-repo (optional) / maintain CI green
last_cmd: uv run python -m scripts.prime_check
```
