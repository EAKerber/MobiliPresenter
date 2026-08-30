from pathlib import Path

source_path = Path('.github/workflows/hosted-agent-cycle.yml')
target_path = Path('ops/staging/r5a1-hosted-agent-cycle.yml')
source = source_path.read_text(encoding='utf-8')
old = "      (startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_1') ||\n       startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_2') ||\n       startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_3'))"
new = "      (startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_1') ||\n       startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_2') ||\n       startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_3') ||\n       startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_4'))"
if source.count(old) != 1:
    raise SystemExit('hosted workflow marker anchor mismatch')
target_path.parent.mkdir(parents=True, exist_ok=True)
target_path.write_text(source.replace(old, new, 1), encoding='utf-8')
