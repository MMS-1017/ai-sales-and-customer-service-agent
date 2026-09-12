import chromadb

class ChromaVectorStore:
    def __init__(self, path: str, collection_name: str = "knowledge"):
        self.client = chromadb.PersistentClient(path=path)

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ):
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def delete_documents(self, ids: list[str]):
        if ids:
            self.collection.delete(ids=ids)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 3,
    ):
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )