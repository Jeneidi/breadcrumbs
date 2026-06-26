---
name: breadcrumbs
description: Use at the end of every completed step in a multi-step task, and whenever the user reports new constraints/decisions, to keep .breadcrumbs/checkpoint.md up to date so context compaction never loses task state.
---

# breadcrumbs

Maintain a single living checkpoint file at `.breadcrumbs/checkpoint.md` (project root). This is the only file this skill touches.

## When to update

- At the end of every completed step or clean breakpoint, before context could be compacted.
- Whenever the user states a new constraint, decision, or hard requirement.
- Whenever a file is created, edited, or deleted as part of the task.

## How to update

Create the directory and file if they don't exist. Otherwise **edit it in place** — rewrite sections, don't append a growing log. This is a snapshot of current task state, not a diary. Stale or completed items get removed, not buried under new ones.

Use exactly these section headers, in this order:

```markdown
## Active Task
One or two sentences: what is being worked on right now.

## Decisions
- Decision — why (one line each).

## Files Touched
- path/to/file — what changed.

## Open TODOs
- Remaining work, not yet done.

## Hard Constraints
- Non-negotiable requirements (e.g. "never touch X", "must use Y").
```

Keep every section tight: a handful of bullets, not paragraphs. If a section has nothing yet, leave the header with no bullets under it rather than omitting the header.

## Why this exists

Claude Code's auto-compaction can fire mid-task under token pressure and silently drop decisions or constraints from history. This file is the durable source of truth that survives compaction (see the plugin's hooks: `PreCompact` snapshots it, `PostCompact` re-injects it). Keeping it current is the whole point — a stale checkpoint is as bad as no checkpoint.
