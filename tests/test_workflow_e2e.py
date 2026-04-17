import re
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from report_building_agent.graph import AgentState, create_workflow
from report_building_agent.schemas import (
    AnswerResponse,
    CalculationResponse,
    SummarizationResponse,
    UpdateMemoryResponse,
    UserIntent,
)
from report_building_agent.retrieval import SimulatedRetriever
from report_building_agent.tools import ToolLogger, get_all_tools


class _StructuredLLM:
    def __init__(self, schema_type):
        self._schema_type = schema_type

    def invoke(self, prompt: Any):
        text = str(prompt)
        if self._schema_type is UserIntent:
            user_match = re.search(r"User Input:\s*(.*)", text)
            user_input = (user_match.group(1).strip() if user_match else text).lower()
            if any(token in user_input for token in ["summar", "resum"]):
                intent_type = "summarization"
            elif any(token in user_input for token in ["calc", "som", "add", "+", "total", "average", "media"]):
                intent_type = "calculation"
            elif any(token in user_input for token in ["?", "qual", "what", "which", "when", "payment", "prazo"]):
                intent_type = "qa"
            else:
                intent_type = "unknown"
            return UserIntent(intent_type=intent_type, confidence=0.9, reasoning="Deterministic test classifier.")

        if self._schema_type is UpdateMemoryResponse:
            doc_ids = sorted(set(re.findall(r"\b[A-Z]{3}-\d{3}\b", text)))
            summary = "Conversation summarized for tests."
            return UpdateMemoryResponse(summary=summary, document_ids=doc_ids)

        raise AssertionError(f"Unexpected schema: {self._schema_type}")


class FakeLLM:
    def with_structured_output(self, schema_type):
        return _StructuredLLM(schema_type)

    def bind_tools(self, tools):
        return self


def _tool_map(tools) -> Dict[str, Any]:
    mapping: Dict[str, Any] = {}
    for tool in tools:
        name = getattr(tool, "name", None) or getattr(getattr(tool, "__class__", object), "__name__", "tool")
        mapping[name] = tool
    return mapping


def fake_agent_invoke(*, response_schema, messages: List[BaseMessage], tools, llm):
    last_user = ""
    for message in reversed(messages):
        if getattr(message, "type", "") == "human":
            last_user = str(getattr(message, "content", ""))
            break
    tool_by_name = _tool_map(tools)
    produced_messages: List[BaseMessage] = []

    if response_schema is CalculationResponse:
        # Use a doc as source and compute something deterministic.
        doc_id = "INV-002"
        doc_text = tool_by_name["document_reader"].invoke({"doc_id": doc_id})
        produced_messages.append(ToolMessage(name="document_reader", content=doc_text, tool_call_id="t1"))
        calc_out = tool_by_name["calculator"].invoke({"expression": "2 + 3"})
        produced_messages.append(ToolMessage(name="calculator", content=calc_out, tool_call_id="t2"))
        produced_messages.append(AIMessage(content=f"Computed from {doc_id}: {calc_out}"))
        return {"messages": produced_messages}

    if response_schema is SummarizationResponse:
        doc_id = "CON-001"
        doc_text = tool_by_name["document_reader"].invoke({"doc_id": doc_id})
        produced_messages.append(ToolMessage(name="document_reader", content=doc_text, tool_call_id="t1"))
        produced_messages.append(AIMessage(content=f"Summary for {doc_id}: key points ..."))
        return {"messages": produced_messages}

    if response_schema is AnswerResponse:
        results = tool_by_name["document_search"].invoke({"query": last_user, "search_type": "keyword"})
        produced_messages.append(ToolMessage(name="document_search", content=results, tool_call_id="t1"))
        produced_messages.append(AIMessage(content=f"Answer (from docs): {results.splitlines()[0] if results else ''}"))
        return {"messages": produced_messages}

    raise AssertionError(f"Unexpected response_schema: {response_schema}")


def _invoke(user_input: str) -> Dict[str, Any]:
    retriever = SimulatedRetriever()
    logger = ToolLogger(logs_dir="./logs", session_id="test-session")
    tools = get_all_tools(retriever, logger)
    workflow = create_workflow()

    config = {
        "configurable": {
            "thread_id": "test-thread",
            "llm": FakeLLM(),
            "tools": tools,
            "agent_invoke": fake_agent_invoke,
        }
    }

    initial_state: AgentState = {
        "messages": [],
        "user_input": user_input,
        "intent": None,
        "next_step": "classify_intent",
        "conversation_summary": "No previous conversation.",
        "active_documents": [],
        "current_response": None,
        "tools_used": [],
        "session_id": "test-session",
        "user_id": "test-user",
        "actions_taken": [],
    }

    return workflow.invoke(initial_state, config=config)


def test_workflow_routes_qa_and_updates_memory():
    final_state = _invoke("Which invoices mention Acme?")
    assert final_state["intent"].intent_type == "qa"
    assert "classify_intent" in final_state["actions_taken"]
    assert "qa_agent" in final_state["actions_taken"]
    assert "update_memory" in final_state["actions_taken"]
    assert "document_search" in final_state["tools_used"]


def test_workflow_routes_summarization_and_updates_memory():
    final_state = _invoke("Summarize CON-001")
    assert final_state["intent"].intent_type == "summarization"
    assert "summarization_agent" in final_state["actions_taken"]
    assert "document_reader" in final_state["tools_used"]


def test_workflow_routes_calculation_and_updates_memory():
    final_state = _invoke("Calculate 2 + 3 using invoice data")
    assert final_state["intent"].intent_type == "calculation"
    assert "calculation_agent" in final_state["actions_taken"]
    assert "calculator" in final_state["tools_used"]
