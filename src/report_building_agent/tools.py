from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from langchain_core.tools import tool


class ToolLogger:
    """Simple JSON logger for tool usage."""

    def __init__(self, logs_dir: str = "./logs", session_id: str | None = None) -> None:
        self.logs: List[Dict[str, Any]] = []
        self.logs_dir = logs_dir
        self.session_id = session_id
        os.makedirs(logs_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{session_id}.json" if session_id else f"tool_usage_{timestamp}.json"
        self.log_file = os.path.join(logs_dir, filename)

    def log_tool_use(self, tool_name: str, input_data: Dict[str, Any], output: Any) -> None:
        self.logs.append(
            {
                "timestamp": datetime.now().isoformat(),
                "tool_name": tool_name,
                "input": input_data,
                "output": str(output),
            }
        )
        with open(self.log_file, "w", encoding="utf-8") as file:
            json.dump(self.logs, file, indent=2, ensure_ascii=True)


def create_calculator_tool(logger: ToolLogger):
    """Create a safe calculator tool for arithmetic expressions."""

    @tool
    def calculator(expression: str) -> str:
        """Evaluate a basic arithmetic expression using digits, spaces, and math operators."""

        if not re.fullmatch(r"[0-9\.\+\-\*\/\(\)\s]+", expression):
            error = "Invalid expression. Only basic arithmetic is allowed."
            logger.log_tool_use("calculator", {"expression": expression}, {"error": error})
            return error

        try:
            result = eval(expression, {"__builtins__": {}}, {})
            response = f"Result: {result}"
            logger.log_tool_use("calculator", {"expression": expression}, {"result": result})
            return response
        except Exception as exc:
            error = f"Calculation error: {exc}"
            logger.log_tool_use("calculator", {"expression": expression}, {"error": error})
            return error

    return calculator


def create_document_search_tool(retriever, logger: ToolLogger):
    @tool
    def document_search(query: str) -> str:
        """Search documents by keyword and return a formatted overview."""

        results = retriever.retrieve_by_keyword(query)
        logger.log_tool_use("document_search", {"query": query}, {"results_count": len(results)})
        if not results:
            return "No documents found."
        return "\n".join(f"{item.doc_id}: {item.metadata.get('title', 'Untitled')}" for item in results)

    return document_search


def create_document_reader_tool(retriever, logger: ToolLogger):
    @tool
    def document_reader(doc_id: str) -> str:
        """Read a document by ID."""

        doc = retriever.get_document_by_id(doc_id)
        logger.log_tool_use("document_reader", {"doc_id": doc_id}, {"found": bool(doc)})
        if not doc:
            return f"Document {doc_id} not found."
        return f"{doc.doc_id}\n{doc.content}"

    return document_reader


def create_document_statistics_tool(retriever, logger: ToolLogger):
    @tool
    def document_statistics() -> str:
        """Return collection statistics."""

        stats = retriever.get_statistics()
        logger.log_tool_use("document_statistics", {}, stats)
        return json.dumps(stats, indent=2)

    return document_statistics


def get_all_tools(retriever, logger: ToolLogger) -> List[Any]:
    return [
        create_calculator_tool(logger),
        create_document_search_tool(retriever, logger),
        create_document_reader_tool(retriever, logger),
        create_document_statistics_tool(retriever, logger),
    ]
