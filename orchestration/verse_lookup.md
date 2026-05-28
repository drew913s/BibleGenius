---
name: verse_lookup
trigger: POST /api/run with orchestration=verse_lookup
inputs:
  question: required — e.g. "John 3:16", "Matt 5:3", "1 Samuel 17:45"
---

# Verse Lookup

Resolve a verse reference and return that exact verse from the King James corpus.

The orchestration parses the user's question with a regex (book name, chapter, verse), classifies the book name against the 66-book index — using the parsed slug as a name-hint so "John" wins over "3 John" — and loads the verse markdown directly by path. If the question doesn't match a reference pattern, it returns the "I don't know" identity node.

## Process Steps

```yaml
steps:
  - action: load
    target: identity/voice
    as: voice

  - action: extract
    field: inputs.question
    pattern: "(?P<book>\\d?\\s*[A-Za-z]+(?:\\s+[A-Za-z]+)*)\\s+(?P<chapter>\\d+)[:.\\s]+(?P<verse>\\d+)"
    as: ref

  - action: classify
    field: ref.book
    subgraph: books
    as: book
    name_hint_from: ref.book_slug
    when: ref.book

  - action: load_dynamic
    target: "verses/{book.book_slug}/{ref.chapter}_{ref.verse}"
    as: verse

  - action: load_dynamic
    target: identity/dont_know
    as: verse

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
```
