from __future__ import annotations

import faiss
import numpy as np

from rag.embeddings import LocalEmbeddings


class SchemaVectorStore:
    def __init__(self, index: faiss.IndexFlatIP, documents: list[str], embeddings: LocalEmbeddings) -> None:
        self.index = index
        self.documents = documents
        self.embeddings = embeddings

    @classmethod
    def from_documents(cls, documents: list[str], embeddings: LocalEmbeddings) -> "SchemaVectorStore":
        vectors = np.array(embeddings.embed_documents(documents), dtype=np.float32)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        return cls(index=index, documents=documents, embeddings=embeddings)

    def search(self, query: str, top_k: int) -> list[str]:
        query_vector = np.array([self.embeddings.embed_query(query)], dtype=np.float32)
        _, indices = self.index.search(query_vector, top_k)
        return [self.documents[i] for i in indices[0] if i >= 0]

    def search_with_scores(self, query: str, top_k: int) -> tuple[list[str], list[float]]:
        query_vector = np.array([self.embeddings.embed_query(query)], dtype=np.float32)
        scores, indices = self.index.search(query_vector, top_k)
        docs: list[str] = []
        out_scores: list[float] = []
        for idx, score in zip(indices[0], scores[0], strict=False):
            if idx < 0:
                continue
            docs.append(self.documents[idx])
            out_scores.append(float(score))
        return docs, out_scores

    @property
    def document_count(self) -> int:
        return len(self.documents)
