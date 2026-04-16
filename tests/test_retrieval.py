from report_building_agent.retrieval import SimulatedRetriever


def test_retrieve_by_type_invoice():
    retriever = SimulatedRetriever()
    chunks = retriever.retrieve_by_type("invoice")
    assert {c.doc_id for c in chunks} >= {"INV-001", "INV-002", "INV-003"}


def test_retrieve_by_keyword():
    retriever = SimulatedRetriever()
    chunks = retriever.retrieve_by_keyword("Acme")
    assert any(c.doc_id == "INV-001" for c in chunks)


def test_retrieve_by_amount_range_over_50k():
    retriever = SimulatedRetriever()
    chunks = retriever.retrieve_by_amount_range(min_amount=50_000)
    ids = {c.doc_id for c in chunks}
    assert "INV-002" in ids
    assert "INV-003" in ids
    assert "CON-001" in ids


def test_statistics_shape():
    retriever = SimulatedRetriever()
    stats = retriever.get_statistics()
    assert stats["total_documents"] >= 5
    assert "invoice" in stats["document_types"]
