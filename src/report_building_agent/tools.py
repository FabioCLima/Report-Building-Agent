from __future__ import annotations

import ast
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

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

    allowed_operators = (
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
    )

    @tool
    def calculator(expression: str) -> str:
        """Evaluate a basic arithmetic expression using digits, spaces, and math operators."""

        if not re.fullmatch(r"[0-9\.\+\-\*\/\%\(\)\s]+", expression):
            error = "Invalid expression. Only basic arithmetic is allowed."
            logger.log_tool_use("calculator", {"expression": expression}, {"error": error})
            return error

        try:
            parsed = ast.parse(expression, mode="eval")

            for node in ast.walk(parsed):
                if isinstance(node, ast.Call) or isinstance(node, ast.Attribute) or isinstance(node, ast.Name):
                    raise ValueError("Invalid expression.")
                if isinstance(node, ast.BinOp) and not isinstance(node.op, allowed_operators):
                    raise ValueError("Invalid operator.")
                if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
                    raise ValueError("Invalid constant.")

            result = eval(compile(parsed, "<calculator>", "eval"), {"__builtins__": {}}, {})
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
    def document_search(
        query: str,
        search_type: Literal["keyword", "type", "amount", "amount_range", "all"] = "keyword",
        doc_type: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
    ) -> str:
        """Search documents using keyword/type/amount criteria."""

        try:
            if search_type == "all":
                results = retriever.retrieve_all()
            elif search_type == "type" and doc_type:
                results = retriever.retrieve_by_type(doc_type)
            elif search_type in {"amount", "amount_range"}:
                results = retriever.retrieve_by_amount_range(min_amount=min_amount, max_amount=max_amount)
            elif search_type == "keyword":
                results = retriever.retrieve_by_keyword(query)
            else:
                # Best-effort fallback: detect amount patterns, otherwise keyword.
                if any(token in query.lower() for token in ["$", "over", "under", "between", "around", "exact"]):
                    results = retriever.retrieve_by_amount(query)
                else:
                    results = retriever.retrieve_by_keyword(query)

            logger.log_tool_use(
                "document_search",
                {
                    "query": query,
                    "search_type": search_type,
                    "doc_type": doc_type,
                    "min_amount": min_amount,
                    "max_amount": max_amount,
                },
                {"results_count": len(results)},
            )

            if not results:
                return "No documents found matching your criteria."

            lines: List[str] = []
            for chunk in results:
                title = chunk.metadata.get("title", "Untitled")
                dtype = chunk.metadata.get("doc_type", "unknown")
                amount = None
                for field in ["total", "amount", "value"]:
                    if field in chunk.metadata:
                        amount = chunk.metadata[field]
                        break
                amount_part = f" | amount={amount}" if amount is not None else ""
                lines.append(f"{chunk.doc_id} | {dtype} | {title}{amount_part}")
            return "\n".join(lines)
        except Exception as exc:
            error = f"Error searching documents: {exc}"
            logger.log_tool_use("document_search", {"query": query, "search_type": search_type}, {"error": error})
            return error

    return document_search


def create_document_reader_tool(retriever, logger: ToolLogger):
    @tool
    def document_reader(doc_id: str) -> str:
        """Read a document by ID."""

        doc = retriever.get_document_by_id(doc_id)
        logger.log_tool_use("document_reader", {"doc_id": doc_id}, {"found": bool(doc)})
        if not doc:
            return f"Document {doc_id} not found."
        amount_info = ""
        for field in ["total", "amount", "value"]:
            if field in doc.metadata:
                try:
                    amount_info = f"\nAmount: ${float(doc.metadata[field]):,.2f}"
                except Exception:
                    amount_info = f"\nAmount: {doc.metadata[field]}"
                break
        return f"Document {doc.doc_id}:{amount_info}\n\n{doc.content}"

    return document_reader


def create_document_statistics_tool(retriever, logger: ToolLogger):
    @tool
    def document_statistics() -> str:
        """Return collection statistics."""

        try:
            stats = retriever.get_statistics()
            logger.log_tool_use("document_statistics", {}, stats)
            formatted = "DOCUMENT COLLECTION STATISTICS\n\n"
            formatted += f"Total Documents: {stats['total_documents']}\n"
            formatted += f"Documents with Amounts: {stats['documents_with_amounts']}\n"
            formatted += "Document Types:\n"
            for doc_type, count in stats["document_types"].items():
                formatted += f"- {doc_type}: {count}\n"
            if stats["documents_with_amounts"] > 0:
                formatted += "\nFinancial Summary:\n"
                formatted += f"- Total Amount: ${stats['total_amount']:,.2f}\n"
                formatted += f"- Average Amount: ${stats['average_amount']:,.2f}\n"
                formatted += f"- Minimum Amount: ${stats['min_amount']:,.2f}\n"
                formatted += f"- Maximum Amount: ${stats['max_amount']:,.2f}\n"
            return formatted.strip()
        except Exception as exc:
            error = f"Error getting statistics: {exc}"
            logger.log_tool_use("document_statistics", {}, {"error": error})
            return error

    return document_statistics


def get_all_tools(retriever, logger: ToolLogger) -> List[Any]:
    return [
        create_calculator_tool(logger),
        create_document_search_tool(retriever, logger),
        create_document_reader_tool(retriever, logger),
        create_document_statistics_tool(retriever, logger),
    ]
