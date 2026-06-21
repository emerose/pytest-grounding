"""``grounding`` CLI — currently one verb, ``trace``.

    grounding trace <grounding_report.json | dir>      re-verify claims' inputs vs shas
    grounding trace <dir> --json                        machine-readable

Exit 0 if every claim is still grounded, 1 if any input changed/went missing.
"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="grounding", description="grounded-claims tooling")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("trace", help="re-verify each claim's inputs still match recorded shas")
    t.add_argument("path", help="grounding_report.json, or a directory containing it")
    t.add_argument("--json", action="store_true", help="machine-readable output")

    args = ap.parse_args(argv)

    if args.cmd == "trace":
        from . import trace as T

        result = T.trace(args.path)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(T.render(result))
        return 0 if result["status"] == "GROUNDED" else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
