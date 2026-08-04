"""Human-readable report."""

from __future__ import annotations

from scripts.prime_check.finding import Status, StepResult


def render_report(results: list[StepResult]) -> str:
    lines: list[str] = []
    failed = [r for r in results if r.status in (Status.FAIL, Status.ERROR)]
    skipped = [r for r in results if r.status == Status.SKIPPED]
    passed = [r for r in results if r.status == Status.PASS]

    lines.append("=== EXEC SUMMARY ===")
    lines.append(f"PASS={len(passed)} FAIL={len(failed)} SKIPPED={len(skipped)}")
    lines.append("")
    lines.append("=== FIX PLAN ===")
    if not failed:
        lines.append("ALL GREEN - no fixes required")
    else:
        lines.append("P1 — fix all FAIL findings below, then re-run FULL")
        for r in failed:
            for f in r.findings:
                loc = f"{f.file}:{f.line}" if f.file else r.step_id
                lines.append(f"  [{f.priority}] {f.rule_id} {loc} — {f.issue}")
    lines.append("")
    lines.append("=== STEPS ===")
    for r in results:
        tag = r.status.value
        extra = f" ({r.skip_adr})" if r.skip_adr else ""
        detail = f" — {r.detail}" if r.detail else ""
        lines.append(f"[{tag}]{extra} {r.step_id} ({r.duration_ms}ms){detail}")
        for f in r.findings:
            lines.append(f"  FAIL {f.rule_id} [{f.priority}]")
            if f.file:
                lines.append(f"    file: {f.file}:{f.line or '?'}")
            lines.append(f"    issue: {f.issue}")
            if f.hint:
                lines.append(f"    hint: {f.hint}")
            if f.rerun:
                lines.append(f"    rerun: {f.rerun}")
    return "\n".join(lines)
