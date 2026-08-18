#!/usr/bin/env python3
"""Read-only factual sensors for the MobiliPresenter project machine."""
from __future__ import annotations

from typing import Any

from tools import agent, capability_gates, continuation, coordination, project_state, publication
from tools.semantics.observation import ObservationStatus


def sensor(status: str, *, code: str | None = None, data: Any = None, required: bool = True, authority: dict[str, Any] | None = None) -> dict[str, Any]:
    try: normalized = ObservationStatus.parse(str(status).upper()).value
    except RuntimeError as exc: raise RuntimeError("PROJECT_SENSOR_STATUS_INVALID") from exc
    return {"status": normalized, "required": bool(required), "code": code, "authority": authority, "data": data}


def summarize_checks(checks: list[dict[str, Any]]) -> tuple[str, str | None]:
    statuses: list[str] = []
    for item in checks:
        try: statuses.append(ObservationStatus.parse(str(item.get("status") or ObservationStatus.UNKNOWN.value).upper()).value)
        except RuntimeError: statuses.append(ObservationStatus.FAIL.value)
    if ObservationStatus.FAIL.value in statuses:
        first = next((item for item in checks if str(item.get("status")).upper() == ObservationStatus.FAIL.value), {})
        return ObservationStatus.FAIL.value, str(first.get("code") or "CHECK_FAILED")
    if ObservationStatus.UNKNOWN.value in statuses:
        first = next((item for item in checks if str(item.get("status")).upper() == ObservationStatus.UNKNOWN.value), {})
        return ObservationStatus.UNKNOWN.value, str(first.get("code") or "CHECK_UNKNOWN")
    return ObservationStatus.PASS.value, None


def capability_items() -> list[dict[str, Any]]:
    out=[]
    for value in capability_gates.discover_capabilities():
        plan=capability_gates.build_review_plan(value)
        out.append({"id":value["id"],"policy":value["policy"],"supervisorParticipation":capability_gates.supervisor_participation(value),"reviewAction":plan["action"],"nextGates":plan["nextGates"],"backlogCount":len(plan["backlog"]),"roundsWithoutActiveGates":plan["roundsWithoutActiveGates"],"maxRoundsWithoutActiveGates":plan["maxRoundsWithoutActiveGates"],"deferReason":plan["deferReason"],"reviewPlanHash":plan["planHash"]})
    return out


def observe_capabilities():
    try:return sensor("PASS",data={"items":capability_items()},authority={"kind":"repository","path":"ops/capabilities"})
    except (RuntimeError,OSError,ValueError,KeyError) as exc:return sensor("FAIL",code="CAPABILITY_OBSERVATION_FAILED",data={"items":[],"detail":str(exc)},authority={"kind":"repository","path":"ops/capabilities"})


def continuation_item(value):
    view=continuation.operational_view(value)
    return {**view,"sourceSchemaVersion":value["schemaVersion"],"stateHash":continuation.state_hash(value)}


def observe_continuations_local():
    return sensor(
        "UNKNOWN",
        code="NOT_OBSERVED_IN_LOCAL_SCOPE",
        data={"available":False,"reason":"NOT_REQUESTED","authorityBranch":"coordination/continuations","authorityHead":None,"items":[],"mode":"not-observed"},
        required=False,
        authority={"kind":"git-authority","branch":"coordination/continuations"},
    )


def observe_continuations_live():
    try:
        from tools.continuation_remote import GitHubContinuationAuthority
        authority=GitHubContinuationAuthority(); observed=authority.observe(); items=[continuation_item(v) for _,v in sorted(observed.items.items())]
        return sensor("PASS",data={"available":True,"authorityBranch":authority.authority_branch,"authorityHead":observed.head_sha,"items":items,"mode":"live-authority"},authority={"kind":"git-authority","branch":authority.authority_branch})
    except (OSError,RuntimeError,ImportError) as exc:return sensor("UNKNOWN",code="CONTINUATION_AUTHORITY_UNAVAILABLE",data={"available":False,"reason":getattr(exc,"code","CONTINUATION_UNAVAILABLE"),"detail":getattr(exc,"detail",str(exc)),"items":[]},authority={"kind":"git-authority","branch":"coordination/continuations"})


def observe_pull_requests(state,*,live):
    view=project_state.operational_view(state)
    if not live:return sensor("UNKNOWN",code="NOT_OBSERVED_IN_LOCAL_SCOPE",data={"available":False,"reason":"NOT_REQUESTED","items":[]},required=False,authority={"kind":"github","resource":"pull-requests"})
    repo=view["project"]["repository"]; ok,payload=agent.run_gh_json(f"repos/{repo}/pulls?state=open&per_page=100")
    if not ok or not isinstance(payload,list):return sensor("UNKNOWN",code="REMOTE_PR_INVENTORY_UNAVAILABLE",data={"available":False,"reason":"OPEN_PR_READ_FAILED","detail":payload,"items":[]},authority={"kind":"github","resource":"pull-requests"})
    active_pr=view["development"].get("prNumber"); result_status="PASS"; result_code=None; items=[]
    for raw in payload:
        if not isinstance(raw,dict):continue
        head=raw.get("head") if isinstance(raw.get("head"),dict) else {}; base=raw.get("base") if isinstance(raw.get("base"),dict) else {}; head_sha=head.get("sha"); runs=[]; ci="unknown"; ci_observed=False
        if isinstance(head_sha,str):
            runs_ok,w=agent.run_gh_json(f"repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100")
            if runs_ok and isinstance(w,dict) and isinstance(w.get("workflow_runs"),list):
                ci_observed=True; runs=[{"name":x.get("name"),"status":x.get("status"),"conclusion":x.get("conclusion"),"id":x.get("id")} for x in w["workflow_runs"] if isinstance(x,dict)]; ci=agent.aggregate_ci(runs)
        number=raw.get("number")
        if isinstance(active_pr,int) and number==active_pr and not ci_observed:result_status="UNKNOWN";result_code="ACTIVE_PR_CI_UNAVAILABLE"
        items.append({"number":number,"draft":raw.get("draft"),"headRef":head.get("ref"),"headSha":head_sha,"baseRef":base.get("ref"),"ci":ci,"ciObserved":ci_observed,"workflows":runs})
    items.sort(key=lambda item:int(item.get("number") or 0)); return sensor(result_status,code=result_code,data={"available":True,"items":items},authority={"kind":"github","resource":"pull-requests"})


def observe_coordination(*,live):
    if not live:return sensor("UNKNOWN",code="NOT_OBSERVED_IN_LOCAL_SCOPE",data={"available":False,"reason":"NOT_REQUESTED","intents":[],"leases":[]},required=False,authority={"kind":"git-authority","branch":"coordination/leases"})
    try:
        from tools.coordination_remote import GhApiTransport,GitHubCoordinationAuthority
        authority=GitHubCoordinationAuthority(GhApiTransport()); observed=authority.observe(); current=coordination.compact_expired(observed.state,observed.authority_now)
        return sensor("PASS",data={"available":True,"authorityBranch":authority.authority_branch,"authorityHead":observed.head_sha,"intents":current["intents"],"leases":current["leases"]},authority={"kind":"git-authority","branch":authority.authority_branch})
    except (OSError,RuntimeError,ImportError) as exc:return sensor("UNKNOWN",code="COORDINATION_AUTHORITY_UNAVAILABLE",data={"available":False,"reason":getattr(exc,"code","COORDINATION_UNAVAILABLE"),"detail":getattr(exc,"detail",str(exc)),"intents":[],"leases":[]},authority={"kind":"git-authority","branch":"coordination/leases"})


def observe_control_head(state,*,live):
    view=project_state.operational_view(state); branch=view["git"]["controlBranch"]
    if live:
        repo=view["project"]["repository"];ok,payload=agent.run_gh_json(f"repos/{repo}/git/ref/heads/{branch}");sha=payload.get("object",{}).get("sha") if ok and isinstance(payload,dict) and isinstance(payload.get("object"),dict) else None
        if isinstance(sha,str) and len(sha)==40:return sensor("PASS",data={"branch":branch,"sha":sha,"mode":"remote"},authority={"kind":"git-ref","branch":branch})
        return sensor("UNKNOWN",code="CONTROL_HEAD_UNAVAILABLE",data={"branch":branch,"sha":None,"detail":payload},authority={"kind":"git-ref","branch":branch})
    ok,sha=agent.run_git("rev-parse",branch)
    if ok and isinstance(sha,str) and len(sha)==40:return sensor("PASS",data={"branch":branch,"sha":sha,"mode":"local"},authority={"kind":"git-ref","branch":branch})
    return sensor("UNKNOWN",code="CONTROL_HEAD_NOT_AVAILABLE_LOCALLY",data={"branch":branch,"sha":None},required=False,authority={"kind":"git-ref","branch":branch})


def observe_local_core(state):
    state_errors=project_state.validate_current(state)
    project_checks=[]
    if state_errors:
        project_checks.extend({"name":"project-state","status":"FAIL",**error} for error in state_errors);view=None
    else:
        project_checks.append({"name":"project-state","status":"PASS","code":None});view=project_state.operational_view(state)
    schema_ok=project_state.CURRENT_SCHEMA_PATH.is_file();project_checks.append({"name":"project-state-schema","status":"PASS" if schema_ok else "FAIL","code":None if schema_ok else "SCHEMA_FILE_MISSING"})

    repository_checks=[]
    for rel in ("AGENTS.md","README.md"):
        exists=(agent.ROOT/rel).is_file();repository_checks.append({"name":f"required:{rel}","status":"PASS" if exists else "FAIL","code":None if exists else "REQUIRED_FILE_MISSING"})

    publication_checks=[];publication_data={"checks":publication_checks};publication_path="ops/published/unknown";published_source=None
    if view is None:
        publication_checks.append({"name":"published-artifact-state","status":"FAIL","code":"PROJECT_STATE_INVALID"})
    else:
        publication_path=view["published"]["artifactManifest"]
        try:
            manifest=publication.load_manifest(publication_path);projection=publication.publication_view(view,manifest);publication_data.update(projection);published_source=projection["sourceBranch"]
            publication_checks.append({"name":"published-artifact-state","status":"PASS","code":None,"observedRelease":projection["release"],"observedSourceBranch":projection["sourceBranch"],"observedSourceBuildFingerprint":projection["sourceBuildFingerprint"],"fingerprintKind":projection["fingerprintKind"]})
        except RuntimeError as exc:
            publication_checks.append({"name":"published-artifact-state","status":"FAIL","code":str(exc).split(":",1)[0],"path":publication_path});publication_data["detail"]=str(exc)

    observed=agent.observed_git();git_checks=[]
    if view is None:git_checks.append({"name":"git-context","status":"FAIL","code":"PROJECT_STATE_INVALID"})
    else:git_checks.append(agent.git_context_check(state,observed,published_source_branch=published_source))

    all_checks=project_checks+publication_checks+repository_checks+git_checks;verification={**agent.verification_summary(all_checks),"checks":all_checks,"remote":None}
    project_status,project_code=summarize_checks(project_checks);publication_status,publication_code=summarize_checks(publication_checks);git_status,git_code=summarize_checks(git_checks);repository_status,repository_code=summarize_checks(repository_checks)
    return {
        "projectState":sensor(project_status,code=project_code,data={"verification":verification,"checks":project_checks},authority={"kind":"repository","path":"ops/state/project.json"}),
        "publication":sensor(publication_status,code=publication_code,data=publication_data,authority={"kind":"repository","path":publication_path}),
        "git":sensor(git_status,code=git_code,data={"observed":observed,"checks":git_checks},authority={"kind":"worktree"}),
        "repository":sensor(repository_status,code=repository_code,data={"checks":repository_checks},authority={"kind":"repository","name":view["project"]["repository"] if view else None}),
    }
