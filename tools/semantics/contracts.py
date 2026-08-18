from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import capability_gates, continuation, coordination, project_state, publication, transition_protocol
from tools.semantics.registry import ROOT, load_registry, validate_registry
from tools.semantics.work import WorkStatus

CAPABILITY_BASE_FIELDS={"schemaVersion","id","policy","gates","roundsWithoutActiveGates","maxRoundsWithoutActiveGates","deferReason"}
SEMANTIC_TOP_FIELDS={"schemaVersion","owners","concepts","contracts","branchGrammar","managedAuthorities","resources","components"}
SOURCE_BUILD_FIELDS=set(publication.TOP_FIELDS)


def _load_json(path:Path)->dict[str,Any]:
    try:value=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:raise RuntimeError(f"SEMANTIC_CONTRACT_JSON_INVALID:{path}") from exc
    if not isinstance(value,dict):raise RuntimeError(f"SEMANTIC_CONTRACT_ROOT_INVALID:{path}")
    return value

def _contract(contract_id:str,validator:str)->tuple[dict[str,Any]|None,list[str]]:
    registry=load_registry();item=registry.get("contracts",{}).get(contract_id);errors=[]
    if not isinstance(item,dict):return None,[f"SEMANTIC_{contract_id.upper().replace('-','_')}_CONTRACT_MISSING"]
    if item.get("semanticValidator")!=validator:errors.append(f"SEMANTIC_{contract_id.upper().replace('-','_')}_VALIDATOR_MISMATCH")
    return item,errors

def _schema_for(contract:dict[str,Any])->dict[str,Any]:
    return _load_json(ROOT/str(contract.get("structuralSchema")))

def _properties(schema:dict[str,Any])->dict[str,Any]:
    value=schema.get("properties");return value if isinstance(value,dict) else {}

def _required(schema:dict[str,Any])->set[str]:return set(schema.get("required") or [])
def _pattern(spec:Any)->str|None:return spec.get("pattern") if isinstance(spec,dict) else None

def check_schema_registry_coverage()->list[str]:
    registry=load_registry();contracts=registry.get("contracts") if isinstance(registry.get("contracts"),dict) else {};errors=[];refs=[]
    for contract in contracts.values():
        if isinstance(contract,dict) and isinstance(contract.get("structuralSchema"),str):refs.append(contract["structuralSchema"])
    if len(refs)!=len(set(refs)):errors.append("SEMANTIC_SCHEMA_CONTRACT_DUPLICATE")
    registered=set(refs);actual={str(path.relative_to(ROOT)).replace("\\","/") for path in (ROOT/"ops"/"schemas").glob("*.schema.json")}
    if registered!=actual:
        missing=sorted(actual-registered);dangling=sorted(registered-actual)
        if missing:errors.append(f"SEMANTIC_SCHEMA_UNREGISTERED:{','.join(missing)}")
        if dangling:errors.append(f"SEMANTIC_SCHEMA_REFERENCE_MISSING:{','.join(dangling)}")
    return errors

def check_capability_gates_contract()->list[str]:
    registry=load_registry();errors=validate_registry(registry)
    if errors:return errors
    contract=registry["contracts"].get("capability-gates")
    if not isinstance(contract,dict):return ["SEMANTIC_CAPABILITY_CONTRACT_MISSING"]
    if contract.get("semanticValidator")!="tools.capability_gates.validate_capability":return ["SEMANTIC_CAPABILITY_VALIDATOR_MISMATCH"]
    schema_path=ROOT/str(contract.get("structuralSchema"));schema=_load_json(schema_path);properties=_properties(schema);schema_fields=set(properties);accepted_fields=CAPABILITY_BASE_FIELDS|{"supervisorParticipation"}
    if schema_fields!=accepted_fields:errors.append("SEMANTIC_CAPABILITY_SCHEMA_FIELDS_MISMATCH")
    if _required(schema)!=CAPABILITY_BASE_FIELDS:errors.append("SEMANTIC_CAPABILITY_SCHEMA_REQUIRED_MISMATCH")
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

def check_continuation_state_contract()->list[str]:
    registry=load_registry();errors=[];contract=registry.get("contracts",{}).get("continuation-state")
    if not isinstance(contract,dict):return ["SEMANTIC_CONTINUATION_CONTRACT_MISSING"]
    if contract.get("semanticValidator")!="tools.continuation.validate_current":errors.append("SEMANTIC_CONTINUATION_VALIDATOR_MISMATCH")
    schema=_schema_for(contract);properties=_properties(schema)
    if set(properties)!=continuation.FIELDS:errors.append("SEMANTIC_CONTINUATION_SCHEMA_FIELDS_MISMATCH")
    if _required(schema)!=continuation.FIELDS:errors.append("SEMANTIC_CONTINUATION_SCHEMA_REQUIRED_MISMATCH")
    version=properties.get("schemaVersion") if isinstance(properties.get("schemaVersion"),dict) else {}
    if version.get("const")!=continuation.CURRENT_SCHEMA_VERSION:errors.append("SEMANTIC_CONTINUATION_SCHEMA_VERSION_MISMATCH")
    statuses=set((properties.get("status") or {}).get("enum") or []) if isinstance(properties.get("status"),dict) else set()
    if statuses!={item.value for item in WorkStatus}:errors.append("SEMANTIC_CONTINUATION_STATUS_ENUM_MISMATCH")
    return errors

def check_coordination_state_contract()->list[str]:
    contract,errors=_contract("coordination-state","tools.coordination.validate_state")
    if contract is None:return errors
    schema=_schema_for(contract);properties=_properties(schema);defs=schema.get("$defs") if isinstance(schema.get("$defs"),dict) else {}
    if schema.get("additionalProperties") is not False:errors.append("SEMANTIC_COORDINATION_SCHEMA_OPEN_ROOT")
    if set(properties)!=coordination.STATE_FIELDS or _required(schema)!=coordination.STATE_FIELDS:errors.append("SEMANTIC_COORDINATION_SCHEMA_FIELDS_MISMATCH")
    version=properties.get("schemaVersion") if isinstance(properties.get("schemaVersion"),dict) else {}
    if version.get("const")!=coordination.SCHEMA_VERSION:errors.append("SEMANTIC_COORDINATION_SCHEMA_VERSION_MISMATCH")
    for name,expected in (("owner",coordination.OWNER_FIELDS),("intent",coordination.INTENT_FIELDS),("lease",coordination.LEASE_FIELDS)):
        spec=defs.get(name) if isinstance(defs.get(name),dict) else {};fields=_properties(spec)
        if spec.get("additionalProperties") is not False or set(fields)!=expected or _required(spec)!=expected:errors.append(f"SEMANTIC_COORDINATION_{name.upper()}_FIELDS_MISMATCH")
    lease=defs.get("lease") if isinstance(defs.get("lease"),dict) else {};lease_props=_properties(lease);ttl=lease_props.get("ttlSeconds") if isinstance(lease_props.get("ttlSeconds"),dict) else {};mode=lease_props.get("mode") if isinstance(lease_props.get("mode"),dict) else {}
    if mode.get("const")!="exclusive-write":errors.append("SEMANTIC_COORDINATION_MODE_MISMATCH")
    if ttl.get("minimum")!=1 or ttl.get("maximum")!=coordination.MAX_TTL_SECONDS:errors.append("SEMANTIC_COORDINATION_TTL_MISMATCH")
    try:coordination.validate_state(coordination.empty_state())
    except RuntimeError as exc:errors.append(f"SEMANTIC_COORDINATION_RUNTIME_INVALID:{exc}")
    return errors

def check_operational_semantics_contract()->list[str]:
    registry=load_registry();errors=validate_registry(registry);contract=registry.get("contracts",{}).get("operational-semantics")
    if not isinstance(contract,dict):return errors+["SEMANTIC_REGISTRY_CONTRACT_MISSING"]
    if contract.get("semanticValidator")!="tools.semantics.registry.validate_registry":errors.append("SEMANTIC_REGISTRY_VALIDATOR_MISMATCH")
    schema=_schema_for(contract)
    if schema.get("title")!="OperationalSemantics 0.2":errors.append("SEMANTIC_REGISTRY_SCHEMA_TITLE_MISMATCH")
    properties=_properties(schema)
    if set(properties)!=SEMANTIC_TOP_FIELDS:errors.append("SEMANTIC_REGISTRY_SCHEMA_FIELDS_MISMATCH")
    if _required(schema)!=SEMANTIC_TOP_FIELDS:errors.append("SEMANTIC_REGISTRY_SCHEMA_REQUIRED_MISMATCH")
    schema_version=properties.get("schemaVersion") if isinstance(properties.get("schemaVersion"),dict) else {}
    if schema_version.get("const")!=registry.get("schemaVersion"):errors.append("SEMANTIC_REGISTRY_SCHEMA_VERSION_MISMATCH")
    component_schema=properties.get("components") if isinstance(properties.get("components"),dict) else {};component_item=component_schema.get("additionalProperties") if isinstance(component_schema.get("additionalProperties"),dict) else {};required_component=set(component_item.get("required") or []);expected_component={"module","owner","kind","sideEffects","readsAuthorities","writesAuthorities","readsResources","writesResources","produces","canonicalWriterFor","delegatesTo"}
    if required_component!=expected_component:errors.append("SEMANTIC_COMPONENT_SCHEMA_REQUIRED_MISMATCH")
    return errors

def check_source_build_contract()->list[str]:
    registry=load_registry();errors=[];contract=registry.get("contracts",{}).get("source-build")
    if not isinstance(contract,dict):return ["SEMANTIC_SOURCE_BUILD_CONTRACT_MISSING"]
    if contract.get("semanticValidator")!="tools.publication.validate_manifest":errors.append("SEMANTIC_SOURCE_BUILD_VALIDATOR_MISMATCH")
    schema=_schema_for(contract);properties=_properties(schema)
    if set(properties)!=SOURCE_BUILD_FIELDS:errors.append("SEMANTIC_SOURCE_BUILD_SCHEMA_FIELDS_MISMATCH")
    if _required(schema)!=SOURCE_BUILD_FIELDS:errors.append("SEMANTIC_SOURCE_BUILD_SCHEMA_REQUIRED_MISMATCH")
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
    schema=_schema_for(contract);properties=_properties(schema);expected={"schemaVersion","project","git","published","development"}
    if set(properties)!=expected:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_FIELDS_MISMATCH")
    if _required(schema)!=expected:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_REQUIRED_MISMATCH")
    version=properties.get("schemaVersion") if isinstance(properties.get("schemaVersion"),dict) else {}
    if version.get("const")!=project_state.CURRENT_SCHEMA_VERSION:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_VERSION_MISMATCH")
    state=project_state.load_state();runtime_errors=project_state.validate_current(state)
    if runtime_errors:errors.append(f"SEMANTIC_PROJECT_STATE_RUNTIME_INVALID:{runtime_errors[0]['code']}")
    if set(state)!=expected:errors.append("SEMANTIC_PROJECT_STATE_SCHEMA_REJECTS_RUNTIME")
    nested={"project":{"id","repository"},"git":{"controlBranch","activeDevelopmentBranch","protectedBranches"},"published":{"url","artifactManifest"},"development":{"initiative","phase","checkpoint","nextTransition","blockers","prNumber"}}
    for name,fields in nested.items():
        spec=properties.get(name) if isinstance(properties.get(name),dict) else {};required=_required(spec);value=state.get(name)
        if required!=fields:errors.append(f"SEMANTIC_PROJECT_STATE_{name.upper()}_REQUIRED_MISMATCH")
        if not isinstance(value,dict) or set(value)!=fields:errors.append(f"SEMANTIC_PROJECT_STATE_{name.upper()}_RUNTIME_FIELDS_MISMATCH")
    return errors

def _check_transition_common(schema:dict[str,Any],errors:list[str],prefix:str)->None:
    props=_properties(schema)
    for name in ("domain","action"):
        if _pattern(props.get(name))!=transition_protocol.ID_PATTERN:errors.append(f"{prefix}_{name.upper()}_PATTERN_MISMATCH")
    subject=props.get("subject") if isinstance(props.get("subject"),dict) else {};subject_props=_properties(subject)
    if subject.get("additionalProperties") is not False or set(subject_props)!=transition_protocol.SUBJECT_FIELDS or _required(subject)!=transition_protocol.SUBJECT_FIELDS:errors.append(f"{prefix}_SUBJECT_FIELDS_MISMATCH")
    elif any(_pattern(subject_props.get(name))!=transition_protocol.ID_PATTERN for name in transition_protocol.SUBJECT_FIELDS):errors.append(f"{prefix}_SUBJECT_PATTERN_MISMATCH")
    authority=props.get("authority") if isinstance(props.get("authority"),dict) else {};authority_props=_properties(authority)
    if authority.get("additionalProperties") is not False or set(authority_props)!=transition_protocol.AUTHORITY_FIELDS or _required(authority)!=transition_protocol.AUTHORITY_FIELDS:errors.append(f"{prefix}_AUTHORITY_FIELDS_MISMATCH")
    elif _pattern(authority_props.get("kind"))!=transition_protocol.ID_PATTERN:errors.append(f"{prefix}_AUTHORITY_PATTERN_MISMATCH")
    locator=authority_props.get("locator") if isinstance(authority_props.get("locator"),dict) else {};additional=locator.get("additionalProperties") if isinstance(locator.get("additionalProperties"),dict) else {};choices=additional.get("oneOf") if isinstance(additional.get("oneOf"),list) else []
    string_choice=next((item for item in choices if isinstance(item,dict) and item.get("type")=="string"),{});int_choice=next((item for item in choices if isinstance(item,dict) and item.get("type")=="integer"),{})
    property_names=locator.get("propertyNames") if isinstance(locator.get("propertyNames"),dict) else {}
    if locator.get("type")!="object" or locator.get("minProperties")!=1 or property_names.get("minLength")!=1 or string_choice.get("minLength")!=1 or not int_choice:errors.append(f"{prefix}_LOCATOR_SHAPE_MISMATCH")

def check_transition_plan_contract()->list[str]:
    contract,errors=_contract("transition-plan","tools.transition_protocol.validate_plan")
    if contract is None:return errors
    schema=_schema_for(contract);properties=_properties(schema);prefix="SEMANTIC_TRANSITION_PLAN"
    if schema.get("additionalProperties") is not False or set(properties)!=transition_protocol.PLAN_FIELDS or _required(schema)!=transition_protocol.PLAN_FIELDS:errors.append(f"{prefix}_FIELDS_MISMATCH")
    version=properties.get("schemaVersion") if isinstance(properties.get("schemaVersion"),dict) else {}
    if version.get("const")!=transition_protocol.PLAN_SCHEMA:errors.append(f"{prefix}_VERSION_MISMATCH")
    _check_transition_common(schema,errors,prefix)
    for name in ("beforeStateHash","afterStateHash","planHash"):
        if _pattern(properties.get(name))!=transition_protocol.HASH_PATTERN:errors.append(f"{prefix}_{name.upper()}_PATTERN_MISMATCH")
    reversibility=set((properties.get("reversibility") or {}).get("enum") or []) if isinstance(properties.get("reversibility"),dict) else set()
    if reversibility!=transition_protocol.REVERSIBILITY:errors.append(f"{prefix}_REVERSIBILITY_MISMATCH")
    return errors

def check_transition_receipt_contract()->list[str]:
    contract,errors=_contract("transition-receipt","tools.transition_protocol.validate_receipt")
    if contract is None:return errors
    schema=_schema_for(contract);properties=_properties(schema);prefix="SEMANTIC_TRANSITION_RECEIPT"
    if schema.get("additionalProperties") is not False or set(properties)!=transition_protocol.RECEIPT_FIELDS or _required(schema)!=transition_protocol.RECEIPT_FIELDS:errors.append(f"{prefix}_FIELDS_MISMATCH")
    version=properties.get("schemaVersion") if isinstance(properties.get("schemaVersion"),dict) else {}
    if version.get("const")!=transition_protocol.RECEIPT_SCHEMA:errors.append(f"{prefix}_VERSION_MISMATCH")
    _check_transition_common(schema,errors,prefix)
    for name in ("planHash","beforeStateHash","afterStateHash","readbackStateHash","receiptHash"):
        if _pattern(properties.get(name))!=transition_protocol.HASH_PATTERN:errors.append(f"{prefix}_{name.upper()}_PATTERN_MISMATCH")
    revision=properties.get("authorityRevision") if isinstance(properties.get("authorityRevision"),dict) else {};choices=revision.get("oneOf") if isinstance(revision.get("oneOf"),list) else [];string_choice=next((item for item in choices if isinstance(item,dict) and item.get("type")=="string"),{});has_null=any(isinstance(item,dict) and item.get("type")=="null" for item in choices)
    if string_choice.get("minLength")!=1 or not has_null:errors.append(f"{prefix}_REVISION_SHAPE_MISMATCH")
    verified=properties.get("verified") if isinstance(properties.get("verified"),dict) else {}
    if verified.get("const") is not True:errors.append(f"{prefix}_VERIFIED_MISMATCH")
    return errors

def check_contracts()->list[str]:
    errors=check_schema_registry_coverage();errors.extend(check_capability_gates_contract());errors.extend(check_continuation_state_contract());errors.extend(check_coordination_state_contract());errors.extend(check_operational_semantics_contract());errors.extend(check_source_build_contract());errors.extend(check_project_state_contract());errors.extend(check_transition_plan_contract());errors.extend(check_transition_receipt_contract());return errors
