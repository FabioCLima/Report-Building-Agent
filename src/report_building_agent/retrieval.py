from __future__ import annotations

import re
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
        sample_docs: List[Document] = [
            Document(
                doc_id="INV-001",
                title="Invoice #12345",
                content="""
Invoice #12345
Date: 2024-01-15
Client: Acme Corporation

Services Rendered:
- Consulting Services: $5,000
- Software Development: $12,500
- Support & Maintenance: $2,500

Subtotal: $20,000
Tax (10%): $2,000
Total Due: $22,000
Payment Terms: Net 30 days
""".strip(),
                doc_type="invoice",
                metadata={"client": "Acme Corporation", "date": "2024-01-15", "total": 22000},
            ),
            Document(
                doc_id="CON-001",
                title="Service Agreement",
                content="""
SERVICE AGREEMENT

Provider: DocDacity Solutions Inc.
Client: Healthcare Partners LLC
Start Date: 2024-01-01

Duration: 12 months
Monthly Fee: $15,000
Total Contract Value: $180,000

Termination: Either party may terminate with 60 days written notice.
""".strip(),
                doc_type="contract",
                metadata={"client": "Healthcare Partners LLC", "value": 180000},
            ),
            Document(
                doc_id="CLM-001",
                title="Insurance Claim #78901",
                content="""
INSURANCE CLAIM FORM
Claim Number: 78901
Date of Incident: 2024-02-10
Policy Number: POL-456789

Claimant: John Doe
Type of Claim: Medical Expense Reimbursement

Expenses:
- Hospital Visit: $1,200
- Diagnostic Tests: $800
- Medication: $150
- Follow-up Consultation: $300

Total Claim Amount: $2,450
Status: Under Review
""".strip(),
                doc_type="claim",
                metadata={"claimant": "John Doe", "amount": 2450},
            ),
            Document(
                doc_id="INV-002",
                title="Invoice #12346",
                content="""
Invoice #12346
Date: 2024-02-20
Client: TechStart Inc.

Products:
- Enterprise License (Annual): $50,000
- Implementation Services: $15,000
- Training Package: $5,000

Subtotal: $70,000
Discount (10%): -$7,000
Tax (10%): $6,300
Total Due: $69,300
Payment Terms: Net 45 days
""".strip(),
                doc_type="invoice",
                metadata={"total": 69300, "client": "TechStart Inc.", "date": "2024-02-20"},
            ),
            Document(
                doc_id="INV-003",
                title="Invoice #12347",
                content="""
Invoice #12347
Date: 2024-03-01
Client: Global Corp

Services:
- Annual Subscription: $120,000
- Premium Support: $30,000
- Custom Development: $45,000

Subtotal: $195,000
Tax (10%): $19,500
Total Due: $214,500
Payment Terms: Net 60 days
""".strip(),
                doc_type="invoice",
                metadata={"total": 214500, "client": "Global Corp", "date": "2024-03-01"},
            ),
        ]
        for doc in sample_docs:
            self.documents[doc.doc_id] = doc

    def add_document(self, document: Document) -> None:
        self.documents[document.doc_id] = document

    def retrieve_all(self) -> List[DocumentChunk]:
        return [self._to_chunk(doc, 1.0) for doc in self.documents.values()]

    def retrieve_by_keyword(self, query: str, top_k: int = 3) -> List[DocumentChunk]:
        query_terms = query.lower().split()
        matches: List[DocumentChunk] = []
        for doc in self.documents.values():
            # Include doc_id so users/agent can search by identifiers like "INV-002".
            haystack = f"{doc.doc_id} {doc.title} {doc.content} {doc.metadata}".lower()
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

    def retrieve_by_amount_range(
        self, min_amount: Optional[float] = None, max_amount: Optional[float] = None
    ) -> List[DocumentChunk]:
        results: List[DocumentChunk] = []
        for doc in self.documents.values():
            amount = self._get_document_amount(doc)
            if amount is None:
                continue

            if min_amount is not None and amount < min_amount:
                continue
            if max_amount is not None and amount > max_amount:
                continue

            results.append(self._to_chunk(doc, 1.0))

        results.sort(key=lambda chunk: self._get_amount_from_chunk(chunk), reverse=True)
        return results

    def retrieve_by_exact_amount(self, amount: float, tolerance: float = 0.01) -> List[DocumentChunk]:
        results: List[DocumentChunk] = []
        for doc in self.documents.values():
            doc_amount = self._get_document_amount(doc)
            if doc_amount is not None and abs(doc_amount - amount) <= tolerance:
                results.append(self._to_chunk(doc, 1.0))
        return results

    def retrieve_by_approximate_amount(
        self, amount: float, percentage: float = 10.0
    ) -> List[DocumentChunk]:
        tolerance = amount * (percentage / 100.0)
        min_amount = amount - tolerance
        max_amount = amount + tolerance
        results: List[DocumentChunk] = []
        for doc in self.documents.values():
            doc_amount = self._get_document_amount(doc)
            if doc_amount is None:
                continue
            if min_amount <= doc_amount <= max_amount:
                distance = abs(doc_amount - amount)
                relevance = 1.0 - (distance / tolerance) if tolerance else 1.0
                results.append(self._to_chunk(doc, relevance))
        results.sort(key=lambda chunk: chunk.relevance_score, reverse=True)
        return results

    def retrieve_by_amount(self, query: str) -> List[DocumentChunk]:
        return self._parse_and_retrieve_by_amount(query)

    def _parse_and_retrieve_by_amount(self, query: str) -> List[DocumentChunk]:
        query_lower = query.lower()
        amounts = self._extract_amounts(query_lower)

        if any(word in query_lower for word in ["over", "above", "more than", "greater than", ">"]):
            if amounts:
                return self.retrieve_by_amount_range(min_amount=amounts[0])

        if any(word in query_lower for word in ["under", "below", "less than", "<"]):
            if amounts:
                return self.retrieve_by_amount_range(max_amount=amounts[0])

        if any(word in query_lower for word in ["between", "range", "from"]):
            if len(amounts) >= 2:
                return self.retrieve_by_amount_range(
                    min_amount=min(amounts[0], amounts[1]),
                    max_amount=max(amounts[0], amounts[1]),
                )

        if any(word in query_lower for word in ["around", "about", "approximately", "roughly", "~"]):
            if amounts:
                return self.retrieve_by_approximate_amount(amounts[0])

        if any(word in query_lower for word in ["exactly", "exact", "precisely", "="]):
            if amounts:
                return self.retrieve_by_exact_amount(amounts[0])

        if amounts:
            # If only amounts were mentioned, return a loose range around them.
            return self.retrieve_by_amount_range(min_amount=min(amounts) * 0.9, max_amount=max(amounts) * 1.1)

        return self.retrieve_by_keyword(query)

    def get_document_by_id(self, doc_id: str) -> Optional[DocumentChunk]:
        doc = self.documents.get(doc_id)
        return self._to_chunk(doc, 1.0) if doc else None

    def get_statistics(self) -> Dict[str, Any]:
        amounts: List[float] = []
        doc_types: Dict[str, int] = {}

        for doc in self.documents.values():
            doc_types[doc.doc_type] = doc_types.get(doc.doc_type, 0) + 1
            amount = self._get_document_amount(doc)
            if amount is not None:
                amounts.append(amount)

        return {
            "total_documents": len(self.documents),
            "documents_with_amounts": len(amounts),
            "total_amount": float(sum(amounts)),
            "average_amount": float(sum(amounts) / len(amounts)) if amounts else 0.0,
            "min_amount": float(min(amounts)) if amounts else 0.0,
            "max_amount": float(max(amounts)) if amounts else 0.0,
            "document_types": doc_types,
        }

    def _extract_amounts(self, text: str) -> List[float]:
        amount_pattern = r"\$?(\d+(?:,\d{3})*(?:\.\d{1,2})?)"
        matches = re.findall(amount_pattern, text)
        results: List[float] = []
        for match in matches:
            try:
                results.append(float(match.replace(",", "")))
            except ValueError:
                continue
        return results

    def _get_document_amount(self, doc: Document) -> Optional[float]:
        for field in ["total", "amount", "value", "total_amount", "total_value"]:
            if field in doc.metadata and doc.metadata[field] is not None:
                try:
                    return float(doc.metadata[field])
                except (TypeError, ValueError):
                    continue
        return None

    def _get_amount_from_chunk(self, chunk: DocumentChunk) -> float:
        for field in ["total", "amount", "value", "total_amount", "total_value"]:
            if field in chunk.metadata:
                try:
                    return float(chunk.metadata[field])
                except (TypeError, ValueError):
                    continue
        return 0.0

    def _to_chunk(self, doc: Document, relevance_score: float) -> DocumentChunk:
        return DocumentChunk(
            doc_id=doc.doc_id,
            content=doc.content,
            metadata={"title": doc.title, "doc_type": doc.doc_type, **doc.metadata},
            relevance_score=relevance_score,
        )
