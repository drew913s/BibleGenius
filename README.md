# Bible Genius

> A deterministic King James Bible concordance. **31,100 verses, zero LLM at inference time, ~30 ms per query, every word traceable to a file on disk.**

Bible Genius is a working implementation of the [Markdown Language Model](https://github.com/drew913s/MarkdownLanguageModel) framework over the entire King James Bible. The whole Bible is atomized into 31,100 markdown files — one per verse — plus 66 book index nodes and 30 curated topic clusters. The runtime walks the graph by keyword scoring and exact-path resolution. No model. No GPU. No tokenizer. No embeddings. No API calls.

If the runtime returns a verse, that verse lives in a real `.md` file you can open, read, edit, or delete. Delete the file, the runtime stops returning it. There is no hallucination because there is no inference — only retrieval and template substitution.

## Run it

```bash
pip install fastapi uvicorn pydantic pyyaml httpx pytest

# Build the corpus (one-time — emits ~31k markdown nodes from a KJV JSON source)
python3 build/atomize_kjv.py path/to/kjv.json
python3 build/atomize_topics.py

# Verify the architectural contract — 6 lie detectors + scenario coverage = 20 tests
python3 -m pytest tests/ -v

# Serve it
python3 runner/server.py
# → http://localhost:8042
```

Type `John 3:16`, get John 3:16 in 30 ms with the corpus file cited in the right panel. Type `verses about forgiveness`, get the 15 most forgiveness-bearing verses from the entire KJV, every link clickable.

## Example queries

| Query                                    | Returns                                   | Cited file                            |
|------------------------------------------|-------------------------------------------|---------------------------------------|
| `John 3:16`                              | For God so loved the world…              | `corpus/verses/john/3_16.md`          |
| `Genesis 1:1`                            | In the beginning God created…            | `corpus/verses/genesis/1_1.md`        |
| `3 John 1:13`                            | I had many things to write…              | `corpus/verses/3john/1_13.md`         |
| `Matt 5:3`                               | Blessed are the poor in spirit…          | `corpus/verses/matthew/5_3.md`        |
| `1 Samuel 17:45`                         | Then said David to the Philistine…       | `corpus/verses/1samuel/17_45.md`      |
| `Psalm 23:1`                             | The Lord is my shepherd…                  | `corpus/verses/psalms/23_1.md`        |
| `what does the bible say about forgiveness` | Top 15 forgiveness verses, KJV         | `corpus/topics/forgiveness.md` + 15 verse files |
| `the kingdom of heaven`                  | Top 15 kingdom verses                     | `corpus/topics/kingdom.md` + 15 verse files |
| `gibberish nonsense not a reference`     | "I don't know" — honest empty result      | `corpus/identity/dont_know.md`        |

## The architectural contract (six lie detectors)

Inherited from the [Markdown Language Model](https://github.com/drew913s/MarkdownLanguageModel) framework. Every test must pass. If any fails, the architecture is compromised and the "zero LLM at inference" claim is a lie:

1. **No LLM imports** in `runner/*.py` (allowlist test)
2. **No embedding / similarity calls** in `runner/*.py`
3. **No shelling out to model binaries or APIs** in `runner/*.py`
4. **Every response cites real, existing corpus files**
5. **Deleting a corpus file visibly changes behavior** (proves the graph is load-bearing)
6. **The HTTP API serves the inference endpoint and returns provenance**

Plus 14 scenario tests asserting that specific verses are routed correctly: `John 3:16` cites `corpus/verses/john/3_16.md`, `3 John 1:13` cites `corpus/verses/3john/1_13.md`, and the "I don't know" fallback fires for unmatched queries.

## How it works

```
inputs.question  →  extract regex (book, chapter, verse)
                 →  classify against corpus/books/ (66 nodes, name-hint disambiguation)
                 →  load_dynamic verses/{book_slug}/{chap}_{verse}.md
                 →  template substitution
                 →  output + provenance
```

For verse lookups, classification narrows to the right book in microseconds; the actual verse is then loaded by direct path. For topical queries, classification picks one of the 30 pre-built topic clusters; the runtime follows the cluster's `[[wikilinks]]` to surface scripture.

The orchestration files (`orchestration/*.md`) are the only thing that defines behavior. The runtime is generic — it walks markdown.

### The three orchestrations

- **`verse_lookup`** — answers verse references like "John 3:16"
- **`topical_search`** — answers topical queries like "verses about faith"
- **`cross_reference`** — given a verse, returns its adjacent verses

## Repository structure

```
BibleGenius/
├── README.md
├── runner/                  # generic MLM runtime — DSL extended with `extract` + name-hint classify
│   ├── engine.py
│   ├── parser.py
│   ├── traversal.py         # mtime-cached parsed nodes (warm-cache traversal of 31k files in ~2 ms)
│   ├── composer.py
│   ├── templater.py
│   ├── provenance.py
│   └── server.py
├── orchestration/
│   ├── verse_lookup.md
│   ├── topical_search.md
│   └── cross_reference.md
├── corpus/
│   ├── identity/            # voice + don't-know fallback
│   ├── books/               # 66 book index nodes
│   ├── topics/              # 30 topic clusters with [[wikilinks]] to verses
│   └── verses/<book>/<chapter>_<verse>.md   # 31,100 verse nodes
├── build/                   # build-time atomizers (NEVER imported by the runtime)
│   ├── atomize_kjv.py
│   └── atomize_topics.py
├── frontend/
│   └── index.html           # single-page UI with provenance viewer
└── tests/                   # 6 lie detectors + 14 Bible-Genius scenarios
```

## Extending the corpus

**Add a topic.** Open `build/atomize_topics.py`, append a topic dict to the `TOPICS` list (slug, name, keywords, word-forms), re-run the script. A new cluster node appears under `corpus/topics/` with wikilinks to the 15 best-matching verses.

**Swap the translation.** Replace the KJV JSON source. Re-run `build/atomize_kjv.py`. The runtime doesn't care which translation — it walks whatever files exist.

**Add a new orchestration.** Write a new `.md` under `orchestration/`. The runtime auto-discovers it. The DSL actions available are `load`, `load_optional`, `load_dynamic`, `classify`, `walk`, `follow_wikilinks`, `extract`, `compose`, `render`.

## Performance

| Metric                     | Value                            |
|----------------------------|----------------------------------|
| Verses indexed             | 31,100 (full KJV, all 66 books) |
| Total corpus nodes         | 31,198                           |
| Cold-cache verse lookup    | ~30 ms                           |
| Warm-cache verse lookup    | ~2 ms                            |
| Warm-cache topical search  | ~5–15 ms                         |
| Disk size of corpus        | ~122 MB                          |
| Memory at idle             | <100 MB                          |
| LLM cost per query         | $0                               |
| Tokens emitted             | 0                                |
| GPU required               | none                             |

## Why this exists

To demonstrate, on a non-trivial corpus, that a real product can ship without an LLM at inference time. Scripture is a high-trust domain. Hallucination is not a UX bug there — it is bearing false witness. Bible Genius cannot hallucinate because it does not generate; it composes. Every word returned was authored by translators in 1611 and 1769, stored on disk, and cited by file path.

The framework is the [Markdown Language Model](https://github.com/drew913s/MarkdownLanguageModel). This repository is an existence proof at the 31,000-node scale.

## License

Apache License 2.0 — see [LICENSE](LICENSE).

The King James Bible text is in the public domain.
