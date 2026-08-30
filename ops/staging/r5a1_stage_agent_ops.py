from pathlib import Path

source_path = Path('.github/workflows/agent-ops.yml')
target_path = Path('ops/staging/r5a1-agent-ops.yml')
source = source_path.read_text(encoding='utf-8')
old = """      - name: Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Toolbox unit tests
"""
new = """      - name: Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: R5A1 Hosted runtime ingress qualification
        if: github.ref_name == 'work/operations/m12-at3d-r5a1-hosted-qualification-20260830'
        env:
          GH_TOKEN: ${{ github.token }}
        run: PYTHONPATH=. python .github/qualification/r5a1_hosted_runtime_ingress.py
      - name: Upload R5A1 Hosted runtime ingress qualification
        if: github.ref_name == 'work/operations/m12-at3d-r5a1-hosted-qualification-20260830' && always()
        uses: actions/upload-artifact@v4
        with:
          name: r5a1-hosted-runtime-ingress-qualification
          path: /tmp/r5a1-hosted-qualification
          if-no-files-found: error
      - name: Toolbox unit tests
"""
if source.count(old) != 1:
    raise SystemExit('agent-ops qualification anchor mismatch')
target_path.write_text(source.replace(old, new, 1), encoding='utf-8')
