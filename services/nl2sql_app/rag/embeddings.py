from __future__ import annotations

from sentence_transformers import SentenceTransformer


class LocalEmbeddings:
    def __init__(self, model_name: str) -> None:
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, docs: list[str]) -> list[list[float]]:
        vectors = self.model.encode(docs, convert_to_numpy=True, normalize_embeddings=True)
        return vectors.tolist()

    def embed_query(self, query: str) -> list[float]:
        vector = self.model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
        return vector.tolist()
