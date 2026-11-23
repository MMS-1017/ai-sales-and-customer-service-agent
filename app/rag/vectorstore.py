import os
import threading
import chromadb


class ChromaVectorStore:
    _instances: dict = {}
    _lock = threading.Lock()

    def __new__(cls, path: str, collection_name: str = "knowledge"):
        abs_path = os.path.abspath(path)
        key = (abs_path, collection_name)
        with cls._lock:
            if key not in cls._instances:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[key] = instance
            return cls._instances[key]

    def __init__(self, path: str, collection_name: str = "knowledge"):
        if getattr(self, "_initialized", False):
            return
        abs_path = os.path.abspath(path)
        self.path = abs_path
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(path=abs_path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._initialized = True

    def add_documents(self, ids, documents, embeddings, metadatas):
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )


    def delete_documents(self, ids):
        if ids:
            self.collection.delete(ids=ids)


    def get_document_ids(self, document_id: int):
        result = self.collection.get(
            where={
                "document_id": str(document_id)
            }
        )
        return result.get("ids", [])


    def delete_document(self, document_id: int):
        ids = self.get_document_ids(document_id)
        if ids:
            self.collection.delete(ids=ids)


    def search(self, query_embedding, top_k=3):
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )