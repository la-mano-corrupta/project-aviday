---
name: obsidian-recall
description: Save, organize, and retrieve learning notes, debugging lessons, and active-recall flashcards in the user's Obsidian vault (~/Documents/ObsidianVault) alongside ECC Unified Memory. Use when the user asks to remember something, take study/learning notes, review past lessons, or build a knowledge base.
---

# Obsidian Recall & Learning Skill

This skill connects Antigravity's workflow with the user's local **Obsidian Vault** at `~/Documents/ObsidianVault` and the **ECC Memory Vault** (`ecc-memory` MCP / `unified-memory` skill).

## Vault Layout

- `~/Documents/ObsidianVault/memory/` — `ECC_MEMORY_USER_ROOT` for `ecc-memory` MCP (`memory_search`, `memory_read`, `memory_save`). Use this for structured `ecc.memory.v1` records (`decision`, `lesson`, `fact`, `context`, `runbook`, `preference`).
- `~/Documents/ObsidianVault/learning/` — Human-facing study notes, concept breakdowns, debugging postmortems, and Q&A / active-recall prompts with `[[wikilinks]]` and `#tags`.
- `~/Documents/ObsidianVault/projects/` — Project-level Maps of Content (MOCs) and architecture notes.

## When Saving Notes for Recall & Learning

1. **Search first** (`memory_search` or `rg` inside `~/Documents/ObsidianVault`) so you update or link to existing notes instead of duplicating them.
2. **Choose the right destination**:
   - Quick durable facts, preferences, or cross-session coding lessons → save via `ecc-memory` (`memory_save` with `--scope user` / user scope) **or** `ecc memory save --scope user`.
   - Deeper learning notes, study guides, or concept explanations → write a clean Markdown file in `~/Documents/ObsidianVault/learning/<topic-slug>.md` with:
     - YAML frontmatter (`tags`, `created`, `topic`)
     - Clear summary + key takeaways
     - `## Recall Questions` (2–4 self-test questions with collapsible `<details>` answers or concise bullet answers)
     - `[[wikilinks]]` to related notes.
3. **Keep notes atomic**: One concept or debugging lesson per note so Obsidian's graph and search stay sharp.

## When Reviewing / Recalling

- Search both `memory/` (via `ecc-memory` MCP) and `learning/` (via `read_file` / search) before answering "what did we learn about X?" or quizzing the user on a topic.
