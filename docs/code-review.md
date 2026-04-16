# Report Building Agent — Code Review Documentation

Prepared on 2026-04-16. Aligns the current implementation under `src/report_building_agent/`
with the specification in `project_instructions.txt` and the architecture proposal in
`docs/architecture.md`, and records gaps the reviewer should question.

## 1. Scope and traceability vs. project_instructions.txt

| Task (instructions)                                   | Code location                                      | Status |
| ----------------------------------------------------- | -------------------------------------------------- | ------ |
| 1.1 `AnswerResponse` schema                           | `schemas.py:18`                                    | Done   |
| 1.2 `UserIntent` schema                               | `schemas.py:55`                                    | Done   |
| 2.1 `AgentState` properties                           | `graph.py:29`                                      | Done   |
| 2.2 `classify_intent` node with structured output     | `graph.py:71`                                      | Done   |
| 2.3 `qa_agent`, `summarization_agent`, `calculation_agent` | `graph.py:115-128` via `_run_specialist_node` | Done   |
| 2.4 `update_memory` with structured output            | `graph.py:131`                                     | Done   |
| 2.5 `create_workflow` with conditional edges          | `graph.py:153`                                     | Done   |
| 2.6 `operator.add` on `actions_taken` + `InMemorySaver` checkpointer | `graph.py:40`, `graph.py:175`       | Done   |
| 2.6 `thread_id`, `llm`, `tools` in `config.configurable` | `assistant.py:53-59`                            | Done   |
| 3.1 `get_chat_prompt_template` by intent              | `prompts.py:70`                                    | Done   |
| 3.2 `CALCULATION_SYSTEM_PROMPT`                       | `prompts.py:47`                                    | Done   |
| 4.1 `create_calculator_tool` (safe + logged)          | `tools.py:72`                                      | Done   |
| Auto-generated `logs/` with per-session tool history  | `tools.py:ToolLogger` + `assistant.py:33,46`       | Done   |
| Auto-generated `sessions/` with per-session state     | `assistant.py:_save_session`                       | Done   |

The implementation meets the functional rubric of the starter. Deviations are mostly structural
(e.g. package renamed to `report_building_agent`, `agent.py` split into `graph.py`), which are
allowed and documented in `docs/architecture.md`.

## 2. Architecture and layering

Implemented layering matches the proposal in `docs/architecture.md`:

- Entry: `main.py` → `assistant.run_cli`.
- Application: `assistant.DocumentAssistant` owns the LLM, retriever, tools, workflow, and
  session persistence.
- Workflow: `graph.py` exposes `AgentState`, nodes, routing, and `create_workflow()`.
- Domain: `schemas.py` — Pydantic models for intents, responses, session, and graph result.
- Prompts: `prompts.py` — centralized system/classification/memory prompts.
- Retrieval: `retrieval.py` — in-memory `SimulatedRetriever` with keyword, type, and amount-based
  queries.
- Tools: `tools.py` — calculator, document_search, document_reader, document_statistics, plus
  `ToolLogger`.
- Config: `settings.py` via `pydantic-settings` with `.env` loading.

Routing graph (`graph.py:153`):

```
classify_intent
  ├── qa_agent ─┐
  ├── summarization_agent ─┤
  └── calculation_agent ───┴── update_memory ── END
```

Specialist nodes run inside a prebuilt ReAct agent (`create_react_agent`) with tool-bound LLM and
`response_format=<ResponseSchema>` (`graph.py:invoke_react_agent`). This is the integration point
worth a second look in review (see §5).

## 3. Logging

### 3.1 What exists

- `tools.ToolLogger` (`tools.py:13`) persists tool calls as JSON. When a session starts,
  `assistant.start_session` calls `tool_logger.set_session_id`, which switches the file to
  `logs/session_<session_id>.json` (`tools.py:23-31`). Filenames before a session starts fall
  back to `tool_usage_<timestamp>.json` — these files appear in `logs/` and are artifacts from
  runs where logging was hit before session binding.
- Sessions are persisted via `assistant._save_session` to `sessions/<session_id>.json`.

### 3.2 Does the project use loguru?

**No.** The codebase does not depend on or import `loguru`. The only logging in place is the
custom JSON file-writer `ToolLogger`, and nothing else (LLM calls, graph nodes, CLI lifecycle,
errors) is logged — exceptions in `process_message` are swallowed into the `error` field of
`GraphResult` (`assistant.py:90-100`) with no stderr trace.

### 3.3 Recommendation

Introduce either `loguru` or `logging` for runtime events and keep `ToolLogger` as the audit
trail. Concrete asks for the review:

- Add `loguru` to `pyproject.toml` dependencies.
- Configure a single sink in `settings.py` or a dedicated `logging.py`, pointing to
  `logs/app.log` with rotation, plus stderr at `INFO`.
- Emit structured logs in: `classify_intent` (intent + confidence), each specialist node
  (tools invoked, latency), `update_memory` (summary length, doc IDs), and the CLI loop
  (session start, user input length, errors). Avoid logging raw document content.
- On exceptions in `process_message`, log with traceback before returning the error payload.
- Rewrite `ToolLogger.log_tool_use` to append instead of rewriting the whole JSON file on every
  call (current `json.dump` of the full list on each tool use is O(n²) over a session and risks
  partial writes).

## 4. Guardrails against hallucination

### 4.1 Guardrails present

- **Structured output everywhere.** `classify_intent` uses `with_structured_output(UserIntent)`,
  specialists pass `response_format=<Schema>` to the ReAct agent, and `update_memory` uses
  `with_structured_output(UpdateMemoryResponse)`. Pydantic enforces types, `confidence ∈ [0,1]`,
  and `intent_type ∈ {qa, summarization, calculation, unknown}`.
- **Prompt-level grounding.**
  - `QA_SYSTEM_PROMPT` — "Always search for relevant documents before answering" and "If the
    answer is not present in the available documents, say that clearly" (`prompts.py:31`).
  - `SUMMARIZATION_SYSTEM_PROMPT` — "Search and read the relevant documents first"
    (`prompts.py:39`).
  - `CALCULATION_SYSTEM_PROMPT` — forces tool use on every calculation (`prompts.py:47`).
- **Safe calculator.** `_safe_eval_arithmetic` (`tools.py:46`) regex-whitelists characters,
  AST-walks the expression, rejects `Call`, `Attribute`, `Name`, power, and unknown operators.
  Covered by `tests/test_safe_eval.py`.
- **Low temperature.** `Settings.temperature = 0.1` (`settings.py:11`) biases toward
  deterministic outputs.
- **Memory shape.** `UpdateMemoryResponse` forces summaries + `document_ids`, making memory
  traceable rather than free text.
- **Deterministic retrieval.** The retriever is a fully in-memory, keyword/amount-based lookup
  with no generative component, so the ground truth the agent sees is fixed and inspectable.

### 4.2 Gaps worth flagging in review

1. **No verification that sources cited actually exist.** `AnswerResponse.sources` is a free list
   of strings. Nothing checks that each ID appears in `retriever.documents` or was retrieved this
   turn. Add a post-node validator that intersects `sources` with `tools_used` outputs and either
   drops or flags phantom IDs.
2. **Retrieval is not enforced at the code level.** The QA/summarization system prompts ask the
   model to search "first", but nothing prevents the ReAct agent from answering without calling a
   tool. Options: require at least one `document_search`/`document_reader` tool call before
   accepting the structured response, or add a retrieval pre-step node that seeds the context.
3. **No abstention path.** `UserIntent` admits `"unknown"`, but the router falls back to
   `qa_agent` on unknown intent (`graph.py:80-88`). For low-confidence classifications, the safer
   behavior is a clarification message rather than silently routing.
4. **No confidence floor on the answer.** `AnswerResponse.confidence` is captured but never used
   to gate output. Consider returning a "not enough evidence" response below a threshold.
5. **Calculator scope is narrow by design but silent on failure.** On invalid expressions,
   `calculator` returns a string `"Calculation error: ..."` that the LLM may then paraphrase as
   if it were a result. The node should surface the failure in `CalculationResponse` (e.g. a
   required `status` field), not leave it to the model.
6. **No PII / content redaction on logs.** `ToolLogger` writes full tool inputs and outputs —
   including document content — to `logs/`. Fine for a sandbox; flag it if this ever hits real
   documents.
7. **`eval()` at `tools.py:68` is safe in practice** (AST-validated and `__builtins__` stripped),
   but the review comment should note it anyway; prefer `ast.literal_eval` + an explicit numeric
   evaluator if you want to avoid `eval` entirely.

## 5. Notes the reviewer should pay attention to

- **ReAct agent vs. documented architecture.** `docs/architecture.md` describes plain LangGraph
  nodes, but specialists delegate to `langgraph.prebuilt.create_react_agent`. This is a reasonable
  choice (gives tool-use loop + structured response), but it means the graph shape is
  `classify_intent → react-subgraph → update_memory` rather than "direct LLM call per node". Worth
  either updating the architecture doc or making the trade-off explicit.
- **`_format_history` is built but not used by ReAct specialists.** `classify_intent` calls it
  (`graph.py:75`), but `_run_specialist_node` passes `state["messages"]` as `chat_history` into
  the prompt template; ReAct then receives the templated messages and re-formats history its own
  way. No bug, but the 20-message truncation only applies to intent classification.
- **`next_step` routing is only used once.** The `should_continue` reducer maps it, but the graph
  also has static edges from each specialist to `update_memory`. If you ever need dynamic exits
  (e.g. abstain to END on `unknown`), that logic has a natural home.
- **Session persistence writes on every turn.** Acceptable for this scale; revisit if sessions
  get long or if multi-user concurrency becomes a concern.
- **`assistant.process_message` swallows all exceptions.** Combined with the lack of a real
  logger, a broken run returns `{"success": false, "error": "..."}` with no stack trace anywhere.
  Must log before returning.
- **`__init__.py` imports `DocumentAssistant`** which imports `ChatOpenAI`. Importing the package
  without `OPENAI_API_KEY` set will not fail immediately (the key is only read at instantiation),
  but `Settings()` in `run_cli` will raise if the env var is missing. A friendlier error at CLI
  startup would help.
- **Tests cover retrieval and the calculator only.** No tests for `classify_intent` routing,
  `create_workflow` wiring, or prompt selection. At minimum, add a unit test for
  `get_chat_prompt_template` over all intent types and a smoke test for `create_workflow()` that
  invokes the graph with a mocked LLM.
- **`uv.lock` is tracked.** Fine. Confirm with the team whether `requirements.txt` is still the
  source of truth or if `pyproject.toml` + `uv.lock` should be (currently both exist and are
  in sync).

## 6. What to do to make the project run smoothly

Ordered by payoff:

1. **Introduce `loguru`.** Single sink, rotation, structured fields. Add tracebacks to the
   `process_message` exception branch.
2. **Append-only `ToolLogger`.** Use JSON Lines (`.jsonl`) and `open(..., "a")` per call; remove
   the full-file rewrite.
3. **Enforce retrieval before QA/summarization answers.** Either a retrieval pre-step node or a
   post-check that rejects responses with empty `sources`/`document_ids` when tools were not
   invoked.
4. **Validate `AnswerResponse.sources` against the retriever.** Drop unknown IDs and log a
   warning.
5. **Clarification path for `unknown` intent** and/or low-confidence classifications, instead of
   the silent fallback to `qa_agent`.
6. **Expand tests.** Router, prompt selection, `update_memory` schema compliance, end-to-end graph
   with a fake LLM.
7. **Document the ReAct choice** in `docs/architecture.md` so the graph description matches the
   code.
8. **Environment checks at startup.** Fail fast with a readable message if `OPENAI_API_KEY` is
   missing instead of a raw `ValidationError`.
9. **CLI polish.** `/quit` only matches exact lowercase; consider trimming and handling Ctrl-D /
   Ctrl-C cleanly, and echo the session file path on exit.
10. **Pin or align dependency sources.** Pick `pyproject.toml` + `uv.lock` as canonical and
    generate `requirements.txt` from it, or remove the file.

## 7. Summary for the reviewer

The project delivers all rubric items from `project_instructions.txt` and follows the layered
architecture in `docs/architecture.md`. The hallucination surface is controlled primarily by
Pydantic-structured outputs, prompt instructions to cite sources, and a deterministic in-memory
retriever; the main weaknesses are that source citation is not validated, retrieval is not
enforced at the graph level, low-confidence/unknown intents silently fall through to QA, and
runtime observability relies on a single JSON file written by the tool layer — there is no
`loguru`/`logging` wiring today. Addressing items 1–5 in §6 would meaningfully raise the
reliability and auditability of the system without changing its architecture.
