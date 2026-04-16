# Arquitetura Proposta

## Contexto

O arquivo `project_instructions.txt` da raiz estava vazio no momento da analise. Por isso, os requisitos foram levantados a partir do material em `Code/project/starter/`, especialmente `README.md`, `src/` e o diagrama de workflow.

## Requisitos levantados

### Requisitos funcionais

O sistema deve:
- classificar a intencao do usuario em `qa`, `summarization`, `calculation` ou `unknown`;
- rotear a execucao para o agente adequado;
- consultar documentos por busca e leitura detalhada;
- executar calculos com ferramenta dedicada;
- retornar respostas estruturadas;
- manter memoria resumida da conversa;
- persistir sessao e contexto de documentos ativos;
- expor uma interface de linha de comando simples.

### Requisitos nao funcionais

O projeto deve:
- seguir boas praticas de Python com pacote em `src/`;
- separar configuracao, dominio, workflow e I/O;
- reduzir acoplamento entre LLM, grafo e ferramentas;
- permitir testes unitarios dos modulos centrais;
- centralizar configuracao por ambiente;
- registrar uso de ferramentas para auditoria e debug;
- preparar o codigo para futura troca do retriever simulado por um real.

## Arquitetura recomendada

### 1. Camada de entrada

`main.py`

Responsabilidades:
- carregar variaveis de ambiente;
- instanciar configuracao e assistente;
- iniciar sessao;
- oferecer loop CLI para comandos simples.

### 2. Camada de aplicacao

`assistant.py`

Responsabilidades:
- orquestrar sessao atual;
- preparar `config` do LangGraph com `thread_id`, `llm` e `tools`;
- invocar o grafo;
- traduzir o estado final para um payload amigavel;
- persistir a sessao em disco.

### 3. Camada de workflow

`graph.py`

Responsabilidades:
- definir `AgentState`;
- implementar os nodes do grafo;
- encapsular roteamento condicional;
- compilar o workflow com checkpointer.

Fluxo esperado:

```text
classify_intent
  -> qa_agent
  -> summarization_agent
  -> calculation_agent
  -> update_memory
  -> END
```

### 4. Camada de dominio e contratos

`schemas.py`

Responsabilidades:
- modelos Pydantic para documentos, respostas, memoria e sessao;
- contratos fortemente tipados entre grafo, ferramentas e camada de aplicacao.

### 5. Camada de prompts

`prompts.py`

Responsabilidades:
- centralizar prompts de classificacao, QA, resumo, calculo e memoria;
- evitar strings espalhadas pelo codigo.

### 6. Camada de retrieval

`retrieval.py`

Responsabilidades:
- representar documentos;
- abstrair busca por palavra-chave, tipo e faixa de valor;
- permitir substituicao futura por banco vetorial ou busca hibrida.

### 7. Camada de ferramentas

`tools.py`

Responsabilidades:
- expor tools do LangChain;
- validar entradas;
- registrar uso de ferramentas;
- encapsular calculadora, busca, leitura e estatisticas.

### 8. Configuracao

`settings.py`

Responsabilidades:
- ler e validar ambiente;
- concentrar nome de modelo, temperatura, path de sessoes e logs;
- reduzir espalhamento de `os.getenv`.

## Decisoes de engenharia

### Uso de `src/` layout

Evita import acidental da raiz do projeto e aproxima o repositorio de um pacote Python real.

### `pyproject.toml` como base

Melhora padronizacao do projeto e deixa o caminho aberto para packaging, lint, testes e ferramentas de qualidade.

### Separacao de estado e persistencia

O LangGraph guarda estado conversacional via checkpointer; a aplicacao tambem persiste metadados de sessao em `sessions/`. Isso oferece:
- memoria de execucao do grafo;
- rastreabilidade da sessao fora do processo;
- facilidade de depuracao.

### Ferramenta de calculo isolada

Mesmo em ambiente de aprendizado, calculo deve passar por validacao de expressao e logging. Isso reduz risco e deixa comportamento reproduzivel.

### Retrieval como abstracao

O starter usa um retriever simulado. A estrutura proposta preserva a interface e permite evoluir para:
- vetor store;
- busca semantica;
- parsing de PDF;
- indexacao incremental.

## Arquivos reaproveitados do starter

Itens copiados diretamente:
- `Code/project/starter/docs/langgraph_agent_architecture.png` -> `docs/assets/langgraph_agent_architecture.png`

Itens reaproveitados conceitualmente, mas reorganizados:
- `main.py`
- `src/assistant.py`
- `src/agent.py`
- `src/prompts.py`
- `src/retrieval.py`
- `src/schemas.py`
- `src/tools.py`
- `requirements.txt`

## Estrutura final proposta

```text
src/report_building_agent/
├── __init__.py
├── assistant.py
├── graph.py
├── prompts.py
├── retrieval.py
├── schemas.py
├── settings.py
└── tools.py
```

## TODOs de implementacao

Pendencias esperadas para a proxima etapa:
- validar e ajustar a compatibilidade exata das APIs de `langchain` e `langgraph` instaladas no ambiente;
- endurecer a calculadora segura com testes de casos maliciosos e expressoes invalidas;
- expandir o retriever simulado ou trocar por uma camada real de ingestao de documentos;
- adicionar testes unitarios para retrieval, tools e roteamento;
- adicionar testes de integracao para o fluxo completo do grafo;
- revisar UX da CLI e tratamento de erros de ambiente.

## Dependencias recomendadas

Baseadas no starter e na estrutura proposta:
- `langchain`
- `langgraph`
- `langchain-openai`
- `langchain-core`
- `pydantic`
- `python-dotenv`
- `openai`
- `print-color`

Para desenvolvimento, recomendo adicionar depois:
- `pytest`
- `pytest-cov`
- `ruff`
- `mypy`

## Riscos e pontos de atencao

- O starter mistura detalhes de workshop com codigo de aplicacao; por isso a reorganizacao foi necessaria.
- O endpoint `https://openai.vocareum.com/v1` aparece no starter e pode nao ser o endpoint final do seu ambiente.
- Ha pequenos problemas de implementacao no starter que nao devem ser copiados literalmente, como inconsistencias de nomes de campos e imports absolutos.
