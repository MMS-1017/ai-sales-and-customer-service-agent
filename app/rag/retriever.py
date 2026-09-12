from app.rag.embeddings import EmbeddingService
from app.rag.vectorstore import ChromaVectorStore


class KnowledgeRetriever:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: ChromaVectorStore,
    ):
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def retrieve(self, query: str, top_k: int = 3):
        query_embedding = self.embedding_service.embed_query(query)

        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        retrieved = []

        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        ):
            retrieved.append(
                {
                    "content": document,
                    "metadata": metadata,
                    "distance": distance,
                }
            )

        return retrieved