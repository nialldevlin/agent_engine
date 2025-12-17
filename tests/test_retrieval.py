import os
from pathlib import Path

from agent_engine.retrieval.embedder import EmbeddingProvider
from agent_engine.retrieval.vector_store import SimpleVectorStore
from agent_engine.retrieval.retriever import Retriever
from agent_engine.runtime.context import ContextAssembler
from agent_engine.schemas import (
    ContextProfile,
    ContextProfileSource,
    Task,
    TaskSpec,
    TaskMode,
)


class StubEmbedder(EmbeddingProvider):
    def embed(self, texts):
        # Simple embedding: length-based vector
        return [[len(t), 1.0, 0.0] for t in texts]


def test_context_assembler_with_rag(tmp_path: Path):
    workspace = tmp_path
    file_path = workspace / "sample.txt"
    file_path.write_text("Hello world\nThis is a test document for RAG.", encoding="utf-8")

    store = SimpleVectorStore(str(workspace / "index.json"))
    retriever = Retriever(
        workspace_root=str(workspace),
        embedder=StubEmbedder(),
        store=store,
        include_extensions=[".txt"],
    )

    profile = ContextProfile(
        id="rag_profile",
        max_tokens=500,
        retrieval_policy="semantic",
        sources=[ContextProfileSource(store="task", tags=[])],
        metadata={"rag_enabled": True, "rag_top_k": 3},
    )

    spec = TaskSpec(task_spec_id="spec1", request="test document", mode=TaskMode.ANALYSIS_ONLY)
    task = Task(
        task_id="t1",
        spec=spec,
        task_memory_ref="task",
        project_memory_ref="project",
        global_memory_ref="global",
    )

    assembler = ContextAssembler(
        context_profiles={"rag_profile": profile},
        workspace_root=str(workspace),
        retriever=retriever,
    )

    ctx = assembler.build_context_for_profile(task, profile)
    assert ctx.items, "RAG should add retrieval chunks"
    metadata = assembler.get_context_metadata(ctx)
    assert "retrieval" in metadata
    assert metadata["retrieval"]["rag_enabled"] is True
