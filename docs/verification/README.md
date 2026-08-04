# Verification reports — writing standard

Each phase ship report (`P*_REPORT.md`, `DAY*_REPORT.md`) must answer **two audiences**:

1. **Auditors / gates** — what shipped, test matrix, prime_check evidence.
2. **Future maintainers** — what code exists, why it is shaped this way, and whether it will still be pleasant to change in a year.

A report that only lists deliverables and green gates is **incomplete**.

---

## Required sections (every report)

| # | Section | Purpose |
|---|---------|---------|
| 1 | **Header** | Date, package, path, tier, status, next phase |
| 2 | **What landed** | Tables: paths, one-line role per module |
| 3 | **Implementation walkthrough** | Per service/function: inputs → logic → outputs; cite key files |
| 4 | **Naming & readability** | Why names were chosen; what a reader sees first in each file |
| 5 | **Function size & complexity** | LOC per file; cyclomatic / Prime A11 compliance; split decisions |
| 6 | **Deliberate simplicity** | What we **did not** build (no god objects, no duplicate SSOT, no silent fakes) |
| 7 | **Maintainability (1-year view)** | What P3/P4/P5 will touch; extension points; risks |
| 8 | **Test matrix** | IDs → test files |
| 9 | **Out of scope** | Deferred items with target phase |
| 10 | **Verification commands** | Exact `uv run …` block + expected counts |
| 11 | **Evidence (sealed)** | Copy-paste block for prime_check / ADR |

Sections 3–7 are **mandatory** from P2 onward. Older reports (P1, P1b, Day0) should gain a short **Implementation & maintainability** block when touched.

---

## Implementation walkthrough — checklist

For each new **service**, **port**, or **non-trivial function**, document:

- **Signature** — sync/async, `Result`/`Err`/`Ok` contract
- **Dependencies** — injected ports only (no hidden globals)
- **Control flow** — numbered steps or ASCII pipeline
- **Error paths** — which errors bubble vs map to reply + emit
- **Invariants** — e.g. “exactly one emit after RequestContext exists”

Use code citations sparingly (one representative snippet per service is enough).

---

## Quality rubric (honest self-review)

Score each dimension **Low / OK / Strong** with one sentence of evidence:

| Dimension | Question |
|-----------|----------|
| **Readability** | Can a new dev follow the happy path in &lt;5 minutes without TDD open? |
| **Naming** | Do types/functions say *what* and *when* (`PreAuthError`, `run_execution_plan`, not `handle`/`process`)? |
| **Small functions** | Any function &gt; ~40 LOC or cyclomatic &gt; 10? If yes, why split or why exception? |
| **No over-engineering** | Abstract factories, generic registries, or indirection without a second caller? |
| **Year-ahead maintenance** | Where will the next phase plug in? Any copy-paste or SSOT drift risk? |

Do not claim “clean code” without pointing at concrete structure (file sizes, split functions, single dispatch site).

---

## Template snippet (copy into new reports)

```markdown
## Implementation walkthrough

### `<ServiceName>` (`path/to/file.py`, ~N LOC)

1. …
2. …

**Return contract:** …

## Naming & readability

- …

## Function size & complexity

| File | LOC | Notes |
|------|-----|-------|

## Deliberate simplicity

- Did **not** …

## Maintainability (1-year view)

- P(N+1) will replace …
- Risk: …

## Quality rubric

| Dimension | Score | Evidence |
|-----------|-------|----------|
| Readability | OK | … |
| Naming | Strong | … |
| Small functions | Strong | … |
| No over-engineering | Strong | … |
| Year-ahead maintenance | OK | … |
```

---

## Index

| Report | Phase |
|--------|-------|
| [DAY0_REPORT.md](./DAY0_REPORT.md) | Bootstrap |
| [DAY0_5_REPORT.md](./DAY0_5_REPORT.md) | Domain skeleton |
| [P1_REPORT.md](./P1_REPORT.md) | Policy + guard |
| [P1B_REPORT.md](./P1B_REPORT.md) | PglastSqlAnalyzer |
| [P2_REPORT.md](./P2_REPORT.md) | InvokeAgentTool + ZTA |
| [P3_REPORT.md](./P3_REPORT.md) | JsonAgentPolicyStore + LimePassportVerifier |
| [P4_REPORT.md](./P4_REPORT.md) | AsyncpgDatabaseGateway + Testcontainers |
| [P5_REPORT.md](./P5_REPORT.md) | MCP Streamable HTTP + ConsoleSink |
