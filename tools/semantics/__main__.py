from __future__ import annotations

import argparse
import json

from tools.semantics.branches import parse_branch_name
from tools.semantics.contracts import check_contracts
from tools.semantics.registry import aliases_for, concept, owner_of, validate_registry

ERROR_EXIT = 2


def _emit(value, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                print(f"{key}: {json.dumps(item, ensure_ascii=False)}")
            else:
                print(f"{key}: {item}")
    else:
        print(value)


def _check() -> dict:
    errors = validate_registry()
    errors.extend(check_contracts())
    return {
        "ok": not errors,
        "schemaVersion": "OperationalSemanticsCheck 0.1",
        "errors": errors,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m tools.semantics", description="MobiliPresenter operational semantics")
    sub = root.add_subparsers(dest="command", required=True)

    explain = sub.add_parser("explain")
    explain.add_argument("semantic_id")
    explain.add_argument("--json", action="store_true", dest="as_json")

    check = sub.add_parser("check")
    check.add_argument("--json", action="store_true", dest="as_json")

    branch = sub.add_parser("branch")
    branch.add_argument("name")
    branch.add_argument("--json", action="store_true", dest="as_json")
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "explain":
            item = concept(args.semantic_id)
            payload = {
                **item,
                "owner": owner_of(args.semantic_id),
                "aliases": aliases_for(args.semantic_id),
            }
        elif args.command == "branch":
            payload = parse_branch_name(args.name)
        else:
            payload = _check()
            _emit(payload, args.as_json)
            return 0 if payload["ok"] else ERROR_EXIT
        _emit(payload, args.as_json)
        return 0
    except RuntimeError as exc:
        _emit({"ok": False, "error": str(exc)}, getattr(args, "as_json", False))
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
