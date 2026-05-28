---
name: cross_reference
trigger: POST /api/run with orchestration=cross_reference
inputs:
  question: required — e.g. "John 3:16" — must name a specific verse
---

# Cross-Reference Walk

Identify the verse the user named, then return the adjacent verses linked from that verse's `[[related]]` wikilinks. Useful for reading a verse in its immediate context.

## Process Steps

```yaml
steps:
  - action: load
    target: identity/voice
    as: voice

  - action: classify
    field: inputs.question
    subgraph: books
    as: book

  - action: classify
    field: inputs.question
    subgraph: "verses/{book.book_slug}"
    as: verse
    when: book.book_slug

  - action: follow_wikilinks
    from: verse
    as: adjacent
    max_links: 4

  - action: compose
    template: response
    as: answer

  - action: render
    from: answer
```

## Templates

```response
{verse.reference}

{verse.summary}

— Adjacent verses linked from this passage are returned in the provenance list. Open any cited file under corpus/verses/ to read them in full.
```
