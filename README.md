# Report Building Agent

Estrutura inicial de um assistente de documentos baseado em LangChain + LangGraph, organizada para evoluir com boas praticas de engenharia em Python.

O desafio de referencia descreve um assistente capaz de:
- responder perguntas sobre documentos;
- resumir documentos;
- realizar calculos com dados extraidos dos documentos;
- manter memoria de conversa e estado por sessao.

Este repositório foi preparado primeiro com foco em arquitetura e estrutura de projeto. A implementacao pode ser concluida depois, com o ambiente de desenvolvimento ja configurado.

## Arquitetura

A documentacao principal esta em [docs/architecture.md](/home/fabiolima/Desktop/Report-Building-Agent/docs/architecture.md).

O diagrama de referencia do starter foi preservado em [docs/assets/langgraph_agent_architecture.png](/home/fabiolima/Desktop/Report-Building-Agent/docs/assets/langgraph_agent_architecture.png).

## Estrutura

```text
.
├── docs/
│   ├── architecture.md
│   └── assets/
├── logs/
├── sessions/
├── src/
│   └── report_building_agent/
│       ├── __init__.py
│       ├── assistant.py
│       ├── graph.py
│       ├── prompts.py
│       ├── retrieval.py
│       ├── schemas.py
│       ├── settings.py
│       └── tools.py
├── tests/
├── main.py
├── pyproject.toml
└── requirements.txt
```

## Decisoes

- `src/` layout para evitar imports acidentais a partir da raiz.
- `pyproject.toml` como fonte principal de configuracao do projeto.
- pacote unico `report_building_agent` com separacao por responsabilidade.
- `docs/architecture.md` para registrar requisitos e decisoes antes da implementacao completa.
- `sessions/` e `logs/` mantidos fora do pacote por serem artefatos de runtime.

## Proximo passo

Depois que o ambiente for criado, o fluxo natural e:

1. instalar dependencias;
2. implementar os TODOs do workflow e das tools;
3. adicionar testes unitarios e de integracao;
4. validar o fluxo interativo com `.env`.
