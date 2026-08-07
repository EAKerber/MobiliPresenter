# Recuperação das entregas ZIP

**Status:** inventário factual.  
**Data da recuperação:** 2026-08-06.

## Linha de base canônica recuperada

| Campo | Valor |
|---|---|
| Artefato | `balcao-360-v7-i5.zip` |
| Tamanho | 30.001.308 bytes |
| SHA-256 | `5ba5672ebc4625b99892dc80b1ae859ed9c406eccf5ba284d523d04129948d5a` |
| Arquivos | 2.904 |
| Tamanho expandido | 32.666.164 bytes |

O ZIP contém o código TypeScript, ferramentas Python, testes, schemas, documentação, fontes de módulos, pacotes compilados, assemblies, relatórios e frames raster da V7.0-I5.

O repositório publicado antes desta recuperação continha apenas o preview leve para Netlify e seu mecanismo determinístico de reconstrução. Portanto, a versão hospedada era verificável, mas não constituía a fonte técnica completa.

## Inventário das principais entregas

| Fase | Artefatos | Papel |
|---|---|---|
| Calibração | `balcao-360-calibrador-v1.zip` a `v6.zip` | evolução da câmera, geometria, slots, oclusão, acabamento e compositor |
| MVP | `balcao-360-mvp.zip` a `v5.zip` | experimentação visual e estabilidade por slot |
| Arquitetura V7 | `balcao-360-v7-i1.zip` a `i5.zip` | contratos, compilação, negociação, montagem e fabricação |
| Fixtures angulares | `modulo teste.zip`, `modulo teste 2.zip`, `modulo teste 3.zip` | validação de yaw e pitch |
| Composição real | `modulo_composto_gaveteiro.zip`, `modulo_composto_balcao.zip`, `modulo_composto_completo.zip` | módulos separados e ground truth |
| Fontes de captura | `eixo x.zip`, `eixo y.zip`, `eixo z.zip`, `eixo z v2.zip`, `eixo z v3.zip` | sequências raster de origem |

## Hashes principais

- V7.0-I1: `abc7bfd1a50d828bf9f29748f7125fc14a865be310ecee8f6f6221748c725966`;
- V7.0-I2: `14f5c06fe62fec84ee500c7b563fb0a1376dd40581289fffd14fe2cc0c274478`;
- V7.0-I3: `cef184f2c6088c2c4899094ce9096da3a00ba08cd5f18c4c7c09417e22162bee`;
- V7.0-I4: `1b1aca6616e15fda29edfa9399be352ab5ec7be471bd71d09815b78793807853`;
- V7.0-I4.1: `84e3ab0065f9968845f1ad62ee8dda2f3e7c786286c7726edbfeaf4daddd98cb`;
- V7.0-I4.2: `9a2b9d6223c0a37947419663e167dabb59d29bed7f1a489e9e10745d0e84cfec`;
- V7.0-I5: `5ba5672ebc4625b99892dc80b1ae859ed9c406eccf5ba284d523d04129948d5a`.

## O que foi formalizado

- evolução e finalidade de cada incremento relevante;
- capacidades incorporadas e correções importantes;
- identidade criptográfica da linha de base atual;
- distinção entre preview publicado, fonte técnica e artefatos históricos;
- limites conhecidos e pontos sujeitos à reavaliação.

## O que ainda não foi promovido para a raiz do Git

Os 2.904 arquivos da fonte técnica completa não foram despejados automaticamente na `main`. Durante a fase de planejamento será decidido:

1. quais arquivos são fonte autoritativa;
2. quais são derivados e devem ser regenerados;
3. como versionar milhares de frames sem degradar o repositório;
4. se os assets usarão Git LFS, releases, armazenamento externo ou fixtures reduzidas;
5. qual estrutura de diretórios corresponde ao novo escopo.

Até essa decisão, o ZIP identificado acima permanece a base forense, e esta documentação é a base semântica para a reavaliação.
