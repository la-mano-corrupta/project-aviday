# Thumbnails, Cover Frames & Cross-Platform Safe Zones

## 1. Cross-Platform 1080 × 1920 Safe-Zone Coordinates

YouTube does not publish a single official pixel safe zone for organic Shorts. Safe-zone design therefore synthesizes **Google's paid vertical ad margins** with **empirical organic mobile UI checks** (Revid, Zeely, Exemplary AI Oct 2026).

| Platform / Spec | Master Frame | Covered UI Margins (Avoid Critical Info) | Safe Content Box | Positioning Rules |
| :--- | :--- | :--- | :--- | :--- |
| **YouTube Shorts (Google Paid Ad Spec)** | `1080 × 1920` (9:16) | Top `288 px` (15%), Bottom `672 px` (35%), Left `48 px` (4%), Right `192 px` (18%) | `840 × 960 px` (`x: 48..888`, `y: 288..1248`; horizontal center `x = 468 px`) | Leaves full bottom `672 px` clear for channel handle, multi-line title, audio pill, and Subscribe button. |
| **YouTube Shorts (Exemplary AI Organic Check)** | `1080 × 1920` (9:16) | Top `380 px`, Bottom `380 px`, Left `60 px`, Right `120 px` | `900 × 1160 px` (`x: 60..960`, `y: 380..1540`) | Protects taller top Shorts search bar. Keep vital hook headlines below `y = 380 px`! |
| **Instagram Reels & Profile Grid** | `1080 × 1920` (9:16); `1080 × 1440` (3:4 grid) | Lower caption overlay + right engagement column | `895 × 980 px` (vertical feed estimate) | Since Jan 2025, IG Profile Grids display **3:4** (`1080 × 1440`) thumbnails (`4:5` trims thin edges). Always export a dedicated `1080 × 1440` cover! |
| **TikTok** | `1080 × 1920` (9:16) | Bottom `~480 px`, Right `~140 px` | `880 × 1220 px` | Narrower bottom overlay than Shorts—captions sized for TikTok sit too low for YouTube Shorts unless raised ~200 px. |
| **Composite "All-3" Safe Box (Skill Default)** | `1080 × 1920` (9:16) | Strict intersection of YouTube Paid/Organic, IG Reels, and TikTok | `x: 60..883` (`width 823 px`), `y: 380..1248` (`height 868–960 px`), center `x = 468 px` | **Skill default:** Put Hook Headline at `y = 400..520`, Hero 2D Stage at `y = 520..980`, Word-Synced Captions at `y = 1040..1200` (inside `900..1248`), all centered at `x = 468 px`. |

### Visual Safe-Zone Map (1080 × 1920)
```text
y = 0     ┌───────────────────────────────────────────┐
          │   TOP SEARCH / CAMERA UI (Avoid: 0..380)  │
y = 380   ├───┬───────────────────────────────────┬───┤
          │   │  HOOK / CITATION ZONE (380..520)  │   │
          │ L │                                   │ R │  Right Action Column
          │ E │   2D HERO STAGE / CHARACTERS      │ I │  (Like, Comment, Share,
          │ F │       (x: 60..883, cx: 468)       │ G │   Remix: x = 888..1080)
y = 960   │ T │                                   │ H │
          │   │  WORD-SYNCED CAPTIONS (980..1220) │ T │
y = 1248  ├───┴───────────────────────────────────┴───┤
          │                                           │
          │  BOTTOM TITLE / CHANNEL / AUDIO PILL      │
          │         (Avoid: y = 1248..1920)           │
y = 1920  └───────────────────────────────────────────┘
```

---

## 2. Cover & Thumbnail Mechanics (2025–2026)

### YouTube Shorts Cover Rules
- **YPP Custom Thumbnails (July 2026+):** Channels in the YouTube Partner Program can upload custom **`1080 × 1920` JPG or PNG (< 2 MB)** covers.
- **Non-YPP Channels:** Desktop Studio cannot select custom Shorts thumbnails. Use the **YouTube mobile app** (pencil icon during upload, or schedule unlisted from desktop and edit frame on mobile) to pick an in-video frame.
- **Cover-Frame Hack for Non-YPP:** Append or prepend a clean **0.10–0.20s (`3–6 frames`)** dedicated `1080 × 1920` cover frame inside the edit (prefer placing it inside a brief micro-frame or frame 0 if it doubles cleanly as the Frame-1 visual hook) so the mobile frame picker grabs a sharp graphic without hurting retention.
- **Multi-Aspect Crop Survival:** YouTube Search, Home, Channel Grids, and Watch History crop vertical `9:16` thumbnails into **`4:5`, `1:1` square, and even `16:9` horizontal previews** around the center. Keep character eyes and 2–3 cover words inside the **middle third (`y = 660..1260`, `x = 180..900`)** so zero letters or faces get clipped!

### Instagram Reels Cover Rules
- **Profile Grid (Jan 2025 Update):** IG switched profile grids from `1:1` squares to **`3:4` vertical rectangles (`1080 × 1440 px`)**.
- Render a dedicated `1080 × 1440` cover variant alongside the `1080 × 1920` video using `node scripts/render_canvas.mjs cover` (or Remotion `Cover3x4` composition) so profile tiles look intentional with zero edge slicing.

---

## 3. High-CTR 2D Cover Design Principles

Even though Shorts auto-play in feeds, high-CTR covers drive Search, Browse, Suggested, Channel Page binges, and IG Profile exploration:

1. **Complement, Never Duplicate the Title:**
   - *Title:* `"Why Diogenes Told Alexander to Move"`
   - *Bad Cover Text:* `"Diogenes Told Alexander to Move"` (redundant).
   - *High-CTR Cover Text:* **`"MOVE."`** or **`"OWN NOTHING"`** (creates a curiosity gap alongside the expressive 2D confrontation).
2. **2–3 Bold Words Maximum (4 Word Hard Cap):**
   - Phone feed thumbnails shrink to ~120–160 px wide. Thin serifs or full sentences blur into noise.
   - Use heavy sans-serif (`Inter Black`, `Montserrat Black`, `Anton`) with high-contrast stroke/shadow, max 2 colors (e.g., off-white `#FAF6EE` + amber-gold `#F5B73B` on deep ink `#111318`).
3. **One Expressive Face or Symbolic Metaphor:**
   - *The School of Life* model: solid pastel backdrop, central stylized cartoon face showing an unmistakable emotion (dread, calm defiance, shock).
   - *Sisyphus 55* model: stark monochrome/paper ground, bold sketchy stick/ink figure facing a massive boulder or abyss.
   - *Einzelgänger* model: chiaroscuro dark charcoal backdrop, dramatic warm rim-lit silhouette or classical bust, minimal serif/sans contrast.
4. **Temperature & Value Separation:**
   - Pair cool/dark backgrounds (charcoal, midnight slate, muted sage) with warm high-chroma focal elements (amber sunbeam, glowing boulder, terracotta figure).
5. **The Postage-Stamp Squint Test (Mandatory QA):**
   - Zoom the exported cover down to **150 px wide** (or inspect it on a contact sheet). If you cannot read every letter and recognize the emotion/prop in <0.5 seconds, thicken the outlines and delete background clutter.

---

## 4. A/B Testing Protocol (Isolate One Variable)

When testing 2–3 thumbnails (e.g., via YouTube Test & Compare or IG Trial Reels):
- **Test 1 (Hook Text):** Same 2D illustration -> Test `"NOT A STOIC"` vs `"STOP PRETENDING"`.
- **Test 2 (Color Polarity):** Same text & layout -> Test dark charcoal background vs warm parchment paper background.
- **Evaluate Post-Click Quality:** Never chase deceptive clickbait CTR; pair CTR with **Viewed vs. Swiped Away** and **Watch Time Share** so clicks convert into completions.
