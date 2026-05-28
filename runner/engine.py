"""
Engine — the dumb runtime.

Reads an orchestration .md, executes its steps over the corpus, returns output + provenance.
ZERO LLM. ZERO embeddings. Pure file reads + regex + dict lookups + template substitution.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any

from runner.composer import compose, node_as_dict
from runner.parser import (
    extract_sections,
    extract_steps,
    load_node,
)
from runner.provenance import Provenance
from runner.templater import lookup, render_template
from runner.traversal import (
    find_best_node,
    find_top_nodes,
    follow_wikilinks,
    resolve_path,
)

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "corpus"
ORCHESTRATION = ROOT / "orchestration"


def execute(orchestration_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Run an orchestration over the corpus.

    Returns:
        {
            "output": str,            # the response text
            "provenance": list[str],  # file paths that contributed
            "elapsed_ms": int,
            ...endpoint-specific fields (classification, etc.)
        }
    """
    t0 = time.monotonic()

    orch_path = ORCHESTRATION / f"{orchestration_name}.md"
    if not orch_path.exists():
        raise FileNotFoundError(f"Orchestration not found: {orch_path}")

    orch_node = load_node(orch_path, ROOT)
    steps = extract_steps(orch_node.body)

    prov = Provenance()
    prov.add(orch_node.source)

    ctx: dict[str, Any] = {"inputs": inputs}
    classification: str | None = None
    output: str = ""

    for step in steps:
        action = step.get("action")
        if action == "load":
            _do_load(step, ctx, prov)
        elif action == "load_optional":
            _do_load_optional(step, ctx, prov)
        elif action == "load_dynamic":
            _do_load_dynamic(step, ctx, prov)
        elif action == "classify":
            classification = _do_classify(step, ctx, prov)
        elif action == "walk":
            _do_walk(step, ctx, prov)
        elif action == "follow_wikilinks":
            _do_follow_wikilinks(step, ctx, prov)
        elif action == "extract":
            _do_extract(step, ctx)
        elif action == "compose":
            _do_compose(step, ctx, orch_node.body)
        elif action == "render":
            output = _do_render(step, ctx)
        else:
            raise ValueError(f"Unknown action: {action!r} in step {step}")

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    result: dict[str, Any] = {
        "output": output,
        "provenance": prov.as_list(),
        "elapsed_ms": elapsed_ms,
    }
    if classification:
        result["classification"] = classification
    return result


def _do_load(step: dict, ctx: dict, prov: Provenance) -> None:
    target = step["target"]
    var = step["as"]
    path = resolve_path(target, ROOT)
    if not path.exists():
        raise FileNotFoundError(f"load step: corpus node not found at {path}")
    node = load_node(path, ROOT)
    ctx[var] = node_as_dict(node)
    prov.add(node.source)


def _do_load_optional(step: dict, ctx: dict, prov: Provenance) -> None:
    """Load only if `when` evaluates truthy from inputs."""
    when_path = step.get("when")
    if when_path and not lookup(when_path, ctx):
        return
    target_template = step["target"]
    target = render_template(target_template, ctx)
    if not target:
        return
    path = resolve_path(target, ROOT)
    if not path.exists():
        # Optional — log but don't crash
        return
    node = load_node(path, ROOT)
    ctx[step["as"]] = node_as_dict(node)
    prov.add(node.source)


def _do_load_dynamic(step: dict, ctx: dict, prov: Provenance) -> None:
    """Load a target whose path is computed from context (e.g. matched.name).

    Chainable: if multiple load_dynamic steps share the same `as:`, the first one
    that finds a file wins. This enables fallback chains like
    `templates/specific_template` → `templates/generic_template`.
    """
    as_var = step["as"]
    if ctx.get(as_var):
        return  # already loaded by an earlier step — don't clobber
    target_template = step["target"]
    target = render_template(target_template, ctx)
    if not target:
        return
    path = resolve_path(target, ROOT)
    if not path.exists():
        return
    node = load_node(path, ROOT)
    ctx[as_var] = node_as_dict(node)
    prov.add(node.source)


def _do_classify(step: dict, ctx: dict, prov: Provenance) -> str | None:
    """
    Classify a query against a subgraph by finding the highest-scoring node.

    Sets ctx[as] to a dict with: name, source, frontmatter fields, and section text.
    Returns the classification string from the matched node's frontmatter (if any).
    """
    when_path = step.get("when")
    if when_path and not lookup(when_path, ctx):
        return None

    field = step["field"]
    subgraph_template = step["subgraph"]
    var = step["as"]

    subgraph = render_template(subgraph_template, ctx)
    if not subgraph:
        ctx[var] = {"name": "unknown", "source": "", "score": 0}
        return None

    query = str(lookup(field, ctx) or "")
    subgraph_path = CORPUS / subgraph
    if not subgraph_path.exists():
        ctx[var] = {"name": "unknown", "source": "", "score": 0}
        return None

    name_hint = None
    if step.get("name_hint_from"):
        hint_val = lookup(step["name_hint_from"], ctx)
        if hint_val:
            name_hint = str(hint_val)

    best, score = find_best_node(subgraph_path, ROOT, query, name_hint=name_hint)
    if best is None or score <= 0:
        # Fallback: load a default node if specified
        fallback = step.get("fallback")
        if fallback:
            fallback_path = resolve_path(fallback, ROOT)
            if fallback_path.exists():
                best = load_node(fallback_path, ROOT)

    if best is None:
        ctx[var] = {"name": "unknown", "source": "", "score": 0}
        return None

    ctx[var] = node_as_dict(best)
    ctx[var]["name"] = best.name  # ensure name is always present
    ctx[var]["score"] = score
    prov.add(best.source)
    return best.frontmatter.get("classification")


def _do_walk(step: dict, ctx: dict, prov: Provenance) -> None:
    """Walk a subgraph and pick the top_k matching nodes."""
    when_path = step.get("when")
    if when_path and not lookup(when_path, ctx):
        ctx[step["as"]] = []
        return

    field = step["field"]
    subgraph_template = step["subgraph"]
    var = step["as"]
    top_k = step.get("top_k", 3)

    subgraph = render_template(subgraph_template, ctx)
    if not subgraph:
        ctx[var] = []
        return

    query = str(lookup(field, ctx) or "")
    subgraph_path = CORPUS / subgraph
    if not subgraph_path.exists():
        ctx[var] = []
        return
    nodes = find_top_nodes(subgraph_path, ROOT, query, top_k=top_k)

    ctx[var] = [node_as_dict(n) for n in nodes]
    for n in nodes:
        prov.add(n.source)


def _do_follow_wikilinks(step: dict, ctx: dict, prov: Provenance) -> None:
    """Follow [[wikilinks]] from a previously-loaded node one hop deep."""
    when_path = step.get("when")
    if when_path and not lookup(when_path, ctx):
        ctx[step["as"]] = []
        return

    from_var = step["from"]
    var = step["as"]
    max_links = step.get("max_links", 5)
    source_dict = ctx.get(from_var, {})
    body = source_dict.get("body", "")
    if not body:
        ctx[var] = []
        return

    from runner.parser import Node
    fake = Node(frontmatter={}, body=body, source=source_dict.get("source", ""))
    linked = follow_wikilinks(fake, ROOT, max_links=max_links)
    ctx[var] = [node_as_dict(n) for n in linked]
    for n in linked:
        prov.add(n.source)


def _do_extract(step: dict, ctx: dict) -> None:
    """Extract named regex groups from a context field into a structured dict.

    Pure text munging — no LLM, no external service. Useful when the user supplies
    a structured-but-stringy input like "John 3:16" that the rest of the orchestration
    wants to address by part. Named groups become keys of ctx[as]; missing groups are
    omitted. If the pattern doesn't match at all, ctx[as] is an empty dict, so downstream
    steps with `when: <var>.<key>` cleanly skip.

    A normalized `<key>_slug` is auto-added for every string group: lowercased and
    whitespace-collapsed, useful for path templating and name-hint matching.
    """
    field = step["field"]
    pattern = step["pattern"]
    var = step["as"]
    flags = re.IGNORECASE if step.get("ignore_case", True) else 0

    text = str(lookup(field, ctx) or "")
    m = re.search(pattern, text, flags)
    if not m:
        ctx[var] = {}
        return

    out: dict[str, Any] = {}
    for k, v in m.groupdict().items():
        if v is None:
            continue
        out[k] = v
        if isinstance(v, str):
            out[f"{k}_slug"] = re.sub(r"\s+", "", v.lower())
    ctx[var] = out


def _do_compose(step: dict, ctx: dict, orchestration_body: str) -> None:
    template_name = step["template"]
    var = step["as"]
    ctx[var] = compose(template_name, orchestration_body, ctx)


def _do_render(step: dict, ctx: dict) -> str:
    """Final render step. `from` is the var name in context to emit."""
    return str(ctx.get(step["from"], ""))


# CLI for local testing
if __name__ == "__main__":
    import json

    if len(sys.argv) < 2:
        print("Usage: python -m runner.engine <orchestration_name> [json_inputs]")
        sys.exit(2)

    name = sys.argv[1]
    inputs_json = sys.argv[2] if len(sys.argv) > 2 else "{}"
    inputs = json.loads(inputs_json)
    result = execute(name, inputs)
    print(json.dumps(result, indent=2))
