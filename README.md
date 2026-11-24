# Aviday Starter (`project-aviday`)

Create vertical `9:16` faceless short videos (`renders/*.mp4`) and cover thumbnails (`review/cover_*.jpg`) locally on macOS/Linux or in the cloud on GitHub Actions Linux servers — **no social media keys or paid API keys required to get started**.

When you are ready, you can optionally plug in API keys for AI script generation (Gemini), extra TTS voices (Kokoro, Gemini TTS, ElevenLabs), automatic Instagram Reels (Meta Graph API) and YouTube Shorts uploading, or a 24/7 Cloudflare Worker.

## Table of Contents

- [1. Prerequisites and Installation](#1-prerequisites-and-installation)
- [2. API Key Placeholders and Configuration](#2-api-key-placeholders-and-configuration)
- [3. Local Rendering vs GitHub Linux Server Rendering](#3-local-rendering-vs-github-linux-server-rendering)
- [4. Selecting a TTS and Voice Provider](#4-selecting-a-tts-and-voice-provider)
- [5. Video-Only and Dry-Run Walkthrough Without Upload Keys](#5-video-only-and-dry-run-walkthrough-without-upload-keys)
- [6. CLI Reference](#6-cli-reference)
- [7. Optional Instagram Meta Graph API and YouTube Shorts Upload Setup](#7-optional-instagram-meta-graph-api-and-youtube-shorts-upload-setup)
- [8. Optional Cloudflare Worker and Daemon Notes](#8-optional-cloudflare-worker-and-daemon-notes)
- [9. Bundled Video-Production and Obsidian Skills](#9-bundled-video-production-and-obsidian-skills)
- [10. Running Tests and Troubleshooting](#10-running-tests-and-troubleshooting)

---

## 1. Prerequisites and Installation

### System Requirements

To run video generation locally, install the following tools:

- **Python**: **3.10+** or **3.11** recommended.
  - Note: All root CLI scripts and unit tests also run cleanly on **Python 3.9.6+**, while the optional Kokoro/Whisper installer (`faceless-shorts-skill/faceless-shorts/scripts/setup.sh`) requires **Python 3.10+** to create `$FACELESS_HOME/venv`.
- **Node.js**: **>= 22** (required for headless Chrome CDP capture via `capture.mjs` and thumbnail rendering via `render_viral_thumbnail.mjs`).
- **FFmpeg & FFprobe**: required for audio mixing, TTS transcoding, and H.264/AAC MP4 encoding.
- **Google Chrome or Chromium**: required for headless HTML5 Canvas / Three.js WebGL rendering.

On macOS (Homebrew):

```bash
brew install python@3.11 node ffmpeg
brew install --cask google-chrome
```

On Ubuntu / Debian Linux:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv ffmpeg mesa-vulkan-drivers libgl1-mesa-dri libegl1-mesa-dev fonts-noto-color-emoji wget
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb
rm -f google-chrome-stable_current_amd64.deb
```

### Python Dependencies (`requirements.txt` vs. Optional `setup.sh`)

1. **Standard setup (required for `edge-tts`, `numpy`, and `scipy`)**:

   ```bash
   pip install -r requirements.txt
   ```

   This installs `numpy>=1.26.0`, `scipy>=1.11.0`, and `edge-tts>=7.0.0` (used by the default voice fallback and procedural audio mixing in `mix.py`).

2. **Optional offline Kokoro-82M + Whisper setup (`setup.sh`)**:

   If you want offline neural TTS (`kokoro`) and Whisper word-level caption alignment, run the bundled setup script (requires **Python 3.10+** and downloads ~0.9 GB of models into `$FACELESS_HOME/kokoro` and Whisper cache, defaulting to `~/.faceless-shorts`):

   ```bash
   bash faceless-shorts-skill/faceless-shorts/scripts/setup.sh
   ```

   This creates `$FACELESS_HOME/venv` (default `~/.faceless-shorts/venv`) with `numpy`, `scipy`, `kokoro-onnx`, and `faster-whisper`. Note that `setup.sh` does **not** install `edge-tts`, so keep `pip install -r requirements.txt` installed in your main Python environment as well.

   You can verify the underlying skill installation across styles with `selftest.sh` (add `--no-voice` to test quickly without TTS synthesis):

   ```bash
   bash faceless-shorts-skill/faceless-shorts/scripts/selftest.sh --no-voice
   ```

3. **Optional Node dev tooling (only needed for Cloudflare Worker development)**:

   ```bash
   npm install
   ```

---

## 2. API Key Placeholders and Configuration

Copy the environment template to create your local configuration file (`.env` is gitignored):

```bash
cp .env.example .env
```

If you plan to develop or deploy the optional Cloudflare Worker, also copy `.dev.vars.example`:

```bash
cp .dev.vars.example .dev.vars
```

> **Important beginner gotcha:** The Python scripts read `os.environ` directly and do **not** automatically load `.env` files! Whenever you open a new terminal and want your `.env` values to take effect, load them into your shell first:
>
> ```bash
> set -a && source .env && set +a
> ```

### How to Obtain Optional API Keys

You do **not** need any API keys for dry-runs or template/custom-script rendering. Only fill in the placeholders (`YOUR_...` or `<...>`) for features you want to enable:

- **Gemini API (`GEMINI_API_KEY`)**: Optional, used for AI script generation from `--topic` and for `--tts-provider gemini`. Create a key in [Google AI Studio](https://aistudio.google.com/) and replace `YOUR_GOOGLE_AI_STUDIO_API_KEY`.
- **ElevenLabs API (`ELEVENLABS_API_KEY`)**: Optional, only needed for `--tts-provider elevenlabs`. Create an API key and choose a voice ID (`ELEVENLABS_VOICE_ID`) from your [ElevenLabs dashboard](https://elevenlabs.io/).
- **Meta Graph API (Instagram Reels)**: Optional, only needed to auto-publish to Instagram. Requires an Instagram Business or Creator account linked to a Facebook Page, plus a Meta App in [Meta for Developers](https://developers.facebook.com/) to obtain `META_PAGE_ACCESS_TOKEN`, `IG_BUSINESS_ACCOUNT_ID`, and `FB_PAGE_ID`.
- **YouTube Data API v3 (Shorts)**: Optional, only needed to auto-upload to YouTube Shorts. Create an OAuth 2.0 Desktop Client in [Google Cloud Console](https://console.cloud.google.com/) with **YouTube Data API v3** enabled, download `client_secret.json`, and run the one-time OAuth flow to populate `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN`.

### Complete `.env.example` Environment Variable Reference

Every key in [`.env.example`](.env.example) uses non-secret placeholders or empty defaults:

| Variable | Category | Default / Placeholder | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | AI / Gemini | `"YOUR_GOOGLE_AI_STUDIO_API_KEY"` | Optional Gemini API key for topic script generation & Gemini TTS |
| `GEMINI_API_KEYS` | AI / Gemini | `""` | Optional comma-separated pool of Gemini keys for rotation |
| `GEMINI_TTS_VOICE` | AI / Gemini | `"Kore"` | Default voice used when `--tts-provider gemini` is selected |
| `TTS_PROVIDER` | TTS | `"default"` | Default voice provider (`default`, `kokoro`, `gemini`, `elevenlabs`) |
| `TTS_VOICE` | TTS | `""` | Global voice name/ID override (takes precedence over provider defaults) |
| `KOKORO_VOICE` | TTS | `"af_heart"` | Voice override when using Kokoro TTS |
| `EDGE_TTS_VOICE` | TTS | `"en-US-AndrewNeural"` | Voice override when using Edge-TTS fallback |
| `ELEVENLABS_API_KEY` | TTS | `""` | Optional ElevenLabs API key (`YOUR_ELEVENLABS_API_KEY`) |
| `ELEVENLABS_VOICE_ID` | TTS | `""` | Optional ElevenLabs voice ID (`YOUR_ELEVENLABS_VOICE_ID`) |
| `FPS` | Rendering | `"24"` | Video capture frame rate (`24` in pipeline; `30` in standalone `capture.mjs`) |
| `SOFTWARE_GL` | Rendering | `""` | Set to `"1"` on headless Linux/VMs without a GPU (enables SwiftShader WebGL) |
| `QS` | Rendering | `""` | Query string appended to `index.html`; defaults to `&res=0.6&aa=0&shadow=1024` when `SOFTWARE_GL=1` and `QS` is unset |
| `CHROME` | Rendering | `""` | Optional explicit path to Chrome/Chromium executable (fails fast if set to a nonexistent path) |
| `FACELESS_HOME` | Rendering | `""` | Base dir for Kokoro models & venv (defaults to `~/.faceless-shorts`) |
| `PROJECTS_DIR` | Rendering | `""` | Output root for rendered project folders (defaults to `~/faceless-shorts`) |
| `META_PAGE_ACCESS_TOKEN` | Instagram | `""` | Optional Facebook Page access token (`YOUR_META_PAGE_ACCESS_TOKEN`) |
| `IG_BUSINESS_ACCOUNT_ID` | Instagram | `""` | Optional Instagram Business/Creator account ID (`YOUR_IG_BUSINESS_ACCOUNT_ID`) |
| `FB_PAGE_ID` | Instagram | `""` | Optional linked Facebook Page ID (`YOUR_FB_PAGE_ID`) |
| `META_VERIFY_TOKEN` | Instagram | `"CHANGE_ME_VERIFY_TOKEN"` | Webhook verification token for Meta webhooks & optional Worker |
| `PUBLIC_VIDEO_BASE_URL` | Instagram | `""` | Optional HTTPS base URL hosting rendered MP4s for Meta Graph API |
| `LITTERBOX_UPLOAD` | Instagram | `"1"` | Set to `"1"` (default) to use temporary 72h Litterbox hosting if `PUBLIC_VIDEO_BASE_URL` is blank, or `"0"` to disable |
| `YOUTUBE_CLIENT_ID` | YouTube | `""` | Optional Google OAuth client ID (`YOUR_YOUTUBE_CLIENT_ID`) |
| `YOUTUBE_CLIENT_SECRET` | YouTube | `""` | Optional Google OAuth client secret (`YOUR_YOUTUBE_CLIENT_SECRET`) |
| `YOUTUBE_REFRESH_TOKEN` | YouTube | `""` | Optional Google OAuth refresh token (`YOUR_YOUTUBE_REFRESH_TOKEN`) |
| `AVIDAY_WORKER_URL` | Worker | `""` | Optional URL of your deployed Cloudflare Worker (`https://your-worker.example.workers.dev`) |
| `AVIDAY_HANDLE` | Worker | `""` | Optional Instagram handle for local webhook/agent scripts |
| `OWNER_NAME` | Worker | `"YOUR_NAME"` | Optional owner display name for Worker persona |
| `AGENT_NAME` | Worker | `"Aviday"` | Optional agent display name |
| `ADMIN_1_USERNAME` | Worker | `""` | Optional Instagram admin username for Worker DM controls |

*(Optional advanced overrides also read by `tts_providers.py` if set: `GEMINI_BASE_URL`, `GEMINI_TTS_MODEL`, `ELEVENLABS_BASE_URL`, `ELEVENLABS_MODEL_ID`, `KOKORO_AUTO_DOWNLOAD`.)*

---

## 3. Local Rendering vs GitHub Linux Server Rendering

You can render videos in two ways: **locally** on your own Mac/Linux machine, or **in the cloud** on GitHub's Linux runners using [`.github/workflows/faceless-reels.yml`](.github/workflows/faceless-reels.yml).

| Feature | Local Rendering | GitHub Actions Linux Server |
|---|---|---|
| **Best for** | Fast iteration on a Mac or PC with GPU | Friends without a fast local Mac or local setup |
| **Setup required** | Python, Node 22+, FFmpeg, Chrome | Zero local install — runs in GitHub UI |
| **WebGL mode** | Hardware GPU by default (fast) | Software WebGL (`SOFTWARE_GL=1`, `QS=&res=0.6&aa=0&shadow=1024`) |
| **Default FPS** | `24` via Python pipeline (`30` if calling `capture.mjs` directly) | `24` |
| **Where outputs go** | `$PROJECTS_DIR/<slug>/renders/*.mp4` & `review/cover_*.jpg` | Downloadable **Artifacts** zip (`faceless-reel-artifacts`) |
| **Social upload default** | Uploads only if keys are set and `--no-upload` is omitted | `publish` defaults to `false` (passes `--no-upload`) |

### Visual Styles (`--style`)

All 6 visual styles live under [`faceless-shorts-skill/faceless-shorts/styles/`](faceless-shorts-skill/faceless-shorts/styles):

| Style Slug | Visual Engine | Notes |
|---|---|---|
| `deep-dive` | 3D Three.js + WebGL | Rich 3D scenes; uses SwiftShader on Linux CPU (`SOFTWARE_GL=1`) |
| `night-file` | 3D Three.js + WebGL | Moody 3D documentary look |
| `tall-tale` | 2D cutouts in 3D Three.js world | Stylized animated storytelling |
| `stick-story` | Flat 2D HTML5 Canvas | Very fast to render even without a GPU |
| `inside-out` | Flat 2D HTML5 Canvas | Fast 2D body/concept explainer |
| `paper-atlas` | Cut-paper 2D HTML5 Canvas | Fast textured paper animation |
| `auto` | Rotates every 6 hours | Cycles across `deep-dive`, `night-file`, `stick-story`, and `tall-tale` |

### Option A: Local Rendering Environment Variables

On macOS or a desktop Linux GPU, leave `SOFTWARE_GL` unset for fast hardware WebGL rendering:

```bash
export PROJECTS_DIR="$HOME/my-aviday-renders"
export FPS="24"
```

On a headless Linux VM without a GPU, enable software WebGL:

```bash
export SOFTWARE_GL="1"
export QS="&res=0.6&aa=0&shadow=1024"
export CHROME="/usr/bin/google-chrome"
export FACELESS_HOME="$HOME/.faceless-shorts"
export PROJECTS_DIR="$HOME/faceless-shorts"
```

Note on `FPS`: the Python pipeline scripts (`generate_custom_topic_reel.py` and `synth_and_render.py`) and GitHub Actions workflow default `FPS` to `24`. Running the standalone `capture.mjs` helper directly without `FPS` set defaults to `30`.

### Option B: GitHub Actions Linux Server Rendering (`.github/workflows/faceless-reels.yml`)

If you do not want to install Chrome, FFmpeg, or Node locally, push/fork this repository to your own GitHub account and run it on GitHub's Linux runners (`ubuntu-latest`):

1. Open your repository on GitHub and click the **Actions** tab.
2. Select **Faceless Reels Cloud Generator (On-Demand)** (`.github/workflows/faceless-reels.yml`).
3. Click **Run workflow** (this triggers `workflow_dispatch`), fill in any of the **8** workflow inputs below, and click **Run workflow**:

| Workflow Input | Type / Default | Options & Description |
|---|---|---|
| `style` | choice (`deep-dive`) | `auto`, `deep-dive`, `night-file`, `stick-story`, `tall-tale`, `inside-out`, `paper-atlas` |
| `topic` | string (`What happens inside your brain when you pull an all-nighter?`) | Custom topic text or `"auto"` |
| `tts_provider` | choice (`default`) | `default`, `kokoro`, `gemini`, `elevenlabs` |
| `voice` | string (`""`) | Optional voice name or ID override |
| `caption` | string (`""`) | Optional custom Reel caption + hashtags |
| `publish` | boolean (`false`) | `false` (default) passes `--no-upload` and saves artifacts only; set `true` to upload (requires repo secrets) |
| `job_id` | string (`""`) | Optional Cloudflare Worker Queue Job ID |
| `existing_youtube_url` | string (`""`) | Optional existing YouTube Short URL if already published |

4. When the job finishes, scroll to the **Artifacts** section at the bottom of the workflow run summary and download **`faceless-reel-artifacts`**, which contains:
   - `output/**/renders/*.mp4`
   - `output/**/review/cover_*.jpg`

The Linux runner automatically configures `SOFTWARE_GL: '1'`, `QS: '&res=0.6&aa=0&shadow=1024'`, `FPS: '24'`, `PROJECTS_DIR: ${{ github.workspace }}/output`, Chrome (`--no-sandbox` / `--disable-dev-shm-usage` inside `capture.mjs`), Mesa GL, FFmpeg, and `fonts-noto-color-emoji`.

*(Optional)* If you want to add API keys for GitHub Actions later, add them under **Settings → Secrets and variables → Actions** (`GEMINI_API_KEY`, `GEMINI_API_KEYS`, `GEMINI_TTS_VOICE`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `META_PAGE_ACCESS_TOKEN`, `IG_BUSINESS_ACCOUNT_ID`, `FB_PAGE_ID`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`, `PUBLIC_VIDEO_BASE_URL`, `AVIDAY_WORKER_URL`).

---

## 4. Selecting a TTS and Voice Provider

Aviday supports **4** TTS providers via `TTS_PROVIDER` or the `--tts-provider` CLI flag. **The `default` provider stays active unless you explicitly change it.**

| Provider | CLI / Env Value | Requirements | How It Works |
|---|---|---|---|
| **Default** | `default` | Zero API keys required | In `generate_custom_topic_reel.py`, uses local Kokoro if `$FACELESS_HOME/kokoro` models + `kokoro_onnx` are installed, otherwise falls back to `edge-tts` (with offline cadence fallback). In `synth_and_render.py`, defaults to `edge-tts`. |
| **Kokoro (Offline)** | `kokoro` | `$FACELESS_HOME/venv` + models from `setup.sh` | Runs local Kokoro-82M (`voice.py`) + Whisper (`words.py`) at `$0` cost. |
| **Gemini TTS** | `gemini` | `GEMINI_API_KEY` or `GEMINI_API_KEYS` | Calls Gemini Interactions API (`gemini-3.8-flash-tts`), transcodes via FFmpeg, and aligns words. |
| **ElevenLabs** | `elevenlabs` | `ELEVENLABS_API_KEY` | Calls ElevenLabs `/v1/text-to-speech/{voice_id}`, transcodes via FFmpeg, and aligns words. |

### Voice Precedence Order

Both `--voice` and `TTS_VOICE` override provider-specific defaults:

1. `--voice` CLI flag
2. `TTS_VOICE` environment variable
3. Provider-specific environment variable / script / style default:
   - **Kokoro**: `KOKORO_VOICE` → `script.json["voice"]` → style default (`am_michael`, `am_onyx`, `am_puck`, etc.)
   - **Edge (`default` fallback)**: `EDGE_TTS_VOICE` → style default (`en-US-AndrewNeural`, `en-US-ChristopherNeural`, `en-US-GuyNeural`, `en-US-BrianNeural`)
   - **Gemini**: `GEMINI_TTS_VOICE` → `"Puck"` (`.env.example` sets `"Kore"`)
   - **ElevenLabs**: `ELEVENLABS_VOICE_ID` → `"21m00Tcm4TlvDq8ikWAM"`

### `--dry-run` Provider Validation Behavior

- With `--tts-provider default` (or omitted): `--dry-run` always exits **`0`** even when zero API keys and no Kokoro models are present.
- With an explicit non-default provider (`kokoro`, `gemini`, or `elevenlabs`): `--dry-run` checks whether required models or API keys exist and exits **`2`** with a clear diagnostic if they are missing.

Examples:

```bash
python3 -B generate_custom_topic_reel.py --style deep-dive --tts-provider default --dry-run --no-upload
```

```bash
python3 -B generate_custom_topic_reel.py --style night-file --tts-provider kokoro --voice am_onyx --dry-run --no-upload
```

```bash
GEMINI_API_KEY="YOUR_KEY_FROM_AI_STUDIO" python3 -B generate_custom_topic_reel.py --style deep-dive --tts-provider gemini --voice Kore --dry-run --no-upload
```

```bash
ELEVENLABS_API_KEY="YOUR_ELEVENLABS_KEY" python3 -B generate_custom_topic_reel.py --style deep-dive --tts-provider elevenlabs --voice 21m00Tcm4TlvDq8ikWAM --dry-run --no-upload
```

---

## 5. Video-Only and Dry-Run Walkthrough Without Upload Keys

You do **not** need Instagram, YouTube, Gemini, or ElevenLabs keys to test or render full videos locally.

### Step 1: Copy `.env.example` (Optional for Video-Only)

```bash
cp .env.example .env
set -a && source .env && set +a
```

### Step 2: Run a Zero-Key Dry-Run Check

Verify your Python environment, style selection, script resolution, and upload-skip logic without rendering or making network calls:

```bash
python3 -B generate_custom_topic_reel.py --style deep-dive --topic "Deep Sea Cables" --dry-run --no-upload
```

You can also dry-run the preset batch runner:

```bash
python3 -B synth_and_render.py --style night-file --tts-provider default --dry-run --no-upload
```

Both commands print a JSON summary and exit with code **`0`**.

### Step 3: Render a Real Video With Zero API Keys

When `GEMINI_API_KEY` is unset (or left as its placeholder), `generate_custom_topic_reel.py` automatically falls back to the style's built-in `example/script.json` template, synthesizes voiceover with `default` TTS, captures frames in headless Chrome, mixes audio, and skips Instagram & YouTube uploads cleanly with exit code **`0`**:

```bash
python3 -B generate_custom_topic_reel.py --style stick-story --no-upload
```

Or pass your own local JSON script via `--script` (zero Gemini calls):

```bash
python3 -B generate_custom_topic_reel.py --style deep-dive --script faceless-shorts-skill/faceless-shorts/styles/deep-dive/example/script.json --no-upload
```

### Step 4: Inspect Your Generated Video and Covers

Outputs are written inside `$PROJECTS_DIR/<slug>/` (default `~/faceless-shorts/<slug>/`):

- Video: `$PROJECTS_DIR/<slug>/renders/*.mp4` (1080×1920 H.264 + AAC)
- Thumbnails: `$PROJECTS_DIR/<slug>/review/cover_*.jpg` (`cover_hook.jpg` and `cover_youtube.jpg`)

Even if you omit `--no-upload`, when Meta Graph API and YouTube credentials are unset or still placeholders, the pipeline logs that uploads were skipped and exits **`0`** with your video and cover images preserved on disk.

---

## 6. CLI Reference

### `generate_custom_topic_reel.py`

Generates a single custom or template-fallback faceless reel, optionally uploads, and prints a JSON summary.

| Flag | Default | Description |
|---|---|---|
| `--style` | `auto` | Visual style (`auto`, `deep-dive`, `inside-out`, `night-file`, `paper-atlas`, `stick-story`, `tall-tale`) |
| `--topic` | `auto` | Reel topic text or `'auto'` (picks from topic curriculum or style template title) |
| `--script` | `""` | Path to a local script JSON file (skips Gemini API calls) |
| `--tts-provider` | `TTS_PROVIDER` or `default` | TTS backend (`default`, `kokoro`, `gemini`, `elevenlabs`) |
| `--voice` | `""` | Voice name or ID override |
| `--no-upload` | `false` | Explicitly skip YouTube and Instagram uploads (takes precedence over `--publish`) |
| `--publish` | `false` | Enable social publishing when credentials are configured |
| `--dry-run` | `false` | Validate config, script resolution, TTS readiness, and upload skipping without rendering |
| `--caption` | `""` | Custom social caption text |
| `--job-id` | `""` | Optional Cloudflare Worker queue job ID |
| `--existing-youtube-url` | `""` | Reuse an existing YouTube Short URL (skips YouTube upload) |
| `--pool` | `false` | Add rendered reel metadata to the Cloudflare Worker pool |

### `synth_and_render.py`

Synthesizes and renders one or more preset reels (or all 4 default presets when `--style` is omitted). Also accepts an optional positional `style_pos` argument.

| Flag | Default | Description |
|---|---|---|
| `--style` | `""` | Filter preset reels by style (`deep-dive`, `inside-out`, `night-file`, `paper-atlas`, `stick-story`, `tall-tale`) |
| `--tts-provider` | `TTS_PROVIDER` or `default` | TTS backend (`default`, `kokoro`, `gemini`, `elevenlabs`) |
| `--voice` | `TTS_VOICE` or `""` | Voice name or ID override |
| `--no-upload` | `false` | Skip YouTube and Instagram uploads |
| `--publish` | `false` | Attempt social publishing when credentials are configured |
| `--dry-run` | `false` | Validate config and print JSON plan without rendering |
| `--pool` | `false` | Add rendered reel to Worker 6-hour pool instead of immediate publish |

### `youtube_shorts_uploader.py`

Runs one-time OAuth2 setup or uploads an MP4 directly to YouTube Shorts via YouTube Data API v3.

| Flag | Default | Description |
|---|---|---|
| `--auth` | `false` | Run one-time interactive OAuth2 login (local callback on `http://127.0.0.1:8089`) and save `youtube_credentials.json` |
| `--client-secrets` | `client_secret.json` | Path to Google OAuth `client_secret.json` |
| `--video` | `""` | Path to MP4 file to upload |
| `--title` | `"Wait Until You See What Happens #Shorts"` | Video title |
| `--description` | `"Daily 3D explainers and untold stories."` | Video description |
| `--style` | `deep-dive` | Style slug used to pick the YouTube category ID |
| `--cover` | `""` | Optional path to a custom `1080x1920` cover JPEG |

---

## 7. Optional Instagram Meta Graph API and YouTube Shorts Upload Setup

Only follow this section if you want automatic social publishing. Without these credentials, video rendering works normally and uploading is skipped cleanly.

### Instagram Reels (Meta Graph API v22.0)

1. Switch your Instagram account to a **Business** or **Creator** (professional) account and link it to a **Facebook Page**.
2. Create an app in [Meta for Developers](https://developers.facebook.com/) with `instagram_basic`, `instagram_content_publish`, and `pages_read_engagement` permissions.
3. Obtain a Page Access Token and exchange it for a long-lived token (you can optionally use `make-permanent-token.mjs` or the local setup UI via `node setup-server.mjs`).
4. Set these variables in `.env` (and re-run `set -a && source .env && set +a`):
   - `META_PAGE_ACCESS_TOKEN`
   - `IG_BUSINESS_ACCOUNT_ID`
   - `FB_PAGE_ID`
   - `PUBLIC_VIDEO_BASE_URL` (optional HTTPS base URL where your rendered MP4 is reachable) or `LITTERBOX_UPLOAD="1"` (default temporary 72-hour upload used if `PUBLIC_VIDEO_BASE_URL` is blank; set `LITTERBOX_UPLOAD="0"` to disable).

### YouTube Shorts (YouTube Data API v3)

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and enable **YouTube Data API v3**.
2. Configure the OAuth consent screen and create an **OAuth 2.0 Client ID** (Desktop app), downloading `client_secret.json` into the repo root (gitignored).
3. Run the one-time interactive OAuth flow:

   ```bash
   python3 -B youtube_shorts_uploader.py --auth --client-secrets client_secret.json
   ```

   This writes `youtube_credentials.json` (also gitignored) and prints `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN` so you can copy them into `.env` or GitHub Actions Secrets.

4. To opt in to uploading:
   - Locally: omit `--no-upload` (or pass `--publish`) when running `generate_custom_topic_reel.py` or `synth_and_render.py`.
   - On GitHub Actions: set the `publish` workflow input to `true` and add the YouTube/Meta secrets to your repository's Actions Secrets.

---

## 8. Optional Cloudflare Worker and Daemon Notes

This repository also includes optional 24/7 Cloudflare Worker and local queue/webhook scripts if you want automated DM replies or remote job queuing:

- **Lightweight D1 Webhook Worker (`src/index.js`, default in [`wrangler.toml`](wrangler.toml))**:
  - Uses [`schema.sql`](schema.sql) for Cloudflare D1 tables (`owner_state`, `user_memories`, `messages`).
  - Copy `.dev.vars.example` to `.dev.vars`, then test locally or deploy:

    ```bash
    npx wrangler dev
    ```

    ```bash
    npx wrangler deploy
    ```

- **Full KV / Reels Queue Worker ([`cloudflare-worker-24-7.js`](cloudflare-worker-24-7.js))**:
  - Exposes `/poll`, `/reels/claim`, `/reels/publish`, `/reels/youtube-token`, and `/session` routes backed by `AVIDAY_KV`.
  - Pair with optional local runner scripts when `AVIDAY_WORKER_URL` is configured:
    - `reel_queue_daemon.py` (async job poller calling `generate_and_publish_custom_topic`)
    - `run_aviday_daemon.py` (sync `/poll` + `/reels/claim` runner)
    - `webhook_server.py` (local Meta webhook server)
    - `setup-server.mjs` (local setup & 3-tier DM simulator at `http://localhost:3333`)
    - `sync_ig_session.mjs` (helper for optional direct IG session sync)

---

## 9. Bundled Video-Production and Obsidian Skills

`project-aviday` bundles a complete library of AI agent skills (all sanitized of personal data and secrets) so you or your coding agent can inspect, customize, or build new video pipelines and Obsidian knowledge workflows.

### Core Faceless Shorts Skill

- **[`faceless-shorts-skill/faceless-shorts/SKILL.md`](faceless-shorts-skill/faceless-shorts/SKILL.md)** (also see [`README.md`](faceless-shorts-skill/faceless-shorts/README.md))
  - **What it does**: End-to-end 9:16 faceless shorts creation across all 6 styles (`deep-dive`, `night-file`, `stick-story`, `tall-tale`, `inside-out`, `paper-atlas`), plus standalone helpers (`new_video.sh`, `voice.py`, `words.py`, `estimate.py`, `capture.mjs`, `mix.py`).
  - **Example standalone commands** (separate from the root Python CLIs):

    ```bash
    faceless-shorts-skill/faceless-shorts/scripts/new_video.sh --list
    ```

    ```bash
    node faceless-shorts-skill/faceless-shorts/styles/stick-story/example/tools/capture.mjs check
    ```

### Bundled `video-skills/` (7 Packs)

| Skill Pack | Entrypoint | Purpose & Prerequisites |
|---|---|---|
| `claude-animated-shorts` | [`video-skills/claude-animated-shorts/SKILL.md`](video-skills/claude-animated-shorts/SKILL.md) | 55–70s vertical 3D cartoon story shorts rendered with Three.js + Remotion (Node.js, Python 3, FFmpeg) |
| `3d-model-anything` | [`video-skills/3d-model-anything/.agents/skills/scan-to-threejs/SKILL.md`](video-skills/3d-model-anything/.agents/skills/scan-to-threejs/SKILL.md) | Reconstruct editable Three.js 3D scenes from LiDAR/RoomPlan captures or photos (Node 22.12+, Python 3) |
| `MotionCraft` | [`video-skills/MotionCraft/skills/motioncraft/SKILL.md`](video-skills/MotionCraft/skills/motioncraft/SKILL.md) | Remotion motion-graphics explainers & reels with Whisper word sync and overlap QA (Node 18+, Remotion) |
| `blender-game-skills` | [`video-skills/blender-game-skills/skills/blender-image-to-3d/SKILL.md`](video-skills/blender-game-skills/skills/blender-image-to-3d/SKILL.md) | Turn reference images into rigged, UV-checked GLB/FBX 3D assets in Blender (Blender + `bpy`) |
| `clawmotion` | [`video-skills/clawmotion/LLM.md`](video-skills/clawmotion/LLM.md) ([`README.md`](video-skills/clawmotion/README.md)) | Isomorphic TypeScript programmatic video motion engine using WebCodecs / Skia Canvas / FFmpeg (Node.js or Bun + FFmpeg) |
| `roblox-blender-modelling` | [`video-skills/roblox-blender-modelling/SKILL.md`](video-skills/roblox-blender-modelling/SKILL.md) | Blender-to-Roblox 3D modeling, UV texel checks, and export validation (Blender) |
| `threejs-skills` | [`video-skills/threejs-skills/skills/threejs-fundamentals/SKILL.md`](video-skills/threejs-skills/skills/threejs-fundamentals/SKILL.md) ([`README.md`](video-skills/threejs-skills/README.md)) | 13 Three.js / R3F / WebGPU / glTF reference sub-skills for AI coding agents |

### Bundled `skills/` (6 Packs — Video, Reverse-Engineering, Remotion & Obsidian)

| Skill Pack | Entrypoint | Purpose & Prerequisites |
|---|---|---|
| `lemo-opuscar` | [`skills/lemo-opuscar/SKILL.md`](skills/lemo-opuscar/SKILL.md) | Direct and produce coded short films in ~99 artistic styles (`impasto`, `watercolor`, `ukiyoe`, etc.; Node.js, FFmpeg, Python 3) |
| `rea-video` | [`skills/rea-video/SKILL.md`](skills/rea-video/SKILL.md) | Reverse-engineer reference videos shot-by-shot into `VIDEO.md` + `report.html` remake plans (Python 3.10+, FFmpeg) |
| `2d-short-video-skill` | [`skills/2d-short-video-skill/SKILL.md`](skills/2d-short-video-skill/SKILL.md) | 9:16 2D philosophy/explainer Shorts with dual Canvas 2D + Remotion 2D engines (Node 22+, FFmpeg, Chrome, Python 3.10+) |
| `remotion-skills` | [`skills/remotion-skills/skills/remotion-best-practices/SKILL.md`](skills/remotion-skills/skills/remotion-best-practices/SKILL.md) ([`README.md`](skills/remotion-skills/README.md)) | 13 official Remotion skills (`remotion-captions`, `remotion-create`, `remotion-render`, `remotion-studio`, etc.; Node.js) |
| `obsidian-skills` | [`skills/obsidian-skills/README.md`](skills/obsidian-skills/README.md) | 7 Obsidian Agent Skills: [`obsidian-markdown`](skills/obsidian-skills/plugins/obsidian/skills/obsidian-markdown/SKILL.md), [`obsidian-bases`](skills/obsidian-skills/plugins/obsidian/skills/obsidian-bases/SKILL.md), [`json-canvas`](skills/obsidian-skills/plugins/obsidian/skills/json-canvas/SKILL.md), [`obsidian-cli`](skills/obsidian-skills/plugins/obsidian/skills/obsidian-cli/SKILL.md), [`obsidian-headless`](skills/obsidian-skills/plugins/obsidian/skills/obsidian-headless/SKILL.md), [`defuddle`](skills/obsidian-skills/plugins/obsidian/skills/defuddle/SKILL.md), and [`knap`](skills/obsidian-skills/plugins/obsidian/skills/knap/SKILL.md) |
| `obsidian-recall` | [`skills/obsidian-recall/SKILL.md`](skills/obsidian-recall/SKILL.md) | Save and review study notes, debugging postmortems, and active-recall cards in a local Obsidian vault (`~/Documents/ObsidianVault`) |

---

## 10. Running Tests and Troubleshooting

### Run the Unit Test Suite

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
```

Syntax-check all JavaScript/Node modules:

```bash
npm run check:js
```

### Common Beginner Issues

- **My `.env` keys are ignored**: Run `set -a && source .env && set +a` in your current shell before invoking Python scripts.
- **Chrome not found on Linux/macOS**: Set `CHROME="/path/to/google-chrome"` (or leave `CHROME=""` so auto-detection runs). Passing a nonexistent `CHROME` path exits immediately with code `1`.
- **WebGL crashes or slow rendering on headless Linux**: Set `SOFTWARE_GL="1"` and `FPS="24"`.
- **`--dry-run` exits with code `2`**: If you chose `--tts-provider kokoro`, `gemini`, or `elevenlabs`, verify that Kokoro models (`$FACELESS_HOME/kokoro`) or the matching API key (`GEMINI_API_KEY` / `ELEVENLABS_API_KEY`) are configured, or switch back to `--tts-provider default`.
