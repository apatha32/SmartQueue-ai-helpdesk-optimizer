"""
Hybrid retrieval: BM25 + dense (ChromaDB) via EnsembleRetriever,
followed by cross-encoder reranking to top-6 results.

Embeddings: paraphrase-multilingual-MiniLM-L12-v2  (384-dim, 50+ languages)
Reranker:   cross-encoder/ms-marco-MiniLM-L-6-v2
"""

import os
from functools import lru_cache
from typing import List, Optional

import chromadb
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder

_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_TOP_K_FETCH = 20   # candidates from ensemble before reranking
_TOP_K_FINAL = 6    # docs returned after cross-encoder reranking

# In-memory BM25 corpus — updated on ingest
_bm25_corpus: List[Document] = []


@lru_cache(maxsize=1)
def _embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=_EMBED_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache(maxsize=1)
def _cross_encoder() -> CrossEncoder:
    return CrossEncoder(_RERANK_MODEL)


def _chroma() -> Chroma:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8001"))
    client = chromadb.HttpClient(host=host, port=port)
    return Chroma(
        client=client,
        collection_name="dtq_knowledge",
        embedding_function=_embeddings(),
    )


async def ingest_documents(
    texts: List[str],
    metadatas: Optional[List[dict]] = None,
) -> int:
    """Add documents to ChromaDB (dense index) and in-memory BM25 corpus."""
    global _bm25_corpus
    metas = metadatas or [{}] * len(texts)
    docs = [Document(page_content=t, metadata=m) for t, m in zip(texts, metas)]
    store = _chroma()
    await store.aadd_documents(docs)
    _bm25_corpus.extend(docs)
    return len(docs)


async def hybrid_retrieve_rerank(
    query: str,
    hyde_text: Optional[str] = None,
) -> List[Document]:
    """
    1. BM25 retrieval on original query (keyword matching).
    2. Dense retrieval on HyDE-expanded text (semantic matching).
    3. EnsembleRetriever merges results (weights 0.4 / 0.6).
    4. Cross-encoder reranks candidates to top-_TOP_K_FINAL.
    """
    store = _chroma()
    dense_query = hyde_text or query
    dense_retriever = store.as_retriever(search_kwargs={"k": _TOP_K_FETCH})

    if _bm25_corpus:
        bm25 = BM25Retriever.from_documents(_bm25_corpus)
        bm25.k = _TOP_K_FETCH
        ensemble = EnsembleRetriever(
            retrievers=[bm25, dense_retriever],
            weights=[0.4, 0.6],
        )
        candidates = await ensemble.ainvoke(dense_query)
    else:
        candidates = await dense_retriever.ainvoke(dense_query)

    if not candidates:
        return []

    encoder = _cross_encoder()
    pairs = [(query, doc.page_content) for doc in candidates]
    scores = encoder.predict(pairs)
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    return [doc for _, doc in ranked[:_TOP_K_FINAL]]
