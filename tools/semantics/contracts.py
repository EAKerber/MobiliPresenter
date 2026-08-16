from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import capability_gates, project_state, publication
from tools.semantics.registry import ROOT, load_registry, validate_registry

CAPABILITY_BASE_FIELDS={"schemaVersion","id","policy","gates","roundsWithoutActiveGates","maxRoundsWithoutActiveGates","deferReason"}
SEMANTIC_TOP_FIELDS={"schemaVersion","owners","concepts","contracts","branchGrammar","managedAuthorities","resources","components"}
SOURCE_BUILD_FIELDS=set(publication.TOP_FIELDS)


def _load_json(path:Path)->dict[str,Any]:
    try:value=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:raise RuntimeError(f"SEMANTIC_CONTRACT_JSON_INVALID:{path}") from exc
    if not isinstance(value,dict):raise RuntimeError(f"SEMANTIC_CONTRACT_ROOT_INVALID:{path}")
    return value

def check_capability_gates_contract()->list[str]:
    registry=load_registry();errors=validate_registry(registry)
    if errors:return errors
    contract=registry["contracts"].get("capability-gates")
    if not isinstance(contract,dict):return ["SEMANTIC_CAPABILITY_CONTRACT_MISSING"]
    if contract.get("semanticValidator")!="tools.capability_gates.validate_capability":return ["SEMANTIC_CAPABILITY_VALIDATOR_MISMATCH"]
    schema_path=ROOT/str(contract.get("structuralSchema"));schema=_load_json(schema_path);properties=schema.get("properties") if isinstance(schema.get("properties"),dict) else {};schema_fields=set(properties);accepted_fields=CAPABILITY_BASE_FIELDS|{"supervisorParticipation"}
    if schema_fields!=accepted_fields:errors.append("SEMANTIC_CAPABILITY_SCHEMA_FIELDS_MISMATCH")
    if set(schema.get("required") or [])!=CAPABILITY_BASE_FIELDS:errors.append("SEMANTIC_CAPABILITY_SCHEMA_REQUIRED_MISMATCH")
    policy_enum=set((properties.get("policy") or {}).get("enum") or []) if isinstance(properties.get("policy"),dict) else set()
    if policy_enum!=set(capability_gates.POLICIES):errors.append("SEMANTIC_CAPABILITY_POLICY_ENUM_MISMATCH")
    participation_enum=set((properties.get("supervisorParticipation") or {}).get("enum") or []) if isinstance(properties.get("supervisorParticipation"),dict) else set()
    if participation_enum!=set(capability_gates.SUPERVISOR_PARTICIPATION):errors.append("SEMANTIC_CAPABILITY_SUPERVISOR_ENUM_MISMATCH")
    for path in sorted(capability_gates.CAPABILITY_DIR.glob("*.json")):
        value=_load_json(path);runtime_errors=capability_gates.validate_capability(value,expected_id=path.stem)
        if runtime_errors:errors.append(f"SEMANTIC_CAPABILITY_RUNTIME_INVALID:{path.name}:{runtime_errors[0]}");continue
        if set(value)-schema_fields:errors.append(f"SEMANTIC_CAPABILITY_SCHEMA_REJECTS_RUNTIME:{path.name}")
        if value.get("policy") not in policy_enum:errors.append(f"SEMANTIC_CAPABILITY_SCHEMA_POLICY_REJECTS_RUNTIME:{path.name}")
        participation=value.get("supervisorParticipation")
        if participation is not None and participation not in participation_enum:errors.append(f"SEMANTIC_CAPABILITY_SCHEMA_SUPERVISOR_REJECTS_RUNTIME:{path.name}")
    return errors
def check_operational_semantics_contract()->list[str]:
    registry=load_registry();errors=validate_registry(registry);contract=registry.get("contracts",{}).get("operational-semantics")
    if not isinstance(contract,dict):return errors+["SEMANTIC_REGISTRY_CONTRACT_MISSING"]
    if contract.get("semanticValidator")!="tools.semantics.registry.validate_registry":errors.append("SEMANTIC_REGISTRY_VALIDATOR_MISMATCH")
    schema_path=ROOT/str(contract.get("structuralSchema"));schema=_load_json(schema_path)
    if schema.get("title")!="OperationalSemantics 0.2":errors.append("SEMANTIC_REGISTRY_SCHEMA_TITLE_MISMATCH")
    properties=schema.get("properties") if isinstance(schema.get("properties"),dict) else {}
    if set(properties)!=SEMANTIC_TOP_FIELDS:errors.append("SEMANTIC_REGISTRY_SCHEMA_FIELDS_MISMATCH")
    if set(schema.get("required") or [])!=SEMANTIC_TOP_FIELDS:errors.append("SEMANTIC_REGISTRY_SCHEMA_REQUIRED_MISMATCH")
    schema_version=properties.get("schemaVersion") if isinstance(properties.get("schemaVersion"),dict) else {}
    if schema_version.get("const")!=registry.get("schemaVersion"):errors.append("SEMANTIC_REGISTRY_SCHEMA_VERSION_MISMATCH")
    component_schema=properties.get("components") if isinstance(properties.get("components"),dict) else {};component_item=component_schema.get("additionalProperties") if isinstance(component_schema.get("additionalProperties"),dict) else {};required_component=set(component_item.get("required") or []);expected_component={"module","owner","kind","sideEffects","readsAuthorities","writesAuthorities","readsResources","writesResources","produces","canonicalWriterFor","delegatesTo"}
    if required_component!=expected_component:errors.append("SEMANTIC_COMPONENT_SCHEMA_REQUIRED_MISMATCH")
    return errors
def check_source_build_contract()->list[str]:
    registry=load_registry();errors=[];contract=registry.get("contracts",{}).get("source-build")
    if not isinstance(contract,dict):return ["SEMANTIC_SOURCE_BUILD_CONTRACT_MISSING"]
    if contract.get("semanticValidator")!="tools.publication.validate_manifest":errors.append("SEMANTIC_SOURCE_BUILD_VALIDATOR_MISMATCH")
    schema_path=ROOT/str(contract.get("structuralSchema"));schema=_load_json(schema_path);properties=schema.get("properties") if isinstance(schema.get("properties"),dict) else {}
    if set(properties)!=SOURCE_BUILD_FIELDS:errors.append("SEMANTIC_SOURCE_BUILD_SCHEMA_FIELDS_MISMATCH")
    if set(schema.get("required") or [])!=SOURCE_BUILD_FIELDS:errors.append("SEMANTIC_SOURCE_BUILD_SCHEMA_REQUIRED_MISMATCH")
    state=project_state.load_state();state_errors=project_state.validate_current(state)
    if state_errors:return errors+[f"SEMANTIC_SOURCE_BUILD_PROJECT_STATE_INVALID:{state_errors[0]['code']}"]
    view=project_state.operational_view(state);path=ROOT/view["published"]["artifactManifest"];manifest=_load_json(path);runtime_errors=publication.validate_manifest(manifest)
    if runtime_errors:errors.append(f"SEMANTIC_SOURCE_BUILD_RUNTIME_INVALID:{runtime_errors[0]['code']}")
    if set(manifest)!=SOURCE_BUILD_FIELDS:errors.append("SEMANTIC_SOURCE_BUILD_SCHEMA_REJECTS_RUNTIME")
    return errors

def check_project_state_contract()->list[str]:
    registry=load_registry();errors=[];contract=registry.get("contracts",{}).get("project-state")
    if not isinstance(contract,dict):return ["SEMANTIC_PROJECT_STATE_CONTRACT_MISSING"]
    if contract.get("semanticValidator")!="tools.project_state.validate_current":errors.append("SEMANTIC_PROJECT_STATE_VALIDATOR_MISMATCH")
    schema_path=ROOT/str(contract.get("structuralSchema"));schema=_load_json(schema_path);properties=schema.get("properties") if isinstance(schema.get("properties"),dict) else {}
    expected={"schemaVersion","project","git","published","development"}
    if set(properties)!=expected:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_FIELDS_MISMATCH")
    if set(schema.get("required") or [])!=expected:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_REQUIRED_MISMATCH")
    version=properties.get("schemaVersion") if isinstance(properties.get("schemaVersion"),dict) else {}
    if version.get("const")!=project_state.CURRENT_SCHEMA_VERSION:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_VERSION_MISMATCH")
    state=project_state.load_state();runtime_errors=project_state.validate_current(state)
    if runtime_errors:errors.append(f"SEMANTIC_PROJECT_STATE_RUNTIME_INVALID:{runtime_errors[0]['code']}")
    if set(state)!=expected:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_REJECTS_RUNTIME")
    nested={"project":{"id","repository"},"git":{"controlBranch","activeDevelopmentBranch","protectedBranches"},"published":{"url","artifactManifest"},"development":{"initiative","phase","checkpoint","nextTransition","blockers","prNumber"}}
    for name,fields in nested.items():
        spec=properties.get(name) if isinstance(properties.get(name),dict) else {};required=set(spec.get("required") or []);value=state.get(name)
        if required!=fields:errors.append(f"SEMANTIC_PROJECT_STATE_{name.upper()}_REQUIRED_MISMATCH")
        if not isinstance(value,dict) or set(value)!=fields:errors.append(f"SEMANTIC_PROJECT_STATE_{name.upper()}_RUNTIME_FIELDS_MISMATCH")
    return errors
def check_contracts()->list[str]:
    errors=check_capability_gates_contract();errors.extend(check_operational_semantics_contract());errors.extend(check_source_build_contract());errors.extend(check_project_state_contract());return errors
