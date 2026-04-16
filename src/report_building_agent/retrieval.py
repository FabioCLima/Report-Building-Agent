from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .schemas import DocumentChunk


@dataclass
class Document:
    doc_id: str
    title: str
    content: str
    doc_type: str
    metadata: Dict[str, Any]


class SimulatedRetriever:
    """In-memory retriever kept intentionally simple for the starter project."""

    def __init__(self) -> None:
        self.documents: Dict[str, Document] = {}
        self._load_sample_documents()

    def _load_sample_documents(self) -> None:
        sample_docs = [
            Document(
                doc_id="INV-001",
                title="Invoice #12345",
                content="Invoice #12345 for Acme Corporation. Subtotal $20,000. Tax $2,000.",
                doc_type="invoice",
                metadata={"client": "Acme Corporation", "date": "2024-01-15", "total": 22000},
            ),
            Document(
                doc_id="CON-001",
                title="Service Agreement",
                content="Service agreement with Healthcare Partners LLC. Total contract value $180,000.",
                doc_type="contract",
                metadata={"client": "Healthcare Partners LLC", "value": 180000},
            ),
            Document(
                doc_id="CLM-001",
                title="Insurance Claim #78901",
                content="Medical expense reimbursement claim. Total claim amount $2,450.",
                doc_type="claim",
                metadata={"claimant": "John Doe", "amount": 2450},
            ),
        ]
        for doc in sample_docs:
            self.documents[doc.doc_id] = doc

    def retrieve_all(self) -> List[DocumentChunk]:
        return [self._to_chunk(doc, 1.0) for doc in self.documents.values()]

    def retrieve_by_keyword(self, query: str, top_k: int = 3) -> List[DocumentChunk]:
        query_terms = query.lower().split()
        matches: List[DocumentChunk] = []
        for doc in self.documents.values():
            haystack = f"{doc.title} {doc.content} {doc.metadata}".lower()
            score = sum(haystack.count(term) for term in query_terms)
            if score > 0:
                matches.append(self._to_chunk(doc, float(score)))
        matches.sort(key=lambda item: item.relevance_score, reverse=True)
        return matches[:top_k]

    def retrieve_by_type(self, doc_type: str) -> List[DocumentChunk]:
        return [
            self._to_chunk(doc, 1.0)
            for doc in self.documents.values()
            if doc.doc_type.lower() == doc_type.lower()
        ]

    def get_document_by_id(self, doc_id: str) -> Optional[DocumentChunk]:
        doc = self.documents.get(doc_id)
        return self._to_chunk(doc, 1.0) if doc else None

    def get_statistics(self) -> Dict[str, Any]:
        amounts = [
            value
            for doc in self.documents.values()
            for key, value in doc.metadata.items()
            if key in {"total", "amount", "value"} and isinstance(value, (int, float))
        ]
        return {
            "total_documents": len(self.documents),
            "documents_with_amounts": len(amounts),
            "total_amount": float(sum(amounts)),
            "average_amount": float(sum(amounts) / len(amounts)) if amounts else 0.0,
            "min_amount": float(min(amounts)) if amounts else 0.0,
            "max_amount": float(max(amounts)) if amounts else 0.0,
            "document_types": self._document_types(),
        }

    def _document_types(self) -> Dict[str, int]:
        result: Dict[str, int] = {}
        for doc in self.documents.values():
            result[doc.doc_type] = result.get(doc.doc_type, 0) + 1
        return result

    def _to_chunk(self, doc: Document, relevance_score: float) -> DocumentChunk:
        return DocumentChunk(
            doc_id=doc.doc_id,
            content=doc.content,
            metadata={"title": doc.title, "doc_type": doc.doc_type, **doc.metadata},
            relevance_score=relevance_score,
        )
