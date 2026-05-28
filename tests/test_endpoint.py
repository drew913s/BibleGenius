"""
Lie detector #6: the HTTP server actually serves the inference endpoint and reports provenance.

Starts the server in a subprocess, hits /api/run, asserts the response shape.
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SERVER_PY = ROOT / "runner" / "server.py"
PORT = 18044


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(scope="module")
def server():
    if not SERVER_PY.exists():
        pytest.skip("runner/server.py not built")

    proc = subprocess.Popen(
        [sys.executable, str(SERVER_PY), "--port", str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for _ in range(50):
        if _port_open(PORT):
            break
        time.sleep(0.2)
    else:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=2)
        pytest.fail(
            f"Server failed to start on port {PORT}.\n"
            f"stdout: {stdout.decode()[:500]}\nstderr: {stderr.decode()[:500]}"
        )

    yield f"http://127.0.0.1:{PORT}"
    proc.terminate()
    proc.wait(timeout=5)


def test_health(server):
    import httpx
    r = httpx.get(f"{server}/health", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("llm") == "none"
    assert body["corpus_nodes"] > 30000, f"Expected 31k+ corpus nodes, got {body['corpus_nodes']}"


def test_run_endpoint_verse_lookup(server):
    import httpx
    r = httpx.post(
        f"{server}/api/run",
        json={"orchestration": "verse_lookup", "inputs": {"question": "John 3:16"}},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert "output" in body
    assert "provenance" in body
    assert isinstance(body["provenance"], list)
    assert "corpus/verses/john/3_16.md" in body["provenance"], (
        f"Provenance must cite the actual verse file. Got: {body['provenance']}"
    )
    assert "elapsed_ms" in body


def test_run_endpoint_topical_search(server):
    import httpx
    r = httpx.post(
        f"{server}/api/run",
        json={"orchestration": "topical_search",
              "inputs": {"question": "verses about forgiveness"}},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert "corpus/topics/forgiveness.md" in body["provenance"], (
        f"Expected topic file in provenance. Got: {body['provenance']}"
    )


def test_corpus_endpoint(server):
    import httpx
    r = httpx.get(f"{server}/api/corpus", timeout=5)
    assert r.status_code == 200
    tree = r.json()
    assert "orchestration" in tree
    assert "verses" in tree
    assert "books" in tree
    assert "topics" in tree
    assert len(tree["verses"]) > 30000


def test_source_endpoint_serves_md(server):
    import httpx
    r = httpx.get(f"{server}/api/source",
                  params={"path": "corpus/verses/john/3_16.md"}, timeout=5)
    assert r.status_code == 200
    assert "everlasting life" in r.text.lower() or "begotten" in r.text.lower()


def test_source_endpoint_blocks_traversal(server):
    import httpx
    r = httpx.get(f"{server}/api/source",
                  params={"path": "../../../etc/passwd"}, timeout=5)
    assert r.status_code in (400, 404)
