# Runtime Capability & Provider Discovery 0.1

Status: **M9-0A architecture/inspection contract**.

## Problema

Um executable concreto não é uma capability lógica. Em particular:

```text
gh ausente != GitHub indisponível
```

O runtime pode oferecer `gh-api`, um GitHub connector, Git local ou artifacts validados. A ausência de um provider não autoriza concluir que a capability lógica inteira está ausente.

## Regra permanente

Antes de classificar uma capability como indisponível:

1. identifique a capability lógica exigida;
2. identifique seus invariantes;
3. observe os providers suportados relevantes;
4. valide se algum provider satisfaz integralmente os invariantes;
5. somente então classifique `PASS`, `UNKNOWN` ou `FAIL`.

Um provider alternativo nunca pode enfraquecer:

```text
observe -> plan -> validate -> apply -> readback
```

nem ampliar autoridade, scope ou permissões.

## RuntimeCapabilityInspection 0.1

`tools/runtime_capabilities.py` produz somente uma `Inspection` read-only.

Ela:

- não é authority;
- não seleciona provider para mutation;
- não executa discovery externo;
- não executa transporte;
- não autoriza mutation;
- não persiste estado;
- é determinística para a mesma observação de providers.

`authorizesMutation` deve permanecer `false`.

## RuntimeProviderObservations 0.1

O runtime/orquestrador pode materializar uma observação explícita:

```json
{
  "schemaVersion": "RuntimeProviderObservations 0.1",
  "providers": {
    "github-connector": {
      "status": "PASS",
      "features": [
        "repository-read",
        "ref-read",
        "blob-create",
        "tree-create",
        "commit-create-with-parent",
        "non-force-ref-update",
        "content-readback"
      ],
      "reason": null
    }
  }
}
```

`PASS` significa que as features foram efetivamente observadas. `UNKNOWN` e `FAIL` não podem declarar features verificadas.

Providers não observados permanecem `UNKNOWN`.

## Git direct mutation

Para `git.direct-mutation`, a existência de `update_file` ou de qualquer Contents API isoladamente não prova equivalência.

O path deve demonstrar, no mínimo:

```text
ref-read
blob-create
tree-create
commit-create-with-parent
non-force-ref-update
content-readback
```

A intenção é preservar o vínculo entre o head observado, o commit candidato e o readback.

## Coordination

Coordination possui requisito adicional de tempo remoto confiável para TTL/expiry.

Portanto é válido ter simultaneamente:

```text
git.direct-mutation = PASS
coordination.mutate = FAIL ou UNKNOWN
```

quando o connector Git-data está disponível mas `trusted-remote-time` não foi provado.

Não substituir tempo remoto por relógio local para forçar `PASS`.

## Uso

Somente observação local:

```bash
python3 tools/runtime_capabilities.py inspect --json
```

Com provider externo observado pelo runtime:

```bash
python3 tools/runtime_capabilities.py inspect \
  --providers /tmp/runtime-providers.json \
  --json
```

O mesmo bundle pode ser passado ao `doctor`:

```bash
python3 tools/agent.py doctor \
  --runtime-providers /tmp/runtime-providers.json \
  --json
```

## Limite de M9-0A

Este recorte não:

- troca `GhApiTransport`;
- faz ProjectMachine selecionar connector;
- muda Coordination ou Work writers;
- cria provider routing;
- cria nova authority;
- torna connector obrigatório;
- altera Scheduler/Maintenance;
- cria fallback mutável automático.

Consumer adoption pertence ao próximo recorte.
