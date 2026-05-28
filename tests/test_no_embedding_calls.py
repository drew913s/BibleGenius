"""
Lie detector #2: assert runner/ never computes embeddings or vector similarity.

Embedding-based retrieval is a sneaky way to smuggle an LLM in. This grep catches it.
"""
import re
from pathlib import Path

RUNNER_DIR = Path(__file__).parent.parent / "runner"

FORBIDDEN_PATTERNS = [
    r"\.encode\s*\(", r"embedding", r"embed_documents", r"embed_query",
    r"cosine_similarity", r"vector_search", r"semantic_search",
    r"\.similarity\s*\(", r"faiss\.", r"chroma", r"pinecone",
    r"weaviate", r"qdrant", r"milvus",
]


def test_no_embedding_calls_in_runner():
    py_files = list(RUNNER_DIR.glob("*.py"))
    assert py_files, f"No Python files found in {RUNNER_DIR}"

    violations = []
    for py in py_files:
        text = py.read_text()
        stripped = re.sub(r"#.*", "", text)
        stripped = re.sub(r'""".*?"""', "", stripped, flags=re.DOTALL)
        stripped = re.sub(r"'''.*?'''", "", stripped, flags=re.DOTALL)
        for pattern in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, stripped, re.IGNORECASE):
                line_no = stripped[: match.start()].count("\n") + 1
                violations.append((py.name, line_no, pattern, match.group(0)))

    assert not violations, (
        f"Embedding/similarity calls found in runner/ — architecture violated:\n"
        + "\n".join(
            f"  {name}:{line} matched {pat!r} -> {snippet!r}"
            for name, line, pat, snippet in violations
        )
    )
