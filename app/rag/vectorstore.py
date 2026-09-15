import chromadb


class ChromaVectorStore:

    def __init__(self, path: str, collection_name: str = "knowledge"):

        self.client = chromadb.PersistentClient(path=path) #Persistent:  save data to the local disk so that it will not be lost when the Python script finishes running.

        self.collection = self.client.get_or_create_collection(
            name = collection_name,
            metadata = {"hnsw:space": "cosine"},
        )

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