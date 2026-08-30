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


def _write(name: str, value: object) -> None:
    (OUT / name).write_text(
        json.dumps(value, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )


def _capability_summary(context: dict) -> dict:
    runtime = context['runtimeCapabilities']
    observed = {}
    for capability_id in CAPABILITIES:
        item = runtime['capabilities'][capability_id]
        observed[capability_id] = {
            'status': item['status'],
            'satisfiedProviders': item['satisfiedProviders'],
            'reasonCode': item['reasonCode'],
        }
    return observed


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
    _write('command.json', command)

    raw_args = [
        'begin',
        '--role', command['actor']['role'],
        '--intent', command['declaredIntent'],
        '--machine-scope', 'live',
        '--runtime-tool-surface', SURFACE,
        '--runtime-tool-surfaces-complete',
        '--json',
    ]
    raw_rc, raw_context = hosted._run_agent(raw_args)
    _write('raw-context.json', raw_context)
    raw_summary = {
        'returnCode': raw_rc,
        'status': raw_context.get('status'),
        'blockingUnknowns': raw_context.get('blockingUnknowns'),
        'capabilities': _capability_summary(raw_context) if 'runtimeCapabilities' in raw_context else None,
    }
    _write('raw-summary.json', raw_summary)
    print(json.dumps({'rawBegin': raw_summary}, sort_keys=True))

    for capability_id, item in (raw_summary['capabilities'] or {}).items():
        if item['status'] != 'PASS' or 'github-connector' not in item['satisfiedProviders']:
            raise SystemExit(
                f'R5A1_QUALIFICATION_INGRESS_NOT_MATERIALIZED:{capability_id}:{item["status"]}'
            )

    meta = {'issueNumber': 1, 'commentId': 1}
    try:
        result = hosted.begin_from_envelope(
            command,
            meta,
            context_path=OUT / 'context.json',
            manifest_path=OUT / 'manifest.json',
        )
    except hosted.HostedAgentCycleError as exc:
        failure = {
            'code': exc.code,
            'detail': exc.detail,
            'failureCore': exc.failure_core,
            'rawBegin': raw_summary,
        }
        _write('hosted-failure.json', failure)
        raise

    context = json.loads((OUT / 'context.json').read_text(encoding='utf-8'))
    manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))

    if result.get('status') != 'READY' or context.get('status') != 'READY':
        raise SystemExit('R5A1_QUALIFICATION_BEGIN_NOT_READY')
    if context.get('semanticAuthority') is not False or context.get('authorizesMutation') is not False:
        raise SystemExit('R5A1_QUALIFICATION_CONTEXT_AUTHORITY_LEAK')
    if manifest.get('semanticAuthority') is not False or manifest.get('authorizesMutation') is not False:
        raise SystemExit('R5A1_QUALIFICATION_MANIFEST_AUTHORITY_LEAK')
    if 'runtimeEnvironment' in context:
        raise SystemExit('R5A1_QUALIFICATION_TRANSPORT_FIELD_LEAKED_INTO_CONTEXT')

    summary = {
        'schemaVersion': 'R5A1HostedRuntimeIngressQualification 0.1',
        'sourceSha': os.environ.get('GITHUB_SHA'),
        'runId': os.environ.get('GITHUB_RUN_ID'),
        'inputKind': 'host-input-fixture',
        'inputToolSurfaces': [SURFACE],
        'inventoryComplete': True,
        'rawBegin': raw_summary,
        'hostedBeginStatus': result['status'],
        'cycleId': result['cycleId'],
        'cycleInstanceId': result['cycleInstanceId'],
        'runtimeCapabilityInspectionHash': context['runtimeCapabilities']['inspectionHash'],
        'transportFieldLeakedIntoContext': False,
        'semanticAuthority': False,
        'authorizesMutation': False,
        'provesWorkModeDiscovery': False,
        'status': 'PASS',
    }
    _write('summary.json', summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
