from app.rag.embeddings import get_embedding_service
from app.rag.retriever import KnowledgeRetriever
from app.rag.vectorstore import ChromaVectorStore
from app.services.knowledge_service import KnowledgeService
from app.config import Config


def get_retriever():
    embedding_service = get_embedding_service(
        Config.EMBEDDING_MODEL
    )

    vector_store = ChromaVectorStore(
        path=Config.CHROMA_PATH
    )

    return KnowledgeRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )


def test_knowledge_create_and_retrieve(app):
    with app.app_context():
        result = KnowledgeService.create_document(
            title="Return Policy",
            content=(
                "Customers can return eligible products "
                "within 30 days of purchase."
            ),
            category="Policy",
            source="test",
        )

        assert result["success"] is True
        assert result["document_id"] is not None
        assert result["chunks"] >= 1

        retriever = get_retriever()

        results = retriever.retrieve(
            "How many days do I have to return a product?"
        )

        assert len(results) > 0
        assert any(
            "30 days" in item["content"]
            for item in results
        )


def test_knowledge_update_refreshes_rag(app):
    with app.app_context():
        create_result = KnowledgeService.create_document(
            title="Return Policy",
            content=(
                "Customers can return eligible products "
                "within 30 days of purchase."
            ),
            category="Policy",
            source="test",
        )

        assert create_result["success"] is True

        document_id = create_result["document_id"]

        update_result = KnowledgeService.update_document(
            document_id=document_id,
            title="Return Policy",
            content=(
                "Customers can return eligible products "
                "within 14 days of purchase."
            ),
            category="Policy",
            source="test",
        )

        assert update_result["success"] is True
        assert update_result["document_id"] == document_id

        retriever = get_retriever()

        results = retriever.retrieve(
            "How many days do I have to return a product?"
        )

        assert len(results) > 0

        retrieved_content = " ".join(
            item["content"]
            for item in results
        )

        assert "14 days" in retrieved_content
        assert "30 days" not in retrieved_content


def test_knowledge_delete_removes_document(app):
    with app.app_context():
        create_result = KnowledgeService.create_document(
            title="Temporary Policy",
            content=(
                "This is a temporary policy "
                "for testing deletion."
            ),
            category="Policy",
            source="test",
        )

        assert create_result["success"] is True

        document_id = create_result["document_id"]

        delete_result = KnowledgeService.delete_document(
            document_id
        )

        assert delete_result["success"] is True

        retriever = get_retriever()

        results = retriever.retrieve(
            "temporary policy testing deletion"
        )

        assert all(
            item["metadata"].get("document_id") != str(document_id)
            for item in results
        )