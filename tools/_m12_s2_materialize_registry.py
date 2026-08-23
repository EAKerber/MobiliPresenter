#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path

PATH = Path("ops/semantics/registry.json")
BASE_BLOB = "f1da396241eb7a21b08ab2162cc04455cd772336"
FINAL_BLOB = "9f5935691358909da2b6faf9ed5bb22558176deb"

CAPABILITY_ANCHOR = '    "remote.canonical.execute": {"owner":"operations-core","description":"Execute a closed remote canonical command through repository planners, existing domain writers or the governed direct-Git path, then emit aggregate readback evidence.","availabilityClass":"contextual","facets":{"roles":["manager-gitops"],"intentClasses":["governed-mutation"],"lifecyclePhases":["execution","validation"],"operations":["authority-mutation","readback"],"objects":["branch","coordination","work-item"],"riskClasses":["authority-write","git-write"]},"requiredAuthorities":[],"requiredScopes":[],"preconditions":["exact-expected-heads","underlying-route-authorized","validated-remote-canonical-command"],"providerRequirements":{},"toolSurfaces":["github-actions-workflows","python-module-cli"],"fallbackPolicy":"forbidden"},\n'
CAPABILITY_LINE = '    "remote.git.role-scoped-mutate": {"owner":"operations-core","description":"Execute a closed remote direct-Git file mutation confined by the hosted actor role to canonical role-owned branches and paths, with exact head preconditions, canonical Git planning, non-force apply, and aggregate readback.","availabilityClass":"contextual","facets":{"roles":["ui-ux"],"intentClasses":["governed-mutation"],"lifecyclePhases":["execution","validation"],"operations":["authority-mutation","readback"],"objects":["branch","repository"],"riskClasses":["git-write"]},"requiredAuthorities":[],"requiredScopes":["repository:write"],"preconditions":["exact-expected-heads","role-owned-branch","role-owned-path","validated-remote-canonical-command"],"providerRequirements":{},"toolSurfaces":["github-actions-workflows","python-module-cli"],"fallbackPolicy":"forbidden"},\n'
WORKFLOW_OLD = '{"targetKind":"workflow","target":".github/workflows/remote-canonical-execution.yml","capabilities":["remote.canonical.execute"]}'
WORKFLOW_NEW = '{"targetKind":"workflow","target":".github/workflows/remote-canonical-execution.yml","capabilities":["remote.canonical.execute","remote.git.role-scoped-mutate"]}'
CLI_OLD = '{"targetKind":"component","target":"remote-canonical-issue-cli","capabilities":["remote.canonical.execute"]}'
CLI_NEW = '{"targetKind":"component","target":"remote-canonical-issue-cli","capabilities":["remote.canonical.execute","remote.git.role-scoped-mutate"]}'


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def replace_once(text: str, old: str, new: str, code: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{code}:{text.count(old)}")
    return text.replace(old, new, 1)


raw = PATH.read_bytes()
current = blob_sha(raw)
if current == FINAL_BLOB:
    print(f"REGISTRY_ALREADY_MATERIALIZED:{FINAL_BLOB}")
    raise SystemExit(0)
if current != BASE_BLOB:
    raise SystemExit(f"REGISTRY_BASE_DRIFT:{current}")

text = raw.decode("utf-8")
text = replace_once(text, CAPABILITY_ANCHOR, CAPABILITY_ANCHOR + CAPABILITY_LINE, "CAPABILITY_ANCHOR_INVALID")
text = replace_once(text, WORKFLOW_OLD, WORKFLOW_NEW, "WORKFLOW_BINDING_INVALID")
text = replace_once(text, CLI_OLD, CLI_NEW, "CLI_BINDING_INVALID")
final = text.encode("utf-8")
actual = blob_sha(final)
if actual != FINAL_BLOB:
    raise SystemExit(f"REGISTRY_FINAL_HASH_MISMATCH:{actual}")
PATH.write_bytes(final)
print(f"REGISTRY_MATERIALIZED:{FINAL_BLOB}")
