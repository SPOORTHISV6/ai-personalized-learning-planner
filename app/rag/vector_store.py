import os
import json
import re

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


# Concept aliases support different ways of referring to a topic.
# Generic concepts such as "class" and "object" are intentionally
# excluded from strong concept boosts to avoid promoting broad titles.
CONCEPT_ALIASES = {
    "constructor": [
        "constructor",
        "__init__",
        "initializer",
    ],
    "self": [
        "self parameter",
        "self",
    ],
    "encapsulation": [
        "encapsulation",
        "data hiding",
        "private attributes",
        "private variables",
    ],
    "inheritance": [
        "inheritance",
        "parent class",
        "child class",
        "base class",
        "derived class",
    ],
    "normalization": [
        "normalization",
        "normalisation",
    ],
    "1nf": [
        "1nf",
        "first normal form",
    ],
    "2nf": [
        "2nf",
        "second normal form",
    ],
    "3nf": [
        "3nf",
        "third normal form",
    ],
    "bcnf": [
        "bcnf",
        "boyce codd normal form",
    ],
    "aggregate_functions": [
        "aggregate functions",
        "aggregate function",
    ],
    "group_by": [
        "group by",
        "having",
    ],
    "order_by": [
        "order by",
        "limit",
    ],
    "inner_join": [
        "inner join",
    ],
    "left_join": [
        "left join",
        "left outer join",
    ],
    "right_join": [
        "right join",
        "right outer join",
    ],
    "full_join": [
        "full join",
        "full outer join",
    ],
}


class VectorStore:
    """FAISS vector store with semantic and concept-aware reranking."""

    _model_cache = {}

    def __init__(self, model_name=MODEL_NAME):
        self.model_name = model_name

        if model_name not in self._model_cache:
            print("\n[Vector Store] Loading embedding model...")
            self._model_cache[model_name] = SentenceTransformer(
                model_name
            )
        else:
            print("\n[Vector Store] Using cached embedding model...")

        self.model = self._model_cache[model_name]
        self.index = None
        self.chunks = []

    @staticmethod
    def _normalize_chunk(chunk):
        if not isinstance(chunk, dict):
            return {
                "text": str(chunk),
                "section_title": "General",
            }

        normalized = dict(chunk)

        if "text" not in normalized and "content" in normalized:
            normalized["text"] = normalized["content"]

        if "section_title" not in normalized:
            normalized["section_title"] = normalized.get(
                "section",
                normalized.get("title", "General"),
            )

        return normalized

    @staticmethod
    def _normalize_phrase(text):
        return " ".join(
            re.findall(r"[a-z0-9]+", str(text).casefold())
        )

    @staticmethod
    def _tokens(text):
        stop_words = {
            "a", "an", "and", "the", "of", "to", "for",
            "in", "on", "with", "is", "are", "was", "were",
            "what", "how", "why", "explain", "examples",
            "example", "basics", "topic", "topics", "using",
            "about", "from", "into", "that", "this",
        }

        tokens = set(
            re.findall(r"[a-z0-9]+", str(text).casefold())
        )

        return tokens - stop_words

    @staticmethod
    def _contains_phrase(text, phrase):
        """Check for a complete normalized phrase."""
        text = " " + VectorStore._normalize_phrase(text) + " "
        phrase = " " + VectorStore._normalize_phrase(phrase) + " "

        return phrase.strip() in text.strip()

    def build(self, chunks):
        if not chunks:
            raise ValueError(
                "No chunks available to build vector store."
            )

        self.chunks = [
            self._normalize_chunk(chunk)
            for chunk in chunks
        ]

        texts = [
            str(chunk.get("text", ""))
            for chunk in self.chunks
        ]

        if any(not text.strip() for text in texts):
            raise ValueError(
                "One or more chunks contain empty text."
            )

        print(
            f"[Vector Store] Generating embeddings for "
            f"{len(texts)} chunks..."
        )

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        embeddings = np.asarray(
            embeddings,
            dtype=np.float32,
        )

        self.index = faiss.IndexFlatIP(
            embeddings.shape[1]
        )

        self.index.add(embeddings)

        print(
            f"[Vector Store] FAISS index created with "
            f"{self.index.ntotal} vectors."
        )

    def save(self, index_path, metadata_path):
        if self.index is None:
            raise ValueError(
                "Vector store has not been built."
            )

        os.makedirs(
            os.path.dirname(index_path) or ".",
            exist_ok=True,
        )

        os.makedirs(
            os.path.dirname(metadata_path) or ".",
            exist_ok=True,
        )

        faiss.write_index(
            self.index,
            index_path,
        )

        with open(
            metadata_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                self.chunks,
                file,
                ensure_ascii=False,
                indent=2,
            )

        print("[Vector Store] Vector store saved.")
        print(f"[Vector Store] Index: {index_path}")
        print(f"[Vector Store] Metadata: {metadata_path}")

    def load(self, index_path, metadata_path):
        if not os.path.exists(index_path):
            raise FileNotFoundError(
                f"FAISS index not found: {index_path}"
            )

        if not os.path.exists(metadata_path):
            raise FileNotFoundError(
                f"Metadata file not found: {metadata_path}"
            )

        self.index = faiss.read_index(index_path)

        with open(
            metadata_path,
            "r",
            encoding="utf-8",
        ) as file:
            metadata = json.load(file)

        if isinstance(metadata, dict):
            if "chunks" not in metadata:
                raise ValueError(
                    "Metadata JSON does not contain 'chunks'."
                )

            metadata = metadata["chunks"]

        if not isinstance(metadata, list):
            raise ValueError(
                "Unsupported metadata format."
            )

        self.chunks = [
            self._normalize_chunk(chunk)
            for chunk in metadata
        ]

        if self.index.ntotal != len(self.chunks):
            raise ValueError(
                "FAISS index/vector count does not match metadata. "
                f"Vectors={self.index.ntotal}, "
                f"Chunks={len(self.chunks)}"
            )

        print("[Vector Store] Existing FAISS index loaded.")
        print(f"[Vector Store] Vectors: {self.index.ntotal}")
        print(f"[Vector Store] Chunks: {len(self.chunks)}")

    def _title_boost(self, query, title):
        """
        Boost section titles that explicitly match query concepts.

        Semantic similarity remains important, but specific titles
        should not lose to generic sections simply because the query
        mentions several concepts at once.
        """

        query_norm = self._normalize_phrase(query)
        title_norm = self._normalize_phrase(title)

        query_tokens = self._tokens(query)
        title_tokens = self._tokens(title)

        if not title_norm:
            return 0.0

        boost = 0.0

        # Small bonus for lexical overlap.
        if query_tokens and title_tokens:
            overlap = (
                len(query_tokens & title_tokens)
                / len(title_tokens)
            )

            boost += min(0.04, overlap * 0.04)

        # Stronger bonus for a complete title phrase in the query.
        # For example, "Classes and Objects".
        if title_norm and title_norm in query_norm:
            boost += 0.18

        # Give a controlled boost when a specific concept appears
        # in both the query and the section title.
        matched_concepts = 0

        for aliases in CONCEPT_ALIASES.values():
            query_matches = any(
                self._contains_phrase(query_norm, alias)
                for alias in aliases
            )

            title_matches = any(
                self._contains_phrase(title_norm, alias)
                for alias in aliases
            )

            if query_matches and title_matches:
                matched_concepts += 1

        if matched_concepts:
            boost += min(
                0.30,
                0.27 + (matched_concepts - 1) * 0.015,
            )

        return min(boost, 0.34)

    def search(self, query, top_k=3):
        if self.index is None:
            raise ValueError(
                "Vector store is not initialized."
            )

        if not self.chunks:
            raise ValueError(
                "No chunk metadata available."
            )

        if not isinstance(query, str) or not query.strip():
            return []

        if top_k <= 0:
            return []

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype=np.float32,
        )

        # Search all indexed chunks before reranking.
        scores, indices = self.index.search(
            query_embedding,
            self.index.ntotal,
        )

        results = []

        for score, chunk_index in zip(
            scores[0],
            indices[0],
        ):
            chunk_index = int(chunk_index)

            if (
                chunk_index < 0
                or chunk_index >= len(self.chunks)
            ):
                continue

            result = self.chunks[chunk_index].copy()

            raw_score = float(score)
            title = str(
                result.get("section_title", "")
            )

            title_boost = self._title_boost(
                query,
                title,
            )

            result["raw_similarity_score"] = raw_score
            result["title_match_boost"] = title_boost
            result["similarity_score"] = (
                raw_score + title_boost
            )

            results.append(result)

        results.sort(
            key=lambda item: item["similarity_score"],
            reverse=True,
        )

        return results[:min(top_k, len(results))]