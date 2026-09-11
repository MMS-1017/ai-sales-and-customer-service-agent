from app.extensions import db
from app.models import KnowledgeDocument


class KnowledgeService:

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
    def create_document(
        title: str,
        content: str,
        category: str,
        source: str | None = None,
    ):
        if not title.strip():
            raise ValueError("Title is required.")

        if not content.strip():
            raise ValueError("Content is required.")

        document = KnowledgeDocument(
            title=title.strip(),
            content=content.strip(),
            category=category.strip(),
            source=source.strip() if source else None,
        )

        db.session.add(document)
        db.session.commit()

        return document

    @staticmethod
    def update_document(
        document_id: int,
        title: str | None = None,
        content: str | None = None,
        category: str | None = None,
        source: str | None = None,
    ):
        document = KnowledgeService.get_document(document_id)

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
            document.category = category.strip()

        if source is not None:
            document.source = source.strip()

        db.session.commit()

        return document

    @staticmethod
    def delete_document(document_id: int):
        document = KnowledgeService.get_document(document_id)

        if not document:
            return False

        db.session.delete(document)
        db.session.commit()

        return True