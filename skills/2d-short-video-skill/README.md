# 2D Short Video Skill for Shorts/Reels

An Antigravity Agent Skill repository for researching, scripting, narrating, animating, and rendering vertical (`9:16`, `1080×1920`) **2D short-form videos** for **YouTube Shorts**, **Instagram Reels**, and **TikTok**—deeply specialized for **2D animated philosophy Shorts**.

## Highlights

- **Antigravity Progressive-Disclosure Bundle:** Lean [SKILL.md](SKILL.md) orchestrator backed by modular domain playbooks in `references/`, reusable script/hook templates in `assets/`, and 4 visual presets in `styles/`.
- **Dual 2D Rendering Engines:**
  1. **HTML5 Canvas + Headless Chrome + FFmpeg** (`templates/canvas-2d`, zero npm packages, Node 22+) — sketchy hand-boil 2D characters, procedural ink/metaphor scenes, word-synced captions, and instant contact sheets + covers.
  2. **Remotion React + SVG/Canvas + FFmpeg** (`templates/remotion-2d`) — component-driven 2D motion graphics, kinetic typography, spring physics, and animated diagrams/charts.
- **7-Key Gemini API Router (`scripts/gemini_router.py`):** Stdlib Python router supporting `GEMINI_API_KEYS` (or `GEMINI_API_KEY_1..7`) with automatic `429`/`503` rotation or optional `--worker-url` proxy.
- **Local $0 Audio & Alignment Pipeline:** Kokoro-82M TTS (`voice.py`), Faster-Whisper word-level timestamps (`words.py`), stdlib duration estimator (`estimate.py`), and procedural ambient + tactile SFX mixing (`mix.py`).
- **Built-In Research & Verification Guardrails:** Philosopher demand matrix, Verified vs. Disputed quote ledger, deterministic script budget/quote auditor (`check_script_budget.py`), and cross-platform `823×868` All-3 safe-zone enforcement (`1080×1920` + `1080×1440` IG `3:4` grid covers).

## Repository Layout

```text
2d-short-video-skill/
├── SKILL.md                             # Concise Antigravity orchestrator
├── README.md                            # Repository documentation
├── .env.example                         # Template for GEMINI_API_KEYS (never commit .env)
├── .gitignore
├── references/
│   ├── philosopher-playbook.md          # Thinkers, topics, engagement matrix, quote ledger
│   ├── hooks-and-algorithms.md          # 2025-2026 ranking signals, 0-3s hooks, loop endings
│   ├── 2d-visuals-and-narration.md      # Benchmarks, 2D craft, SFX, VO rules, 4 sample scripts
│   ├── thumbnails-and-safe-zones.md     # Cross-platform pixel safe zones & cover rules
│   └── engines-and-gemini-pipeline.md   # Canvas vs. Remotion + 7-key Gemini workflow
├── assets/
│   ├── av-script-template.md            # Two-column StudioBinder AV script template
│   └── hook-bank.md                     # Fill-in-the-blank multimodal hook bank
├── styles/                              # sisyphus-sketch, dark-academia-monograph, school-of-thought, socratic-duo
├── scripts/                             # py, check_script_budget.py, gemini_router.py, estimate.py, voice.py, words.py, mix.py, render_canvas.mjs, qa_check.py, new_project.sh
└── templates/
    ├── canvas-2d/                       # Ready-to-render Diogenes 30s 2D Canvas starter
    └── remotion-2d/                     # Ready-to-customize Remotion Stoic starter
```

## Quick Start

```bash
# 1. Symlink into Antigravity global skills directory
ln -sfn "$(pwd)" ~/.gemini/antigravity/skills/2d-short-video-skill

# 2. (Optional) Configure Gemini API keys for script drafting & quote audits
cp .env.example .env

# 3. Scaffold a new Canvas 2D short project
bash scripts/new_project.sh canvas-2d my-first-short

# 4. Audit word budget & quote accuracy
python3 scripts/check_script_budget.py ~/2d-short-videos/my-first-short/script.json --target-sec 30

# 5. Estimate timing (or generate $0 Kokoro voice + Whisper alignment)
python3 scripts/estimate.py ~/2d-short-videos/my-first-short

# 6. Check shots, generate SFX cues, mix audio, inspect sheet & covers, and render
cd ~/2d-short-videos/my-first-short
node tools/render_canvas.mjs check
node tools/render_canvas.mjs cues
../../skills/2d-short-video-skill/scripts/py tools/mix.py .
node tools/render_canvas.mjs sheet review/sheet.jpg 0.5 8 --safezone
node tools/render_canvas.mjs cover review/cover
node tools/render_canvas.mjs video renders/final.mp4
```
