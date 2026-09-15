from functools import lru_cache

from sentence_transformers import SentenceTransformer


class EmbeddingService:

    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:

        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:

        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()


@lru_cache(maxsize=4)
def get_embedding_service(model_name: str) -> EmbeddingService:
    return EmbeddingService(model_name)