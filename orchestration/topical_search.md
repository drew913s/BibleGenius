---
name: topical_search
trigger: POST /api/run with orchestration=topical_search
inputs:
  question: required — e.g. "what does the bible say about forgiveness?"
---

# Topical Search

Find verses related to a topic. Classifies the question against the curated topic index (forgiveness, faith, love, grace, etc.), then follows the topic node's `[[wikilinks]]` to surface the top scripture references for that topic.

## Process Steps

```yaml
steps:
  - action: load
    target: identity/voice
    as: voice

  - action: classify
    field: inputs.question
    subgraph: topics
    as: topic
    fallback: identity/dont_know

  - action: follow_wikilinks
    from: topic
    as: verses
    max_links: 8

  - action: compose
    template: response
    as: answer

  - action: render
    from: answer
```

## Templates

```response
{topic.topic} — {topic.summary}

{topic.preview}
```
