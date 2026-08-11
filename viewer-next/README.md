# Viewer Next

Renderer determinístico em desenvolvimento para o MobiliPresenter.

Princípios:
- câmera fixa é requisito de produto;
- Scene Core é autoridade de geometria e estado;
- Three.js é backend substituível do renderer, não dependência do Scene Core;
- render sob demanda, sem câmera orbital;
- materiais e luz não podem mutar geometria;
- LLM/image generation não é autoridade de runtime.

O plano vigente está em `docs/plans/fixed-view-renderer-0.1.md`.
