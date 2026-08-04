"""CLI: python -m scripts.prime_check"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from scripts.prime_check.config import load_config
from scripts.prime_check.evidence import render_evidence
from scripts.prime_check.orchestrator import exit_code, run_all
from scripts.prime_check.registry import all_step_ids
from scripts.prime_check.reporter import render_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prime_check")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--only", type=str, default=None, help="comma-separated steps")
    parser.add_argument("--diff", action="store_true", help="reserved; runs selected/FULL")
    parser.add_argument("--evidence", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report", type=str, default=None)
    parser.add_argument("--fail-fast", action="store_true", help="dev only; not default")
    args = parser.parse_args(argv)

    cfg = load_config()

    if args.list:
        skipped = cfg.skipped_steps
        for step_id in all_step_ids(skipped):
            if step_id in skipped:
                print(f"SKIPPED({skipped[step_id].get('adr', 'ADR-002')}) {step_id}")
            else:
                print(f"LIVE {step_id}")
        return 0

    only = set(args.only.split(",")) if args.only else None
    results = run_all(cfg, only=only)

    report = render_report(results)
    print(report)

    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")

    if args.json:
        payload = [
            {
                "step": r.step_id,
                "status": r.status.value,
                "duration_ms": r.duration_ms,
                "skip_adr": r.skip_adr,
                "detail": r.detail,
                "findings": [
                    {
                        "rule_id": f.rule_id,
                        "issue": f.issue,
                        "file": f.file,
                        "line": f.line,
                        "hint": f.hint,
                    }
                    for f in r.findings
                ],
            }
            for r in results
        ]
        print(json.dumps(payload, indent=2))

    code = exit_code(results)
    if args.evidence or code == 0:
        print()
        print(render_evidence(cfg, results))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
