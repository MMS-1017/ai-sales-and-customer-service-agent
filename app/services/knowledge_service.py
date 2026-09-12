from app.extensions import db
from app.models import KnowledgeDocument
from app.config import Config
from app.rag import (
    EmbeddingService,
    ChromaVectorStore,
    KnowledgeIngestionService,
)


class KnowledgeService:

    @staticmethod
    def _get_ingestion_service():
        embedding_service = EmbeddingService(
            Config.EMBEDDING_MODEL
        )

        vector_store = ChromaVectorStore(
            Config.CHROMA_PATH
        )

        return KnowledgeIngestionService(
            embedding_service,
            vector_store,
        )

    @staticmethod
    def get_document(document_id: int):
        return db.session.get(
            KnowledgeDocument,
            document_id,
        )

    @staticmethod
    def list_documents():
        return KnowledgeDocument.query.order_by(
            KnowledgeDocument.created_at.desc()
        ).all()

    @staticmethod
    def create_document(title, content, category, source=None):

        if not title or not title.strip():
            raise ValueError("Title is required.")

        if not content or not content.strip():
            raise ValueError("Content is required.")

        if not category or not category.strip():
            raise ValueError("Category is required.")

        document = KnowledgeDocument(
            title=title.strip(),
            content=content.strip(),
            category=category.strip(),
            source=source.strip() if source else None,
        )

        db.session.add(document)
        db.session.commit()

        try:
            ingestion_service = (
                KnowledgeService._get_ingestion_service()
            )

            ingestion_service.ingest_document(document)

        except Exception:
            # Database document remains available even if
            # vector indexing fails.
            print(
                f"Warning: Failed to index document "
                f"{document.id} in Chroma."
            )

        return document

    @staticmethod
    def update_document(document_id, title=None, content=None, category=None, source=None):

        document = KnowledgeService.get_document(
            document_id
        )

        if not document:
            return None

        if title is not None:
            if not title.strip():
                raise ValueError("Title is required.")
            document.title = title.strip()

        if content is not None:
            if not content.strip():
                raise ValueError("Content is required.")
            document.content = content.strip()

        if category is not None:
            if not category.strip():
                raise ValueError("Category is required.")
            document.category = category.strip()

        if source is not None:
            document.source = (
                source.strip() if source else None
            )

        db.session.commit()

        try:
            ingestion_service = (
                KnowledgeService._get_ingestion_service()
            )

            collection = (
                ingestion_service.vector_store.collection
            )

            existing = collection.get(
                where={
                    "document_id": str(document_id)
                }
            )

            existing_ids = existing.get("ids", [])

            if existing_ids:
                ingestion_service.vector_store.delete_documents(
                    existing_ids
                )

            ingestion_service.ingest_document(document)

        except Exception:
            print(
                f"Warning: Failed to re-index document "
                f"{document.id} in Chroma."
            )

        return document


    @staticmethod
    def delete_document(document_id):
        document = KnowledgeService.get_document(
            document_id
        )

        if not document:
            return False

        # Get the vector store before deleting the DB record.
        ingestion_service = (
            KnowledgeService._get_ingestion_service()
        )

        # Current implementation uses one chunk ID per chunk.
        # We first inspect the existing chunks.
        try:
            collection = (
                ingestion_service.vector_store.collection
            )
            existing = collection.get(
                where={
                    "document_id": str(document_id)
                }
            )

            existing_ids = existing.get("ids", [])

            if existing_ids:
                ingestion_service.vector_store.delete_documents(
                    existing_ids
                )

        except Exception:
            print(
                f"Warning: Failed to remove vectors "
                f"for document {document_id}."
            )

        db.session.delete(document)
        db.session.commit()

        return True