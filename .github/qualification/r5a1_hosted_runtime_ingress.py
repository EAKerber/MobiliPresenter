from __future__ import annotations

import json
import os
from pathlib import Path

from tools import hosted_agent_cycle as hosted


OUT = Path('/tmp/r5a1-hosted-qualification')
SURFACE = 'github-connector-tools'
CAPABILITIES = [
    'github.git-data.write',
    'github.expected-head-write',
    'github.mutation-readback',
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    command = {
        'schemaVersion': hosted.COMMAND_SCHEMA_V04,
        'requestId': 'r5a1-hosted-qualification',
        'action': 'begin',
        'actor': {
            'role': 'manager-gitops',
            'workerId': 'manager-gitops-a',
            'sessionId': 'session-r5a1-hosted-qualification',
        },
        'declaredIntent': 'inspect-and-plan',
        'machineScope': 'live',
        'workRef': None,
        'runtimeEnvironment': {
            'toolSurfaces': [SURFACE],
            'inventoryComplete': True,
        },
        'evidenceCommentIds': [],
        'semanticAuthority': False,
        'authorizesMutation': False,
    }
    meta = {'issueNumber': 1, 'commentId': 1}
    result = hosted.begin_from_envelope(
        command,
        meta,
        context_path=OUT / 'context.json',
        manifest_path=OUT / 'manifest.json',
    )
    context = json.loads((OUT / 'context.json').read_text(encoding='utf-8'))
    manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))

    if result.get('status') != 'READY' or context.get('status') != 'READY':
        raise SystemExit('R5A1_QUALIFICATION_BEGIN_NOT_READY')
    if context.get('semanticAuthority') is not False or context.get('authorizesMutation') is not False:
        raise SystemExit('R5A1_QUALIFICATION_CONTEXT_AUTHORITY_LEAK')
    if manifest.get('semanticAuthority') is not False or manifest.get('authorizesMutation') is not False:
        raise SystemExit('R5A1_QUALIFICATION_MANIFEST_AUTHORITY_LEAK')

    runtime = context['runtimeCapabilities']
    observed = {}
    for capability_id in CAPABILITIES:
        item = runtime['capabilities'][capability_id]
        if item['status'] != 'PASS':
            raise SystemExit(f'R5A1_QUALIFICATION_CAPABILITY_NOT_PASS:{capability_id}:{item["status"]}')
        if 'github-connector' not in item['satisfiedProviders']:
            raise SystemExit(f'R5A1_QUALIFICATION_CONNECTOR_NOT_SATISFIED:{capability_id}')
        observed[capability_id] = {
            'status': item['status'],
            'satisfiedProviders': item['satisfiedProviders'],
        }

    if 'runtimeEnvironment' in context:
        raise SystemExit('R5A1_QUALIFICATION_TRANSPORT_FIELD_LEAKED_INTO_CONTEXT')

    summary = {
        'schemaVersion': 'R5A1HostedRuntimeIngressQualification 0.1',
        'sourceSha': os.environ.get('GITHUB_SHA'),
        'runId': os.environ.get('GITHUB_RUN_ID'),
        'inputKind': 'host-input-fixture',
        'inputToolSurfaces': [SURFACE],
        'inventoryComplete': True,
        'beginStatus': result['status'],
        'cycleId': result['cycleId'],
        'cycleInstanceId': result['cycleInstanceId'],
        'runtimeCapabilityInspectionHash': runtime['inspectionHash'],
        'capabilities': observed,
        'transportFieldLeakedIntoContext': False,
        'semanticAuthority': False,
        'authorizesMutation': False,
        'provesWorkModeDiscovery': False,
        'status': 'PASS',
    }
    (OUT / 'summary.json').write_text(
        json.dumps(summary, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
