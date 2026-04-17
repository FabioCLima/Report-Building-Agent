# Report Building Agent

[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://www.python.org/)
[![Pytest](https://img.shields.io/badge/Pytest-passing-brightgreen)](https://docs.pytest.org/)
[![LangChain](https://img.shields.io/badge/LangChain-enabled-1f6feb)](https://python.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-enabled-6f42c1)](https://langchain-ai.github.io/langgraph/)

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

## Como funciona (estado, memoria e structured outputs)

- **Structured outputs (Pydantic):** o classificador de intenção retorna `UserIntent` e o nó de QA retorna `AnswerResponse`. Ambos são validados pelo Pydantic em `src/report_building_agent/schemas.py`.
- **Estado do grafo:** o LangGraph mantém um `AgentState` com `messages`, `intent`, `tools_used`, `active_documents`, etc. (`src/report_building_agent/graph.py`).
- **Memória:** após cada resposta, o nó `update_memory` gera um resumo e extrai IDs de documentos referenciados, atualizando `conversation_summary` e `active_documents`.
- **Persistência de sessão:** metadados da sessão são salvos em `sessions/<session_id>.json` (histórico e `document_context`) por `DocumentAssistant` em `src/report_building_agent/assistant.py`.
- **Auditoria de ferramentas:** cada chamada de tool é registrada como JSON em `logs/` por `ToolLogger` (`src/report_building_agent/tools.py`).

## Decisoes

- `src/` layout para evitar imports acidentais a partir da raiz.
- `pyproject.toml` como fonte principal de configuracao do projeto.
- pacote unico `report_building_agent` com separacao por responsabilidade.
- `docs/architecture.md` para registrar requisitos e decisoes antes da implementacao completa.
- `sessions/` e `logs/` mantidos fora do pacote por serem artefatos de runtime.

## Proximo passo

### Passo a passo (pip)

1. Criar e ativar venv:
```bash
python -m venv .venv
source .venv/bin/activate
```
2. Instalar dependencias:
```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```
3. Configurar variaveis:
```bash
cp .env.example .env
```
Edite `.env` e preencha `OPENAI_API_KEY` (e opcionalmente `OPENAI_BASE_URL`, `MODEL_NAME`, `TEMPERATURE`).

4. Executar:
```bash
python main.py
```
Opcional (se instalou com `-e .`): `python -m report_building_agent`

### Passo a passo (uv)

1. Sincronizar ambiente (usa `pyproject.toml` + `uv.lock`):
```bash
uv sync --dev
```
2. Executar:
```bash
uv run python main.py
```

### Como testar

```bash
python -m pytest -q
```

## Conversas de exemplo

1) **QA com fontes (IDs)**
```text
User: Which invoices mention Acme?
Assistant: ... (from docs)
INTENT: qa (conf=0.9)
SOURCES: INV-001, ...
TOOLS USED: document_search, ...
```

2) **Summarization**
```text
User: Summarize CON-001 in 5 bullets
Assistant: Summary for CON-001: ...
INTENT: summarization (conf=0.9)
TOOLS USED: document_reader, ...
```

3) **Calculation (sempre usando calculator tool)**
```text
User: Calculate 2 + 3 using invoice data
Assistant: Computed from INV-002: 5
INTENT: calculation (conf=0.9)
TOOLS USED: document_reader, calculator
```
