from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from print_color import print

from .graph import AgentState, create_workflow
from .retrieval import SimulatedRetriever
from .schemas import GraphResult, SessionState
from .settings import Settings
from .tools import ToolLogger, get_all_tools


class DocumentAssistant:
    """Application service responsible for sessions and graph execution."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.model_name,
            temperature=settings.temperature,
            base_url=settings.openai_base_url,
        )
        self.retriever = SimulatedRetriever()
        self.tool_logger = ToolLogger(logs_dir=settings.logs_dir)
        self.tools = get_all_tools(self.retriever, self.tool_logger)
        self.workflow = create_workflow()
        self.session_storage_path = settings.session_storage_path
        os.makedirs(self.session_storage_path, exist_ok=True)
        self.current_session: Optional[SessionState] = None

    def start_session(self, user_id: str, session_id: Optional[str] = None) -> str:
        if session_id and self._session_exists(session_id):
            self.current_session = self._load_session(session_id)
        else:
            session_id = session_id or str(uuid.uuid4())
            self.current_session = SessionState(session_id=session_id, user_id=user_id)
        return self.current_session.session_id

    def process_message(self, user_input: str) -> GraphResult:
        if not self.current_session:
            raise ValueError("No active session. Call start_session() first.")

        config = {
            "configurable": {
                "thread_id": self.current_session.session_id,
                "llm": self.llm,
                "tools": self.tools,
            }
        }

        initial_state: AgentState = {
            "messages": [],
            "user_input": user_input,
            "intent": None,
            "next_step": "classify_intent",
            "conversation_summary": self._get_conversation_summary(config),
            "active_documents": self.current_session.document_context,
            "current_response": None,
            "tools_used": [],
            "session_id": self.current_session.session_id,
            "user_id": self.current_session.user_id,
            "actions_taken": [],
        }

        try:
            final_state = self.workflow.invoke(initial_state, config=config)
            self._update_session(final_state)
            return {
                "success": True,
                "response": final_state.get("messages", [])[-1].content
                if final_state.get("messages")
                else None,
                "intent": final_state.get("intent").model_dump() if final_state.get("intent") else None,
                "tools_used": final_state.get("tools_used", []),
                "sources": final_state.get("active_documents", []),
                "actions_taken": final_state.get("actions_taken", []),
                "summary": final_state.get("conversation_summary", ""),
                "error": None,
            }
        except Exception as exc:
            return {
                "success": False,
                "response": None,
                "intent": None,
                "tools_used": [],
                "sources": [],
                "actions_taken": [],
                "summary": "",
                "error": str(exc),
            }

    def _session_exists(self, session_id: str) -> bool:
        return os.path.exists(self._session_file(session_id))

    def _load_session(self, session_id: str) -> SessionState:
        with open(self._session_file(session_id), "r", encoding="utf-8") as file:
            data = json.load(file)
        return SessionState(**data)

    def _save_session(self) -> None:
        if not self.current_session:
            return
        with open(self._session_file(self.current_session.session_id), "w", encoding="utf-8") as file:
            json.dump(self.current_session.model_dump(mode="json"), file, indent=2, ensure_ascii=True)

    def _session_file(self, session_id: str) -> str:
        return os.path.join(self.session_storage_path, f"{session_id}.json")

    def _get_conversation_summary(self, config: Dict[str, Any]) -> str:
        if not self.current_session or not self.current_session.conversation_history:
            return "No previous conversation."
        try:
            return self.workflow.get_state(config).values.get("conversation_summary", "")
        except Exception:
            return "No previous conversation."

    def _update_session(self, final_state: Dict[str, Any]) -> None:
        if not self.current_session:
            return
        self.current_session.conversation_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "user_input": final_state.get("user_input"),
                "actions_taken": final_state.get("actions_taken", []),
            }
        )
        if final_state.get("active_documents"):
            merged = set(self.current_session.document_context) | set(final_state["active_documents"])
            self.current_session.document_context = sorted(merged)
        self.current_session.last_updated = datetime.now()
        self._save_session()


def _print_header() -> None:
    print("\n" + "=" * 60)
    print("Report Building Agent", color="blue")
    print("=" * 60 + "\n")


def run_cli() -> None:
    load_dotenv()
    settings = Settings()
    assistant = DocumentAssistant(settings)
    _print_header()
    user_id = input("Enter your user ID (default: demo_user): ").strip() or "demo_user"
    session_id = assistant.start_session(user_id=user_id)
    print(f"Session started: {session_id}", color="green")

    while True:
        user_input = input("\nEnter Message: ").strip()
        if not user_input:
            continue
        command = user_input.lower()
        if command == "/quit":
            print("Goodbye!", color="blue")
            break
        if command == "/help":
            print("Commands: /help, /docs, /quit", color="blue")
            print("Examples: 'Summarize all contracts', 'Invoices over $50,000', 'Calculate 2 + 2'")
            continue
        if command == "/docs":
            print("\nAVAILABLE DOCUMENTS:", color="blue")
            for doc_id, doc in assistant.retriever.documents.items():
                print(f"- {doc_id} | {doc.doc_type} | {doc.title}")
            continue

        result = assistant.process_message(user_input)
        if result["success"]:
            print(result["response"] or "No response generated.")
        else:
            print(f"Error: {result['error']}", color="red")
