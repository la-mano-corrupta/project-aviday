---
name: 2d-short-video-skill
description: >-
  Produces end-to-end 2D short-form videos and creative production packages for
  YouTube Shorts, Instagram Reels, and TikTok (9:16, 1080x1920), specialized for
  the 2D animated philosophy Shorts niche. Supports dual rendering engines
  (HTML5 Canvas + Headless Chrome + FFmpeg with word-synced captions, and
  Remotion React/SVG + FFmpeg), optional multi-key Gemini API scripting/auditing,
  local Kokoro + Whisper narration timing, verified philosopher quote checks,
  3-second multimodal hooks, and cross-platform safe-zone cover specs. Use when
  creating, scripting, narrating, storyboarding, rendering, or auditing 2D short
  videos, Stoic/existentialist/thought-experiment Shorts, or vertical Reels.
metadata:
  version: "1.0.0"
  domain: "short-form-2d-philosophy-video"
---

# 2D Short Video Skill (Shorts / Reels / Philosophy)

Create high-retention `1080x1920` (9:16) 2D animated shorts designed to clear the opening 3-second scroll gate (**Viewed vs. Swiped Away** / **3-second hold**) and drive completions, saves, and DM **Sends Per Reach**.

`SKILL` = the directory containing this file.

## Progressive Reference Loading

Load only the reference files required for the active step:

- Choosing a philosopher, thought experiment, or auditing quotes -> [references/philosopher-playbook.md](references/philosopher-playbook.md)
- Platform signals, runtime budgets, or 0–3s hook templates -> [references/hooks-and-algorithms.md](references/hooks-and-algorithms.md)
- Visual archetypes, 2D pacing, SFX layering, narration craft & sample scripts -> [references/2d-visuals-and-narration.md](references/2d-visuals-and-narration.md)
- Pixel safe zones, `1080x1440` (3:4) IG grid covers, and CTR rules -> [references/thumbnails-and-safe-zones.md](references/thumbnails-and-safe-zones.md)
- Dual rendering engines & 7-key Gemini API router -> [references/engines-and-gemini-pipeline.md](references/engines-and-gemini-pipeline.md)
- Script formatting & hook fill-in templates -> [assets/av-script-template.md](assets/av-script-template.md) and [assets/hook-bank.md](assets/hook-bank.md)

---

## Duration & Spoken Word-Budget Tree (150 WPM / 2.5 wps + Pause Buffer)

| Format | Runtime | Spoken Word Target (Hard Max) | Cadence | Best Philosophy Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Micro-Loop** | **15 s** | `30–35 words` (`38 max`) | 2–3 visual cuts | Quote debunking, single paradox, seamless loop |
| **Discovery Short** | **30 s** | `65–70 words` (`75 max`) | 4–5 scenes + 1.5–2.5s shifts | Diogenes anecdotes, *One Metaphor*, Reels velocity |
| **Thought Experiment** | **45 s** | `95–102 words` (`113 max`) | 6 scenes × 6–8s | Plato's Cave, Trolley, Sartre's *Look*, Socratic Duo |
| **Deep Contrast** | **60 s** | `125–140 words` (`150 max`) | 7–9 scenes + 15s interrupt | Thinker contrast (Kant vs. Mill, Camus vs. Sartre) |

---

## End-to-End Execution Workflow

### Step 1: Lock Concept, Style & Rendering Engine
1. Confirm duration (`30s` or `45s` default), platform target (`All-3` composite safe zone default), and **1-Sentence North Star** (exact philosophical shift the viewer leaves with).
2. Choose one **2D Style Preset** (`styles/*.json`) and **Advids Model** (*One Metaphor*, *Line Diagram*, *Hero Chart*, or *Bare Object*):
   - `sisyphus-sketch` — raw notebook ink wobble (*Sisyphus 55* / *After Skool*)
   - `dark-academia-monograph` — nocturnal charcoal + gold (*Einzelgänger* / *Eternalised*)
   - `school-of-thought` — warm flat pastel vectors (*The School of Life*)
   - `socratic-duo` — Sage + Skeptic debate interrupting at second 12–15 (*Philosophy Vibe*)
3. Select rendering engine:
   - **Canvas Engine (`templates/canvas-2d`)**: zero-npm Node + Chrome + FFmpeg; best for sketchy 2D characters, procedural ink draws, fast local batches, and word-synced captions.
   - **Remotion Engine (`templates/remotion-2d`)**: React + SVG/Canvas + FFmpeg; best for kinetic typography, animated line diagrams, springs, and live Studio scrubbing.
4. Avoid sensational "dark psychology / alpha" clichés; anchor every script in honest human philosophical tension.

### Step 2: Mandatory Quote & Fact Verification Gate
1. Check every attribution against [references/philosopher-playbook.md](references/philosopher-playbook.md) (or run `python3 scripts/gemini_router.py audit-quotes --script <file>`).
2. Quote verbatim **only** with verified book/letter citations (e.g., *Meditations* II.1, *Letters* 13.4). Mark anecdotal traditions (*Diogenes*, *Socrates via Diogenes Laërtius*) as historical reports.
3. **Never** present disputed/fabricated quotes (e.g., *Gladiator* lines as Marcus Aurelius, James Allen as Epictetus, viral fake Socrates quotes) as authentic—swap them or flip them into a myth-busting hook.

### Step 3: Engineer 3 Multimodal Hooks (0–3 Seconds)
Zero greetings, zero logos, zero fade-ins on Frame 1. Draft 3 distinct variations (e.g., *Misconception Break*, *Historical Story*, *Second-Person Callout*), each pairing:
- **Spoken Hook:** Strictly **7–8 words max** starting mid-tension.
- **On-Screen Text Hook:** **5–8 words max**, high contrast inside `y = 380..500`.
- **Frame-1 Visual Motion:** Expressive 2D character or bold metaphor prop legible with sound muted.

### Step 4: Reverse-Write & Audit the Ear-First Script
1. Draft the **Last Line first** (seamless loop into Line 1 or DM-share mirror stinger), then Hook, then 2–3 tight middle beats.
2. Follow ear-first rules: short sentences (<18 words), punch word at the end, spell out numbers (`twenty-four`, not `24`), add first-use phonetics (`Nietzsche (NEE-chuh)`), and mark silent beats with `[beat]` / `[pause]`.
3. Optionally scaffold via the 7-key Gemini router (keys loaded from `.env` or env vars, never committed):
   ```bash
   python3 scripts/gemini_router.py generate-short \
     --philosopher "Albert Camus" --topic "..." --duration 45 --style sisyphus-sketch --out script.json
   ```
4. **Required Audit:** Run the budget & quote validator before generating audio:
   ```bash
   python3 scripts/check_script_budget.py <project>/script.json --target-sec 30
   ```

### Step 5: Voiceover, Word Alignment & Procedural Soundtrack
1. Scaffold project if needed: `bash scripts/new_project.sh <canvas-2d|remotion-2d> <slug>`
2. Generate timing (`estimate.py` for instant preview, or Kokoro `$0` local voice + Whisper word alignment):
   ```bash
   scripts/py scripts/voice.py <project>
   scripts/py scripts/words.py <project>
   ```
3. Build SFX cues and voice-ducked ambient soundtrack (`48 kHz` stereo `data/mix.wav`):
   ```bash
   cd <project>
   node tools/render_canvas.mjs cues
   <SKILL>/scripts/py tools/mix.py .
   ```

### Step 6: Safe-Zone Visual QA, Covers & Final Render
All vital text, characters, and captions (`y = 980..1220`) must stay inside the **All-3 composite safe box** (`x = 60..883`, `y = 380..1248`, horizontal center `x = 468`) so YouTube Shorts, IG Reels, and TikTok UI overlays never clip content.
1. Inspect shot timeline, contact sheet, and dual-aspect covers (`9:16` `1080x1920` + IG Grid `3:4` `1080x1440`):
   ```bash
   node tools/render_canvas.mjs check
   node tools/render_canvas.mjs sheet review/sheet.jpg 0.5 8 --safezone
   node tools/render_canvas.mjs cover review/cover
   python3 <SKILL>/scripts/qa_check.py . --target-sec 30
   ```
2. Visually inspect `review/sheet.jpg` and `review/cover-3x4.jpg` / `review/cover-9x16.jpg` before exporting. For high-CTR illustrated covers generated via the 7-key Gemini Image API (`gemini-nano-banana-2.1` / `gemini-3-pro-image`), run:
   ```bash
   python3 <SKILL>/scripts/gemini_router.py generate-thumbnail --script script.json --both --out review/cover-ai
   ```
   Fix any collision, unsafe caption placement, or low-contrast cover text at 150 px postage-stamp scale.
3. Export final `1080x1920` MP4:
   ```bash
   node tools/render_canvas.mjs video renders/final.mp4
   ```
   *(For Remotion projects: `npm install && npm run studio` or `npm run render`, plus `npm run cover:3x4`.)*

---

## Pre-Delivery QA Checklist

- [ ] Spoken hook is `<= 8 words`, paired with `<= 8 word` text hook and clear muted Frame-1 motion.
- [ ] `check_script_budget.py` passes with zero disputed quotes and word count inside pause-buffered budget.
- [ ] Every 1.5–2.5s interval has a visual beat, camera push, polarity flip, or prop action.
- [ ] Captions (`1–3` words, `1` accent highlight) and focal faces sit inside the `823x868` All-3 safe box (`cx = 468`).
- [ ] Cover uses `2–3` bold curiosity words (not duplicating the title) surviving `4:5`, `1:1`, and `3:4` crops.
- [ ] Contact sheet, covers, and final `1080x1920` MP4 audio/video verified cleanly via `qa_check.py`.
