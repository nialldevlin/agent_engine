"""Retrieval module providing embedding, vector store, and search utilities."""

from .embedder import EmbeddingProvider, OllamaEmbeddingProvider
from .vector_store import SimpleVectorStore
from .retriever import Retriever, RetrievalDocument, RetrievalChunk
