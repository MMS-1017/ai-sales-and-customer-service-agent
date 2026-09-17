from app.services.knowledge_service import KnowledgeService
from app.models import KnowledgeDocument


def test_knowledge_create_fails_when_vector_ingestion_fails(app, monkeypatch):
    
    with app.app_context():

        def failing_ingest(self, document):
            raise RuntimeError("Vector store unavailable")

        monkeypatch.setattr(
            "app.rag.ingestion.KnowledgeIngestionService.ingest_document",
            failing_ingest,
        )

        result = KnowledgeService.create_document(
            title="Test Policy",
            content="This policy should not be created if indexing fails.",
            category="Policy",
            source="test",
        )

        assert result["success"] is False

        document = KnowledgeDocument.query.filter_by(
            title="Test Policy"
        ).first()

        assert document is None