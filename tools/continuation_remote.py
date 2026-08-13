"""Git-backed remote authority for live Continuation State."""
from __future__ import annotations
import base64, json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from tools import continuation
from tools.coordination_remote import ApiError, GhApiTransport

DEFAULT_REPOSITORY="EAKerber/MobiliPresenter"; DEFAULT_BRANCH="coordination/continuations"; DEFAULT_DIR="ops/continuations"

class ContinuationRemoteError(RuntimeError):
    def __init__(self,code,detail=""):
        self.code=code; self.detail=detail; super().__init__(f"{code}:{detail}" if detail else code)

@dataclass(frozen=True)
class Observation:
    head_sha:str; tree_sha:str; items:dict[str,dict[str,Any]]

class GitHubContinuationAuthority:
    def __init__(self,transport=None,repository=DEFAULT_REPOSITORY,authority_branch=DEFAULT_BRANCH,state_dir=DEFAULT_DIR):
        self.transport=transport or GhApiTransport(); self.repository=repository; self.authority_branch=authority_branch; self.state_dir=state_dir
    @property
    def ref_endpoint(self): return f"repos/{self.repository}/git/ref/heads/{quote(self.authority_branch,safe='')}"
    @property
    def update_endpoint(self): return f"repos/{self.repository}/git/refs/heads/{quote(self.authority_branch,safe='')}"
    def _json(self,response,op):
        try: return json.loads(response.body)
        except json.JSONDecodeError as exc: raise ContinuationRemoteError("CONTINUATION_REMOTE_INVALID_RESPONSE",op) from exc
    def _sha(self,value,label):
        if not isinstance(value,str) or len(value)!=40: raise ContinuationRemoteError("CONTINUATION_REMOTE_INVALID_RESPONSE",label)
        return value
    def _head(self):
        try: payload=self._json(self.transport.request("GET",self.ref_endpoint),"read ref")
        except ApiError as exc: raise ContinuationRemoteError("CONTINUATION_REMOTE_UNAVAILABLE",exc.detail) from exc
        return self._sha((payload.get("object") or {}).get("sha"),"head")
    def _tree(self,head):
        payload=self._json(self.transport.request("GET",f"repos/{self.repository}/git/commits/{head}"),"read commit")
        return self._sha((payload.get("tree") or {}).get("sha"),"tree")
    def _task_endpoint(self,cid,ref): return f"repos/{self.repository}/contents/{quote(self.state_dir,safe='/')}/{quote(cid+'.json',safe='')}?ref={quote(ref,safe='')}"
    def _read_task(self,cid,ref):
        try: response=self.transport.request("GET",self._task_endpoint(cid,ref))
        except ApiError as exc:
            if exc.status==404: return None
            raise ContinuationRemoteError("CONTINUATION_REMOTE_UNAVAILABLE",exc.detail) from exc
        payload=self._json(response,"read task"); encoded=payload.get("content")
        if not isinstance(encoded,str) or payload.get("encoding")!="base64": raise ContinuationRemoteError("CONTINUATION_REMOTE_INVALID_RESPONSE","task content")
        try: value=json.loads(base64.b64decode(encoded).decode("utf-8"))
        except Exception as exc: raise ContinuationRemoteError("CONTINUATION_REMOTE_INVALID_STATE",cid) from exc
        errors=continuation.validate(value,cid)
        if errors: raise ContinuationRemoteError(errors[0],cid)
        return value
    def observe(self):
        head=self._head(); tree=self._tree(head)
        endpoint=f"repos/{self.repository}/contents/{quote(self.state_dir,safe='/')}?ref={quote(head,safe='')}"
        try: response=self.transport.request("GET",endpoint); listing=self._json(response,"list continuations")
        except ApiError as exc:
            if exc.status==404: return Observation(head,tree,{})
            raise ContinuationRemoteError("CONTINUATION_REMOTE_UNAVAILABLE",exc.detail) from exc
        if not isinstance(listing,list): raise ContinuationRemoteError("CONTINUATION_REMOTE_INVALID_RESPONSE","directory listing")
        items={}
        for entry in listing:
            name=entry.get("name") if isinstance(entry,dict) else None
            if isinstance(name,str) and name.endswith(".json") and not name.startswith("."):
                cid=name[:-5]; value=self._read_task(cid,head)
                if value is not None: items[cid]=value
        return Observation(head,tree,items)
    def plan_for(self,cid,planner):
        observed=self.observe(); before=observed.items.get(cid); planned=planner(before)
        return observed,planned
    def apply(self,planned,expected_plan):
        if planned.get("planHash")!=expected_plan: raise ContinuationRemoteError("CONTINUATION_PLAN_HASH_MISMATCH")
        observed=self.observe(); current=observed.items.get(planned["id"])
        if continuation.state_hash(current)!=planned.get("beforeStateHash"): raise ContinuationRemoteError("CONTINUATION_PLAN_STALE")
        content=json.dumps(planned["after"],indent=2,ensure_ascii=False)+"\n"
        blob=self._sha(self._json(self.transport.request("POST",f"repos/{self.repository}/git/blobs",payload={"content":content,"encoding":"utf-8"}),"create blob").get("sha"),"blob")
        path=f"{self.state_dir}/{planned['id']}.json"
        tree_payload={"base_tree":observed.tree_sha,"tree":[{"path":path,"mode":"100644","type":"blob","sha":blob}]}
        tree=self._sha(self._json(self.transport.request("POST",f"repos/{self.repository}/git/trees",payload=tree_payload),"create tree").get("sha"),"tree")
        commit_payload={"message":f"continuation: {planned['action']} {planned['id']}","tree":tree,"parents":[observed.head_sha]}
        commit=self._sha(self._json(self.transport.request("POST",f"repos/{self.repository}/git/commits",payload=commit_payload),"create commit").get("sha"),"commit")
        try: self.transport.request("PATCH",self.update_endpoint,payload={"sha":commit,"force":False})
        except ApiError as exc: raise ContinuationRemoteError("CONTINUATION_CAS_LOST",exc.detail) from exc
        readback=self.observe()
        if readback.head_sha!=commit: raise ContinuationRemoteError("CONTINUATION_READBACK_HEAD_MISMATCH")
        value=readback.items.get(planned["id"])
        if continuation.state_hash(value)!=planned.get("afterStateHash"): raise ContinuationRemoteError("CONTINUATION_READBACK_STATE_MISMATCH")
        return {"ok":True,"applied":True,"authorityBranch":self.authority_branch,"beforeSha":observed.head_sha,"afterSha":commit,"id":planned["id"],"action":planned["action"],"planHash":planned["planHash"],"stateHash":planned["afterStateHash"]}
