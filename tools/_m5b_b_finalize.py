#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

# Semantic contract: only the canonical 0.2 schema/runtime pair remains.
p=ROOT/'tools/semantics/contracts.py';text=p.read_text(encoding='utf-8')
start=text.index('def check_continuation_state_contract()->list[str]:')
end=text.index('def check_operational_semantics_contract()->list[str]:')
block='''def check_continuation_state_contract()->list[str]:\n    registry=load_registry();errors=[];contract=registry.get("contracts",{}).get("continuation-state")\n    if not isinstance(contract,dict):return ["SEMANTIC_CONTINUATION_CONTRACT_MISSING"]\n    if contract.get("semanticValidator")!="tools.continuation.validate_current":errors.append("SEMANTIC_CONTINUATION_VALIDATOR_MISMATCH")\n    schema_path=ROOT/str(contract.get("structuralSchema"));schema=_load_json(schema_path);properties=schema.get("properties") if isinstance(schema.get("properties"),dict) else {}\n    if set(properties)!=continuation.FIELDS:errors.append("SEMANTIC_CONTINUATION_SCHEMA_FIELDS_MISMATCH")\n    if set(schema.get("required") or [])!=continuation.FIELDS:errors.append("SEMANTIC_CONTINUATION_SCHEMA_REQUIRED_MISMATCH")\n    version=properties.get("schemaVersion") if isinstance(properties.get("schemaVersion"),dict) else {}\n    if version.get("const")!=continuation.CURRENT_SCHEMA_VERSION:errors.append("SEMANTIC_CONTINUATION_SCHEMA_VERSION_MISMATCH")\n    statuses=set((properties.get("status") or {}).get("enum") or []) if isinstance(properties.get("status"),dict) else set()\n    if statuses!={item.value for item in WorkStatus}:errors.append("SEMANTIC_CONTINUATION_STATUS_ENUM_MISMATCH")\n    return errors\n\n'''
p.write_text(text[:start]+block+text[end:],encoding='utf-8')

# Local scope cannot observe the Git-backed Work authority; do not recreate a local model.
p=ROOT/'tools/project_sensors.py';text=p.read_text(encoding='utf-8')
start=text.index('def observe_continuations_local():')
end=text.index('def observe_continuations_live():')
block='''def observe_continuations_local():\n    return sensor(\n        "UNKNOWN",\n        code="NOT_OBSERVED_IN_LOCAL_SCOPE",\n        data={"available":False,"reason":"NOT_REQUESTED","authorityBranch":"coordination/continuations","authorityHead":None,"items":[],"mode":"not-observed"},\n        required=False,\n        authority={"kind":"git-authority","branch":"coordination/continuations"},\n    )\n\n\n'''
p.write_text(text[:start]+block+text[end:],encoding='utf-8')

# Candidate schema and migration-only tests have completed their purpose.
for rel in ('ops/schemas/continuation-state-0.2.schema.json','tools/tests/test_continuation_compatibility.py','tools/tests/test_m5b_work_authority_migration.py'):
    q=ROOT/rel
    if q.exists():q.unlink()

# ADR records the promotion without rewriting its historical rationale.
p=ROOT/'docs/adr/0007-work-authority.md';text=p.read_text(encoding='utf-8')
text=text.replace('- Status: proposed for M5A/M5B','- Status: accepted — M5B promoted ContinuationState 0.2')
if '## M5B promotion' not in text:
    text += '''\n\n## M5B promotion\n\nM5B migrated the existing `coordination/continuations` authority atomically from `ContinuationState 0.1` to `ContinuationState 0.2`. The authority branch/path and canonical writer did not change. The 0.1 compatibility bridge and candidate schema are retired after verified readback. All normal writes validate the complete candidate WorkGraph before CAS and the complete readback WorkGraph afterward. Historical terminal probe records remain sanitation debt for M6.\n'''
p.write_text(text,encoding='utf-8')
print('M5B-B finalize transformations applied')
