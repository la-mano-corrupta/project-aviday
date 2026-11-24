# Dual Rendering Engines, 7-Key Gemini Pipeline & Originality Guardrails

## 1. Choosing the Right Rendering Engine

This skill supports **two complementary 1080 × 1920 code-driven 2D pipelines** sharing the same `script.json` + word-timing format (`data/words.json`):

| Feature | Engine A: HTML5 Canvas + Headless Chrome + FFmpeg | Engine B: Remotion (React + SVG/Canvas) + FFmpeg |
| :--- | :--- | :--- |
| **Best Visual Fit** | *Sisyphus 55* sketchy ink, *Philosophy Vibe* Socratic duo, *Inside Out* / *Stick Story* flat explainers, frame-by-frame hand-drawn wobble & procedural drawing reveals. | *The School of Life* clean flat vector scenes, *MotionCraft*-grade kinetic typography, animated *Line Diagrams* & *Hero Charts*, interactive spring physics, SVG morphs. |
| **Speed & Dependencies** | **Zero npm dependencies** (uses built-in Node 22+ `http`/`WebSocket`, local Google Chrome, FFmpeg). Fast local renders. | Uses React 18 + `@remotion/cli` + TypeScript (`npm install` inside project). Visual live scrubbing in `remotion studio`. |
| **Audio & Captions** | Shares `voice.py` (Kokoro $0), `words.py` (Whisper), `estimate.py`, and `mix.py` (procedural drone + tactile SFX). | Consumes the exact same `data/words.json` + `data/mix.wav` so audio/caption workflows stay identical. |
| **Cover Export** | `node scripts/render_canvas.mjs cover` outputs both `1080×1920` (Shorts/Reels) and `1080×1440` (IG 3:4 grid). | `Main` (`1080×1920`) and `Cover3x4` (`1080×1440`) compositions registered in `src/Root.tsx`. |

---

## 2. Multi-Key Gemini API Integration (7-Key Pool)

Use `scripts/gemini_router.py` when accelerating research synthesis, generating 3 multimodal hook variations, drafting `script.json`, or running an adversarial quote/fact check.

### Security & Key Configuration (Never Commit Keys)
Configure keys via environment variables or a local `.env` file (excluded by `.gitignore`):
- **Option 1 (Comma-separated list):** `GEMINI_API_KEYS="key1,key2,key3,key4,key5,key6,key7"`
- **Option 2 (Numbered env vars):** `GEMINI_API_KEY_1` through `GEMINI_API_KEY_7` (plus fallback `GEMINI_API_KEY`)
- **Option 3 (Remote Router Worker):** Pass `--worker-url https://...` (or set `GEMINI_WORKER_URL`) if routing through an existing Cloudflare Worker pool.

`gemini_router.py` automatically shuffles/round-robins across keys and **rotates to the next key on HTTP `429` (rate limit) or `500/503` transient errors** without exposing keys in git or logs.

### Common CLI Workflows
```bash
# 1. Generate 3 hook variations + quote check + script.json draft
python3 scripts/gemini_router.py generate-short \
  --philosopher "Albert Camus" \
  --topic "Why Camus imagined Sisyphus happy instead of hopeless" \
  --duration 45 \
  --style sisyphus-sketch \
  --out my-project/script.json

# 2. Verify quotes in an existing draft against primary citations
python3 scripts/gemini_router.py audit-quotes --script my-project/script.json

# 3. Generate high-CTR 9:16 + 3:4 illustrated thumbnails via Gemini Nano Banana API
python3 scripts/gemini_router.py generate-thumbnail \
  --script my-project/script.json --both --out my-project/review/cover-ai
```

Text generation/auditing uses `gemini-3.8-flash` (`GEMINI_MODEL`) and thumbnail generation uses `gemini-nano-banana-2.1` (`GEMINI_IMAGE_MODEL`, or `gemini-3-pro-image` for pro typography/lighting), normalizing covers cleanly to `1080×1920` and `1080×1440` under 2 MB.

---

## 3. End-to-End Local Production Pipeline

```bash
# Step 1: Scaffold a new short project (canvas-2d or remotion-2d)
bash scripts/new_project.sh canvas-2d diogenes-sun

# Step 2: Validate spoken budget, sentence length, AI clichés, and fake quotes
python3 scripts/check_script_budget.py ~/2d-short-videos/diogenes-sun/script.json --target-sec 30

# Step 3: Timing (choose one)
#   A) Instant timing preview without audio:
python3 scripts/estimate.py ~/2d-short-videos/diogenes-sun
#   B) $0 local AI voice + Whisper word timestamps:
scripts/py scripts/voice.py ~/2d-short-videos/diogenes-sun
scripts/py scripts/words.py ~/2d-short-videos/diogenes-sun

# Step 4 (Canvas Engine): Check shots, generate SFX cues, mix soundtrack, inspect sheet & cover
cd ~/2d-short-videos/diogenes-sun
node tools/render_canvas.mjs check
node tools/render_canvas.mjs cues
../../2d-short-video-skill/scripts/py tools/mix.py .
node tools/render_canvas.mjs sheet review/sheet.jpg 0.5 8
node tools/render_canvas.mjs cover review/cover
python3 ../../2d-short-video-skill/scripts/qa_check.py .

# Step 5 (Canvas Engine): Export final 1080x1920 MP4
node tools/render_canvas.mjs video renders/final.mp4
```

*(When `new_project.sh` scaffolds a `canvas-2d` project, it automatically copies `render_canvas.mjs` and `mix.py` into `tools/` so the project stays self-contained.)*

---

## 4. Platform AI Disclosure & Originality Guardrails

- **AI Disclosure Labels:** YouTube states that disclosing realistic AI-generated media does not by itself limit reach or ad eligibility.
- **Anti-"Inauthentic Content" Protection:** YouTube explicitly demonetizes mass-produced, repetitive template slop. Never ship identical scripts with swapped philosopher names. Ensure every short has:
  1. Original, ear-first human-edited prose and verified primary-text framing (no copy-pasted internet quote lists).
  2. Visual scene choreography tailored to the exact metaphor in `shots.js` or React components—not generic looping stock video.
  3. Custom sound timing (`cues.json` + voice-ducked score) and inspected visual QA contact sheets (`review/sheet.jpg`) before publishing.
