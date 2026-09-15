from app.extensions import db
from app.models import KnowledgeDocument
from app.config import Config

from app.rag.embeddings import get_embedding_service
from app.rag.vectorstore import ChromaVectorStore
from app.rag.ingestion import KnowledgeIngestionService

class KnowledgeService:

    @staticmethod
    def _get_ingestion_service():

        embedding_service = get_embedding_service(Config.EMBEDDING_MODEL)

        vector_store = ChromaVectorStore(path=Config.CHROMA_PATH)

        return KnowledgeIngestionService(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

    @staticmethod
    def list_documents():
        return (
            KnowledgeDocument.query
            .order_by(KnowledgeDocument.updated_at.desc())
            .all()
        )

    @staticmethod
    def get_document(document_id: int):
        return db.session.get(KnowledgeDocument, document_id)


    @staticmethod
    def create_document(title: str, content: str, category: str, source: str | None = None):

        title = title.strip()
        content = content.strip()
        category = category.strip()

        if not title:
            return {
                "success": False,
                "error": "Title is required.",
            }

        if not content:
            return {
                "success": False,
                "error": "Content is required.",
            }

        try:

            document = KnowledgeDocument(
                title=title,
                content=content,
                category=category,
                source=source.strip() if source else None,
            )

            db.session.add(document)
            db.session.commit()

            ingestion_service = (KnowledgeService._get_ingestion_service())

            chunks = ingestion_service.ingest_document(document)

            return {
                "success": True,
                "document_id": document.id,
                "chunks": chunks,
            }

        except Exception:

            db.session.rollback()

            return {
                "success": False,
                "error": "Failed to create knowledge document.",
            }

    @staticmethod
    def update_document(document_id: int, title: str, content: str, 
                        category: str, source: str | None = None):

        document = KnowledgeService.get_document(document_id)

        if not document:
            return {
                "success": False,
                "error": "Knowledge document not found.",
            }

        title = title.strip()
        content = content.strip()
        category = category.strip()

        if not title:
            return {
                "success": False,
                "error": "Title is required.",
            }

        if not content:
            return {
                "success": False,
                "error": "Content is required.",
            }

        try:

            document.title = title
            document.content = content
            document.category = category
            document.source = (source.strip() if source else None)

            db.session.commit()

            ingestion_service = (KnowledgeService._get_ingestion_service())

            vector_store = (ingestion_service.vector_store)

            # Remove old chunks
            vector_store.delete_document(document.id)

            # Index updated document
            chunks = ingestion_service.ingest_document(document)

            return {
                "success": True,
                "document_id": document.id,
                "chunks": chunks,
            }

        except Exception:

            db.session.rollback()

            return {
                "success": False,
                "error": "Failed to update knowledge document.",
            }

    @staticmethod
    def delete_document(document_id: int):

        document = KnowledgeService.get_document(document_id)
        if not document:
            return {
                "success": False,
                "error": "Knowledge document not found.",
            }

        try:

            ingestion_service = (KnowledgeService._get_ingestion_service())

            # Remove document chunks from Chroma
            ingestion_service.vector_store.delete_document(document.id)

            # Remove document from PostgreSQL
            db.session.delete(document)
            db.session.commit()

            return {
                "success": True,
                "document_id": document_id,
            }

        except Exception:

            db.session.rollback()

            return {
                "success": False,
                "error": "Failed to delete knowledge document.",
            }