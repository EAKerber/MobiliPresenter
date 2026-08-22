from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.semantics.branches import parse_branch_name
from tools.semantics.contracts import check_contracts
from tools.semantics.convergence import build_inspection as build_convergence_inspection
from tools.semantics.convergence import load_prune_plan, validate_inspection as validate_convergence_inspection
from tools.semantics.coverage import build_inspection
from tools.semantics.maxims import maxim
from tools.semantics.registry import (
    aliases_for,
    component,
    concept,
    logical_capability,
    managed_authority,
    owner_of,
    provider_profile,
    tool_surface,
    validate_registry,
)

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
        "schemaVersion": "OperationalSemanticsCheck 0.3",
        "errors": errors,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m tools.semantics", description="MobiliPresenter operational semantics")
    sub = root.add_subparsers(dest="command", required=True)

    explain = sub.add_parser("explain")
    explain.add_argument("semantic_id")
    explain.add_argument("--json", action="store_true", dest="as_json")

    authority = sub.add_parser("authority")
    authority.add_argument("authority_id")
    authority.add_argument("--json", action="store_true", dest="as_json")

    component_parser = sub.add_parser("component")
    component_parser.add_argument("component_id")
    component_parser.add_argument("--json", action="store_true", dest="as_json")

    capability_parser = sub.add_parser("capability")
    capability_parser.add_argument("capability_id")
    capability_parser.add_argument("--json", action="store_true", dest="as_json")

    provider_parser = sub.add_parser("provider")
    provider_parser.add_argument("provider_id")
    provider_parser.add_argument("--json", action="store_true", dest="as_json")

    surface_parser = sub.add_parser("surface")
    surface_parser.add_argument("surface_id")
    surface_parser.add_argument("--json", action="store_true", dest="as_json")

    maxim_parser = sub.add_parser("maxim")
    maxim_parser.add_argument("maxim_id")
    maxim_parser.add_argument("--json", action="store_true", dest="as_json")

    coverage_parser = sub.add_parser("coverage")
    coverage_parser.add_argument("--json", action="store_true", dest="as_json")

    convergence = sub.add_parser("convergence")
    convergence.add_argument("--prune-plan", required=True)
    convergence.add_argument("--json", action="store_true", dest="as_json")

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
            payload = {**item, "owner": owner_of(args.semantic_id), "aliases": aliases_for(args.semantic_id)}
        elif args.command == "authority":
            payload = managed_authority(args.authority_id)
        elif args.command == "component":
            payload = component(args.component_id)
        elif args.command == "capability":
            payload = logical_capability(args.capability_id)
        elif args.command == "provider":
            payload = provider_profile(args.provider_id)
        elif args.command == "surface":
            payload = tool_surface(args.surface_id)
        elif args.command == "maxim":
            payload = maxim(args.maxim_id)
        elif args.command == "coverage":
            payload = build_inspection()
            _emit(payload, args.as_json)
            return 0 if payload["coverageComplete"] else ERROR_EXIT
        elif args.command == "convergence":
            payload = build_convergence_inspection(load_prune_plan(Path(args.prune_plan)))
            validate_convergence_inspection(payload)
            _emit(payload, args.as_json)
            return 0 if payload["coverageComplete"] and not payload["residues"] else ERROR_EXIT
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
