from app.rag.embeddings import EmbeddingService
from app.rag.vectorstore import ChromaVectorStore


class KnowledgeIngestionService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: ChromaVectorStore,
        chunk_size: int = 700,
        chunk_overlap: int = 100,
    ):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _chunk_text(self, text: str) -> list[str]:
        text = text.strip()

        if not text:
            return []

        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            start = end - self.chunk_overlap

        return chunks

    def ingest_document(self, document):
        chunks = self._chunk_text(document.content)

        if not chunks:
            return 0

        ids = [
            f"doc-{document.id}-chunk-{index}"
            for index in range(len(chunks))
        ]

        metadatas = [
            {
                "document_id": str(document.id),
                "title": document.title,
                "category": document.category,
                "source": document.source or "",
                "chunk_index": index,
            }
            for index in range(len(chunks))
        ]

        embeddings = self.embedding_service.embed_documents(chunks)

        self.vector_store.add_documents(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        return len(chunks)

    def delete_document(self, document_id: int, chunk_count: int):
        ids = [
            f"doc-{document_id}-chunk-{index}"
            for index in range(chunk_count)
        ]

        self.vector_store.delete_documents(ids)

    def ingest_all(self, documents):
        total_chunks = 0

        for document in documents:
            total_chunks += self.ingest_document(document)

        return total_chunks