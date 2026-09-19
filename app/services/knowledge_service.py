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
            return {"success": False, "error": "Title is required."}

        if not content:
            return {"success": False, "error": "Content is required."}

        try:
            document = KnowledgeDocument(
                title=title,
                content=content,
                category=category,
                source=source.strip() if source else None,
            )

            db.session.add(document)

            # Flush assigns the database ID without committing.
            db.session.flush()

            ingestion_service = KnowledgeService._get_ingestion_service()

            chunks = ingestion_service.ingest_document(document)

            # Commit only after vector ingestion succeeds.
            db.session.commit()

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

        old_values = {
            "title": document.title,
            "content": document.content,
            "category": document.category,
            "source": document.source,
        }

        try:
            ingestion_service = KnowledgeService._get_ingestion_service()
            vector_store = ingestion_service.vector_store

            old_ids = vector_store.get_document_ids(document.id)

            document.title = title
            document.content = content
            document.category = category
            document.source = source.strip() if source else None

            # Index the new content before committing the database change.
            # New chunks use deterministic IDs, so existing chunk IDs are
            # updated in place by Chroma upsert.
            chunks = ingestion_service.ingest_document(document)

            new_ids = {
                f"doc-{document.id}-chunk-{index}"
                for index in range(chunks)
            }
            obsolete_ids = [
                vector_id for vector_id in old_ids
                if vector_id not in new_ids
            ]

            # Remove only obsolete chunks after the new content has been
            # successfully indexed.
            vector_store.delete_documents(obsolete_ids)

            db.session.commit()

            return {
                "success": True,
                "document_id": document.id,
                "chunks": chunks,
            }

        except Exception:
            db.session.rollback()

            # Restore the in-memory ORM object to its previous values so a
            # later recovery/rebuild operation sees the database state.
            document.title = old_values["title"]
            document.content = old_values["content"]
            document.category = old_values["category"]
            document.source = old_values["source"]

            return {
                "success": False,
                "error": (
                    "Failed to update knowledge document. "
                    "The vector store may require a rebuild."
                ),
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