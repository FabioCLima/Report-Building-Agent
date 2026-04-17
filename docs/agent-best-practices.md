# Best Practices for Building AI Agents

A practical checklist for designing, implementing, and operating LLM-based agents.
Examples reference this repository (`src/report_building_agent/`) when relevant so the
guidance stays concrete.

## 1. Start from the problem, not the framework

- Write the user goal in one sentence and the **failure modes you cannot tolerate**
  (hallucination, wrong tool call, infinite loops, leaked PII).
- Decide whether you actually need an agent. If the task is a single LLM call with a
  fixed prompt, do that — agents add cost, latency, and surface area.
- Define what "done" looks like as evaluation cases before you write the graph.

## 2. Architect in layers

Keep these concerns in separate modules, even for small projects:

| Layer | Responsibility | Repo example |
| --- | --- | --- |
| Entry / CLI | I/O, env loading, no business logic | `main.py` |
| Application | Sessions, config assembly, error envelope | `assistant.py` |
| Workflow | State, nodes, routing, checkpointer | `graph.py` |
| Domain | Pydantic schemas (the contracts) | `schemas.py` |
| Prompts | Centralized templates, no f-strings in code | `prompts.py` |
| Retrieval | Search abstraction, swappable backend | `retrieval.py` |
| Tools | Side-effecting capabilities, validated I/O | `tools.py` |
| Settings | Env-driven config, fail fast | `settings.py` |

Benefits: testable units, no string drift, a clean swap path when you replace the
simulated retriever with a real vector store.

## 3. Use structured outputs everywhere

- Bind every LLM call to a Pydantic schema (`with_structured_output` or
  `response_format=...`). Free-text parsing is a debugging tax you will keep paying.
- Constrain enums (`Literal`) and ranges (`Field(ge=..., le=...)`) so the model cannot
  produce values outside the contract.
- Add a `confidence` field and **use it** to gate downstream behavior — capturing it
  without acting on it is theatre.
- Distinguish `result` from `status`. A failed tool call should not be returned as if
  it were a value.

## 4. Treat hallucination as an engineering concern

- **Ground first, generate after.** Force a retrieval/tool step before answers, either
  with a pre-step node or by rejecting responses that have no `sources`.
- **Validate citations.** Intersect any IDs in the response with the IDs the retriever
  actually returned this turn. Drop or flag unknown ones.
- **Prefer abstention over guessing.** Provide an explicit `unknown` / "insufficient
  evidence" path. Don't silently route to a default agent.
- **Lower temperature** for deterministic tasks (classification, extraction, math).
- **Keep prompts boring.** Specific instructions beat clever framings; tell the model
  what to cite, what to refuse, and what format to return.
- **Show, don't list.** Few-shot examples beat long bullet rules for shaping output.

## 5. Tools are an API surface — design them like one

- Decorate with `@tool`, write a one-line docstring (the model reads it), and keep
  parameters typed.
- Validate inputs at the boundary (regex, enum, range). The repo's
  `_safe_eval_arithmetic` (`tools.py:46`) is a good template — whitelist characters,
  walk the AST, strip `__builtins__`.
- Return strings the model can quote back. Include identifiers and units, not raw
  blobs.
- Handle errors as values, not exceptions, so the agent loop can react.
- Log every call with input + output for audit and debugging.
- Idempotency: a retried tool call must be safe.

## 6. State and memory

- Make the state object explicit (`TypedDict` or Pydantic). Document each field's
  owner and lifecycle.
- Use **reducers** (`operator.add`, `add_messages`) for accumulating fields instead of
  manual concatenation in nodes.
- Persist long-term context with a checkpointer (`InMemorySaver` for dev, a durable
  store for prod). Always pass `thread_id` so the checkpointer can isolate sessions.
- Summarize old turns into a compact memory rather than feeding the full transcript
  every call. Cap history length (the repo truncates to the last 20 messages in
  `_format_history`).
- Persist session metadata outside the graph too, so you can recover after a crash and
  audit conversations offline.

## 7. Routing and graph design

- One node = one responsibility. If a node both decides and acts, split it.
- Prefer **conditional edges driven by state** (`should_continue`-style) over hidden
  control flow inside nodes.
- Add a maximum-step guard on any loop. ReAct loops can spin; cap iterations and emit
  a structured "gave up" response.
- Make every terminal path explicit: success, abstain, error.

## 8. Observability

- Use a real logger (`loguru` or stdlib `logging`) for runtime events: intent, tool
  calls, latencies, exceptions with traceback. Don't rely only on file dumps.
- Use **JSON Lines** (`.jsonl`) with append-only writes for tool/audit logs — never
  rewrite the full file on every event (O(n²) and risk of partial writes).
- Tag every log line with `session_id`, `node`, and a turn counter so you can replay a
  conversation from logs alone.
- Track at minimum: tokens in/out, tool call counts, total latency per turn,
  classification confidence distribution, abstention rate.

## 9. Security and safety

- **Never `eval` untrusted input.** If you must evaluate expressions, parse to AST,
  whitelist node types, and strip builtins (see `tools.py`).
- Treat document content and tool output as untrusted — they can carry prompt
  injection. Don't blindly forward retrieved text into system prompts.
- Limit tool permissions: read-only by default, write tools behind explicit user
  confirmation.
- Redact secrets and PII before logging. The repo's `ToolLogger` currently logs full
  document content; in production, mask or hash it.
- Set hard limits: max tokens per call, max tool calls per turn, max turns per
  session.
- Time out external calls. Retry with backoff, but cap total retries.

## 10. Configuration and environment

- Use a single typed settings object (`pydantic-settings`) with required fields. Fail
  fast at startup with a readable error if env is incomplete.
- Keep secrets out of code and out of logs. `.env` for dev, secret manager for prod.
- Pin model identifiers explicitly (`gpt-4o`, `claude-opus-4-7`, ...). Don't depend on
  "latest" aliases for reproducibility.
- One source of truth for dependencies (`pyproject.toml` + lockfile). Generate
  `requirements.txt` if you must, don't hand-edit both.

## 11. Testing strategy

- **Pure logic**: unit-test retrievers, validators, prompt selection, schema
  constraints — no LLM needed.
- **Tool I/O**: test each tool in isolation with adversarial inputs (the repo's
  `test_safe_eval_rejects_calls` is a good pattern).
- **Routing**: test `classify_intent` mappings and conditional edges with a fake LLM
  that returns canned `UserIntent` values.
- **End-to-end smoke**: invoke `create_workflow()` with a stub LLM and assert
  `actions_taken`, schema shape, and termination.
- **Golden eval set**: a fixed list of inputs with expected intents, expected tools
  used, and acceptable answers. Run it on every change.
- **Regression on hallucinations**: track citation accuracy and abstention rate over
  time, not just pass/fail.

## 12. Cost, latency, and reliability

- Cache prompts where the framework supports it; the system prompt and tool catalog
  are stable across turns.
- Batch retrieval and prefer narrower queries before broad ones.
- Stream outputs to the user when latency matters.
- Add timeouts on every external call (LLM, retriever, tools).
- Degrade gracefully: on tool failure, return a structured "tool unavailable" answer
  rather than crashing the turn.

## 13. Evaluation as a first-class loop

- Build a small **eval harness** (deterministic seed, fake or recorded LLM responses)
  that runs in CI.
- Score on multiple axes: correctness, citation accuracy, abstention appropriateness,
  tool-use efficiency, latency, cost.
- Sample real sessions for manual review weekly. Bugs hide in long-tail prompts.

## 14. Prompt hygiene

- Keep prompts in one module, named constants, documented inputs.
- Version prompts the same way you version code; a prompt change is a behavior
  change.
- Prefer task-specific system prompts per node over one mega-prompt.
- When in doubt, give the model the schema description and one example, not three
  paragraphs of rules.

## 15. Minimal launch checklist

Before shipping or demoing:

- [ ] `OPENAI_API_KEY` (or equivalent) validated at startup with a clear error.
- [ ] Structured logger configured with rotation; tracebacks captured.
- [ ] Tool inputs validated; `eval`/shell paths reviewed.
- [ ] Citations validated against the retriever index.
- [ ] Abstention path exercised in tests.
- [ ] Max-turn / max-tool-call guards in place.
- [ ] Session checkpointer wired with `thread_id`.
- [ ] At least one end-to-end test with a stub LLM passes in CI.
- [ ] README has run instructions and a sample conversation.

## Further reading

- LangGraph docs: state, checkpointers, conditional edges, prebuilt agents.
- Anthropic & OpenAI guides on tool use and structured outputs.
- "Building LLM applications for production" — chapters on evaluation and
  observability.
- OWASP Top 10 for LLM Applications — prompt injection, insecure output handling,
  excessive agency.
