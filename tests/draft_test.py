from app import create_app
from app.services import KnowledgeService

app = create_app()

with app.app_context():
    doc = KnowledgeService.create_document(
        title="Exchange Policy",
        content=(
            "Customers can exchange eligible products "
            "within 14 days of delivery."
        ),
        category="policy",
        source="admin",
    )

    print(doc.id)
    print(doc.title)

from app.config import Config
from app.rag import (
    EmbeddingService,
    ChromaVectorStore,
    KnowledgeRetriever,
)

embedding_service = EmbeddingService(
    Config.EMBEDDING_MODEL
)

vector_store = ChromaVectorStore(
    Config.CHROMA_PATH
)

retriever = KnowledgeRetriever(
    embedding_service,
    vector_store,
)
results = retriever.retrieve(
    "Can I exchange my product?"
)

for result in results:
    print(result["content"])
    print(result["metadata"])
    print("-" * 50)
with app.app_context():
    doc = KnowledgeService.update_document(
        document_id=5,
        content=(
            "Customers can exchange eligible products "
            "within 30 days of delivery."
        ),
    )

    print(doc.content)
results = retriever.retrieve(
    "How long do I have to exchange a product?"
)

for result in results:
    print(result["content"])
with app.app_context():
    result = KnowledgeService.delete_document(
        document_id=5
    )

    print(result)
results = retriever.retrieve(
    "How long can I exchange a product?"
)

for result in results:
    print(result["content"])