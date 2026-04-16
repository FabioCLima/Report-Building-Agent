from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from .prompts import (
    MEMORY_SUMMARY_PROMPT,
    get_intent_classification_prompt,
    get_chat_prompt_template,
)
from .schemas import (
    AnswerResponse,
    CalculationResponse,
    SummarizationResponse,
    UpdateMemoryResponse,
    UserIntent,
)


class AgentState(TypedDict):
    user_input: Optional[str]
    messages: Annotated[List[BaseMessage], add_messages]
    intent: Optional[UserIntent]
    next_step: str
    conversation_summary: str
    active_documents: Optional[List[str]]
    current_response: Optional[Dict[str, Any]]
    tools_used: List[str]
    session_id: Optional[str]
    user_id: Optional[str]
    actions_taken: Annotated[List[str], operator.add]


def _format_history(messages: List[BaseMessage]) -> str:
    lines: List[str] = []
    for message in messages:
        # BaseMessage usually exposes `.type` and `.content`
        role = getattr(message, "type", message.__class__.__name__)
        content = getattr(message, "content", "")
        if isinstance(content, list):
            content = str(content)
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def invoke_react_agent(
    response_schema: type[BaseModel],
    messages: List[BaseMessage],
    llm: Any,
    tools: List[Any],
) -> tuple[Dict[str, Any], List[str]]:
    llm_with_tools = llm.bind_tools(tools)
    agent = create_react_agent(model=llm_with_tools, tools=tools, response_format=response_schema)
    result = agent.invoke({"messages": messages})
    tools_used = [message.name for message in result.get("messages", []) if isinstance(message, ToolMessage)]
    return result, tools_used


def classify_intent(state: AgentState, config: RunnableConfig) -> AgentState:
    llm = config["configurable"]["llm"]
    history = state.get("messages", [])
    structured_llm = llm.with_structured_output(UserIntent)
    prompt = get_intent_classification_prompt().format(
        user_input=state.get("user_input", ""),
        conversation_history=_format_history(history),
    )
    intent = structured_llm.invoke(prompt)
    route_map = {
        "qa": "qa_agent",
        "summarization": "summarization_agent",
        "calculation": "calculation_agent",
    }
    return {
        "intent": intent,
        "next_step": route_map.get(intent.intent_type, "qa_agent"),
        "actions_taken": ["classify_intent"],
    }


def _run_specialist_node(
    state: AgentState,
    config: RunnableConfig,
    intent_type: str,
    response_schema: type[BaseModel],
    action_name: str,
) -> AgentState:
    llm = config["configurable"]["llm"]
    tools = config["configurable"]["tools"]
    prompt_template = get_chat_prompt_template(intent_type)
    messages = prompt_template.invoke(
        {"input": state["user_input"], "chat_history": state.get("messages", [])}
    ).to_messages()
    result, tools_used = invoke_react_agent(response_schema, messages, llm, tools)
    return {
        "messages": result.get("messages", []),
        "actions_taken": [action_name],
        "current_response": result,
        "tools_used": tools_used,
        "next_step": "update_memory",
    }


def qa_agent(state: AgentState, config: RunnableConfig) -> AgentState:
    return _run_specialist_node(state, config, "qa", AnswerResponse, "qa_agent")


def summarization_agent(state: AgentState, config: RunnableConfig) -> AgentState:
    return _run_specialist_node(
        state, config, "summarization", SummarizationResponse, "summarization_agent"
    )


def calculation_agent(state: AgentState, config: RunnableConfig) -> AgentState:
    return _run_specialist_node(
        state, config, "calculation", CalculationResponse, "calculation_agent"
    )


def update_memory(state: AgentState, config: RunnableConfig) -> AgentState:
    llm = config["configurable"]["llm"]
    prompt = MEMORY_SUMMARY_PROMPT + "\n\n" + _format_history(state.get("messages", []))
    structured_llm = llm.with_structured_output(UpdateMemoryResponse)
    response = structured_llm.invoke(prompt)
    return {
        "conversation_summary": response.summary,
        "active_documents": response.document_ids,
        "actions_taken": ["update_memory"],
        "next_step": "end",
    }


def should_continue(state: AgentState) -> str:
    return state.get("next_step", "end")


def create_workflow(llm: Any, tools: List[Any]):
    # `llm` and `tools` are provided via `configurable` at runtime.
    del llm, tools
    workflow = StateGraph(AgentState)
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("qa_agent", qa_agent)
    workflow.add_node("summarization_agent", summarization_agent)
    workflow.add_node("calculation_agent", calculation_agent)
    workflow.add_node("update_memory", update_memory)
    workflow.set_entry_point("classify_intent")
    workflow.add_conditional_edges(
        "classify_intent",
        should_continue,
        {
            "qa_agent": "qa_agent",
            "summarization_agent": "summarization_agent",
            "calculation_agent": "calculation_agent",
            "end": END,
        },
    )
    workflow.add_edge("qa_agent", "update_memory")
    workflow.add_edge("summarization_agent", "update_memory")
    workflow.add_edge("calculation_agent", "update_memory")
    workflow.add_edge("update_memory", END)
    return workflow.compile(checkpointer=InMemorySaver())
