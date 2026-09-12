from app import create_app
from app.config import Config
from app.models import KnowledgeDocument
from app.rag import (
    EmbeddingService,
    ChromaVectorStore,
    KnowledgeIngestionService,
    KnowledgeRetriever,
)

app = create_app()
with app.app_context():
    embedding_service = EmbeddingService(
        Config.EMBEDDING_MODEL
    )

    vector_store = ChromaVectorStore(
        Config.CHROMA_PATH
    )

    ingestion_service = KnowledgeIngestionService(
        embedding_service,
        vector_store,
    )

    documents = KnowledgeDocument.query.all()

    for document in documents:
        chunks = ingestion_service.ingest_document(document)
        print(document.title, "->", chunks, "chunks")

retriever = KnowledgeRetriever(
    embedding_service,
    vector_store,
)

results = retriever.retrieve(
    "How long do I have to return a product?"
)
for result in results:
    print("CONTENT:")
    print(result["content"])
    print("METADATA:")
    print(result["metadata"])
    print("DISTANCE:")
    print(result["distance"])
    print("-" * 50)