from app.extensions import db
from app.models import KnowledgeDocument


def test_knowledge_create_update_delete(client, app):
    response = client.post(
        "/admin/knowledge/create",
        data={
            "title": "Test Shipping Policy",
            "content": "Test orders are shipped within 2 business days.",
            "category": "Shipping",
            "source": "test",
        },
        follow_redirects=False,
    )

    assert response.status_code in (200, 302)

    with app.app_context():
        document = KnowledgeDocument.query.filter_by(
            title="Test Shipping Policy"
        ).first()

        assert document is not None
        document_id = document.id

    response = client.post(
        f"/admin/knowledge/{document_id}/edit",
        data={
            "title": "Updated Shipping Policy",
            "content": "Test orders are shipped within 5 business days.",
            "category": "Shipping",
            "source": "test",
        },
        follow_redirects=False,
    )

    assert response.status_code in (200, 302)

    with app.app_context():
        document = db.session.get(KnowledgeDocument, document_id)

        assert document is not None
        assert document.title == "Updated Shipping Policy"
        assert "5 business days" in document.content

    response = client.post(
        f"/admin/knowledge/{document_id}/delete",
        follow_redirects=False,
    )

    assert response.status_code in (200, 302)

    with app.app_context():
        document = db.session.get(KnowledgeDocument, document_id)

        assert document is None