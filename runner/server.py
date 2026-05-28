"""
HTTP server for Markdown Language Model.

One generic inference endpoint (`POST /api/run`) plus corpus-browsing endpoints.
Frontends pick which orchestration to invoke. The engine reads it from disk and executes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import HTMLResponse, PlainTextResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from runner.engine import execute, CORPUS, ORCHESTRATION  # noqa: E402
from runner.parser import load_node  # noqa: E402

FRONTEND = ROOT / "frontend" / "index.html"

app = FastAPI(title="Markdown Language Model", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    orchestration: str
    inputs: dict[str, Any] = {}


@app.get("/", response_class=HTMLResponse)
async def serve_frontend() -> HTMLResponse:
    if not FRONTEND.exists():
        raise HTTPException(status_code=404, detail=f"Frontend not built: {FRONTEND}")
    return HTMLResponse(content=FRONTEND.read_text(encoding="utf-8"))


@app.post("/api/run")
async def run(req: RunRequest) -> dict[str, Any]:
    """Single inference endpoint. Pick an orchestration, pass inputs, get output + provenance."""
    try:
        result = execute(req.orchestration, req.inputs)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    return {
        "output": result["output"],
        "provenance": result["provenance"],
        "elapsed_ms": result["elapsed_ms"],
        "classification": result.get("classification"),
    }


@app.get("/api/orchestrations")
async def list_orchestrations() -> list[dict[str, Any]]:
    """List available orchestrations with their frontmatter (name, trigger, inputs)."""
    out: list[dict[str, Any]] = []
    for md in sorted(ORCHESTRATION.glob("*.md")):
        node = load_node(md, ROOT)
        out.append({
            "name": node.frontmatter.get("name", md.stem),
            "filename": md.stem,
            "frontmatter": node.frontmatter,
            "source": node.source,
        })
    return out


@app.get("/api/corpus")
async def list_corpus() -> dict[str, list[str]]:
    """List every markdown node under corpus/ and orchestration/, grouped by category."""
    nodes: dict[str, list[str]] = {}
    for md in sorted(CORPUS.rglob("*.md")):
        rel = str(md.relative_to(ROOT))
        category = md.relative_to(CORPUS).parts[0] if md.relative_to(CORPUS).parts else "root"
        nodes.setdefault(category, []).append(rel)
    for md in sorted(ORCHESTRATION.glob("*.md")):
        nodes.setdefault("orchestration", []).append(str(md.relative_to(ROOT)))
    return nodes


@app.get("/api/source")
async def get_source(path: str) -> PlainTextResponse:
    """Return the raw markdown of a corpus/orchestration file. Path stays inside the project."""
    full = (ROOT / path).resolve()
    if not full.is_relative_to(ROOT.resolve()):
        raise HTTPException(status_code=400, detail="Path escape blocked")
    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail=f"Not found: {path}")
    if full.suffix != ".md":
        raise HTTPException(status_code=400, detail="Only .md files served")
    return PlainTextResponse(content=full.read_text(encoding="utf-8"))


@app.get("/health")
async def health() -> dict[str, Any]:
    corpus_nodes = sum(1 for _ in CORPUS.rglob("*.md"))
    orchestrations = sum(1 for _ in ORCHESTRATION.glob("*.md"))
    return {
        "status": "ok",
        "corpus_nodes": corpus_nodes,
        "orchestrations": orchestrations,
        "engine": "markdown-language-model",
        "llm": "none",
    }


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8042)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    print(f"Markdown Language Model starting on http://{args.host}:{args.port}")
    print(f"Corpus: {CORPUS}")
    print(f"Orchestrations: {ORCHESTRATION}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
