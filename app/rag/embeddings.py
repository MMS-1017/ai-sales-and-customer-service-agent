# from sentence_transformers import SentenceTransformer

# class EmbeddingService:

#     def __init__(self, model_name: str):
#         self.model = SentenceTransformer(model_name)

#     def embed_documents(self, texts: list[str]) -> list[list[float]]:
#         embeddings = self.model.encode(texts, normalize_embeddings=True)
#         return embeddings.tolist()

#     def embed_query(self, text: str) -> list[float]:
#         embedding = self.model.encode(text, normalize_embeddings=True)
#         return embedding.tolist()


# # Module-level cache: created fresh each time the interpreter starts.
# # Avoids "cannot schedule new futures after interpreter shutdown" that
# # occurs when @lru_cache keeps a stale SentenceTransformer thread-pool
# # alive across Flask's debug reloader restarts.
# _embedding_cache: dict[str, EmbeddingService] = {}

# def get_embedding_service(model_name: str) -> EmbeddingService:
#     if model_name not in _embedding_cache:
#         print(f"Initializing embedding model: {model_name}")
#         _embedding_cache[model_name] = EmbeddingService(model_name)
#     return _embedding_cache[model_name]

from functools import lru_cache
from sentence_transformers import SentenceTransformer

class EmbeddingService:

    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        embedding = self.model.encode(text, normalize_embeddings=True,)
        return embedding.tolist()

@lru_cache(maxsize=4)
def get_embedding_service(model_name: str,) -> EmbeddingService:
    print(f"Initializing embedding model: {model_name}")
    return EmbeddingService(model_name)