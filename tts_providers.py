#!/usr/bin/env python3
"""
Selectable 4-Option TTS Router for project-aviday.

Supported providers (`--tts-provider` / `TTS_PROVIDER`):
  - default    : Existing Aviday default (`auto` Kokoro-if-installed / edge-tts fallback,
                 or `edge-tts` in batch mode, with offline fallback if unreachable).
  - kokoro     : Local offline Kokoro-82M via faceless-shorts `voice.py` + `words.py`.
  - gemini     : Google Gemini TTS Interactions API (`gemini-3.8-flash-tts`) + `ffmpeg` + `words.py`.
  - elevenlabs : ElevenLabs REST API (`/v1/text-to-speech/{voice_id}`) + `ffmpeg` + `words.py`.

Top-level imports are strictly Python 3.9+ standard library so CLI `--help`, `--dry-run`,
and API-backed TTS providers work without requiring numpy/scipy in the outer Python process.
"""
from __future__ import annotations

import array
import base64
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path

TTS_PROVIDERS: tuple[str, ...] = ("default", "kokoro", "gemini", "elevenlabs")
SAMPLE_RATE = 24000

SKILL_DIR = Path(__file__).resolve().parent / "faceless-shorts-skill" / "faceless-shorts"

DEFAULT_STYLE_EDGE_VOICES: dict[str, str] = {
    "deep-dive": "en-US-AndrewNeural",
    "night-file": "en-US-ChristopherNeural",
    "stick-story": "en-US-GuyNeural",
    "tall-tale": "en-US-BrianNeural",
    "inside-out": "en-US-AndrewNeural",
    "paper-atlas": "en-US-AndrewNeural",
}

DEFAULT_STYLE_KOKORO_VOICES: dict[str, str] = {
    "deep-dive": "am_michael",
    "night-file": "am_onyx",
    "stick-story": "am_puck",
    "tall-tale": "am_michael",
    "inside-out": "am_michael",
    "paper-atlas": "am_michael",
}

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash-tts"
DEFAULT_GEMINI_VOICE = "Puck"
DEFAULT_ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
DEFAULT_ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"


def get_faceless_home() -> Path:
    raw = os.environ.get("FACELESS_HOME", "").strip()
    return Path(raw).expanduser() if raw else (Path.home() / ".faceless-shorts")


def get_projects_dir() -> Path:
    raw = os.environ.get("PROJECTS_DIR", "").strip()
    return Path(raw).expanduser() if raw else (Path.home() / "faceless-shorts")


def is_real_secret(val: str | None) -> bool:
    if not val:
        return False
    s = str(val).strip()
    if not s:
        return False
    upper = s.upper()
    if upper.startswith(("YOUR_", "CHANGE_ME", "PLACEHOLDER", "EXAMPLE_")):
        return False
    if s.startswith("<") and s.endswith(">"):
        return False
    return True


def load_gemini_keys() -> list[str]:
    keys: list[str] = []
    for env_name in ("GEMINI_API_KEYS", "GEMINI_API_KEY"):
        raw = os.environ.get(env_name, "")
        if not raw:
            continue
        for part in re.split(r"[\n,]+", raw):
            k = part.strip().strip('"').strip("'")
            if is_real_secret(k) and k not in keys:
                keys.append(k)
    return keys


def resolve_tts_provider(cli_provider: str | None = None) -> str:
    raw = cli_provider if (cli_provider is not None and str(cli_provider).strip() != "") else os.environ.get("TTS_PROVIDER", "")
    provider = str(raw).strip().lower() or "default"
    if provider not in TTS_PROVIDERS:
        raise ValueError(
            f"Invalid TTS provider '{provider}'. Must be one of: {', '.join(TTS_PROVIDERS)}"
        )
    return provider


def _venv_python_candidates() -> list[Path]:
    rel = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    candidates: list[Path] = [Path(sys.executable)]
    fhome = get_faceless_home()
    candidates.append(fhome / "venv" / rel)
    candidates.append(Path.home() / ".faceless-shorts" / "venv" / rel)

    deduped: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p)
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped


def _python_has_modules(py_path: Path, required_modules: tuple[str, ...]) -> bool:
    if not required_modules:
        return True
    if os.path.abspath(str(py_path)) == os.path.abspath(sys.executable):
        for mod in required_modules:
            try:
                importlib.import_module(mod)
            except Exception:
                return False
        return True
    if not py_path.is_file():
        return False
    code = "; ".join(f"import {m}" for m in required_modules)
    try:
        res = subprocess.run(
            [str(py_path), "-B", "-c", code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def resolve_python_bin(required_modules: tuple[str, ...] = ()) -> str:
    for cand in _venv_python_candidates():
        if cand.is_file() and _python_has_modules(cand, required_modules):
            return str(cand)
    return sys.executable


def kokoro_models_present(faceless_home: Path | None = None) -> bool:
    kdir = (faceless_home or get_faceless_home()) / "kokoro"
    return (kdir / "kokoro-v1.0.onnx").is_file() and (kdir / "voices-v1.0.bin").is_file()


def _detect_default_backend(default_mode: str = "auto") -> str:
    if default_mode == "auto":
        if kokoro_models_present() and _python_has_modules(
            Path(resolve_python_bin(("kokoro_onnx", "numpy", "scipy"))),
            ("kokoro_onnx", "numpy", "scipy"),
        ):
            return "kokoro"
    return "edge"


def resolve_voice(
    provider: str,
    style: str = "deep-dive",
    cli_voice: str | None = None,
    script_voice: str | None = None,
    default_mode: str = "auto",
) -> str:
    if cli_voice and str(cli_voice).strip():
        return str(cli_voice).strip()
    env_tts_voice = os.environ.get("TTS_VOICE", "").strip()
    if env_tts_voice:
        return env_tts_voice

    effective = provider if provider != "default" else _detect_default_backend(default_mode)
    if effective == "kokoro":
        return (
            os.environ.get("KOKORO_VOICE", "").strip()
            or (str(script_voice).strip() if script_voice else "")
            or DEFAULT_STYLE_KOKORO_VOICES.get(style, "am_michael")
        )
    if effective == "gemini":
        return os.environ.get("GEMINI_TTS_VOICE", "").strip() or DEFAULT_GEMINI_VOICE
    if effective == "elevenlabs":
        return os.environ.get("ELEVENLABS_VOICE_ID", "").strip() or DEFAULT_ELEVENLABS_VOICE_ID
    return (
        os.environ.get("EDGE_TTS_VOICE", "").strip()
        or DEFAULT_STYLE_EDGE_VOICES.get(style, "en-US-AndrewNeural")
    )


def check_provider_readiness(
    provider: str,
    style: str = "deep-dive",
    cli_voice: str | None = None,
    script_voice: str | None = None,
    default_mode: str = "auto",
) -> dict:
    resolved_provider = resolve_tts_provider(provider)
    backend = resolved_provider if resolved_provider != "default" else _detect_default_backend(default_mode)
    voice = resolve_voice(
        resolved_provider,
        style=style,
        cli_voice=cli_voice,
        script_voice=script_voice,
        default_mode=default_mode,
    )

    if backend == "kokoro":
        models_ok = kokoro_models_present()
        deps_ok = _python_has_modules(
            Path(resolve_python_bin(("kokoro_onnx", "numpy", "scipy"))),
            ("kokoro_onnx", "numpy", "scipy"),
        )
        creds_ok = models_ok and deps_ok
        detail = (
            "kokoro models and dependencies ready"
            if creds_ok
            else f"missing kokoro models under {get_faceless_home() / 'kokoro'} or kokoro_onnx"
        )
    elif backend == "gemini":
        creds_ok = len(load_gemini_keys()) > 0
        detail = "GEMINI_API_KEY configured" if creds_ok else "GEMINI_API_KEY / GEMINI_API_KEYS not configured"
    elif backend == "elevenlabs":
        creds_ok = is_real_secret(os.environ.get("ELEVENLABS_API_KEY"))
        detail = "ELEVENLABS_API_KEY configured" if creds_ok else "ELEVENLABS_API_KEY not configured"
    else:
        creds_ok = True
        detail = "edge-tts (with offline local fallback in default mode)"

    return {
        "provider": resolved_provider,
        "resolved_backend": backend,
        "voice": voice,
        "credentials_present": creds_ok,
        "detail": detail,
    }


def _clean_tts_text(text: str) -> str:
    cleaned = re.sub(r"\*+", "", text or "").strip()
    return cleaned or "..."


def _transcode_to_pcm24k_mono(raw_path: Path, wav_path: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(raw_path),
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-sample_fmt",
        "s16",
        str(wav_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode == 0 and wav_path.is_file() and wav_path.stat().st_size > 44:
        return
    # Fallback for headerless 24kHz s16le PCM responses
    cmd_pcm = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "s16le",
        "-ar",
        str(SAMPLE_RATE),
        "-ac",
        "1",
        "-i",
        str(raw_path),
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-sample_fmt",
        "s16",
        str(wav_path),
    ]
    res2 = subprocess.run(cmd_pcm, capture_output=True, text=True, check=False)
    if res2.returncode != 0 or not wav_path.is_file() or wav_path.stat().st_size <= 44:
        raise RuntimeError(
            f"ffmpeg transcode failed for {raw_path.name}: {res.stderr.strip() or res2.stderr.strip()}"
        )


def _read_pcm16_mono(wav_path: Path) -> array.array:
    with wave.open(str(wav_path), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != SAMPLE_RATE:
            raise RuntimeError(
                f"Unexpected WAV format in {wav_path}: ch={wf.getnchannels()} sw={wf.getsampwidth()} sr={wf.getframerate()}"
            )
        raw = wf.readframes(wf.getnframes())
    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _trim_silence_pcm(samples: array.array, threshold: int = 250) -> array.array:
    n = len(samples)
    if n == 0:
        return samples
    first = None
    last = None
    for idx, val in enumerate(samples):
        if abs(val) > threshold:
            if first is None:
                first = idx
            last = idx
    if first is None or last is None:
        return samples
    a = max(0, first - int(0.01 * SAMPLE_RATE))
    b = min(n, last + int(0.03 * SAMPLE_RATE))
    return samples[a:b]


def _write_pcm16_mono(wav_path: Path, samples: array.array) -> None:
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    out = array.array("h", samples)
    if sys.byteorder != "little":
        out.byteswap()
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(out.tobytes())


def _run_words_alignment(proj_dir: Path) -> None:
    py = resolve_python_bin(("faster_whisper", "numpy"))
    if not _python_has_modules(Path(py), ("faster_whisper", "numpy")):
        py = resolve_python_bin()
    subprocess.run(
        [py, str(SKILL_DIR / "scripts" / "words.py"), str(proj_dir)],
        check=True,
    )


def _assemble_wav_and_lines(
    proj_dir: Path,
    script: dict,
    line_clips: list[array.array],
    provider: str,
    voice: str,
) -> Path:
    lead = float(script.get("lead", 0.4))
    outro = float(script.get("outro", 0.9))
    default_gap = float(script.get("gap", 0.32))

    out_samples = array.array("h", [0] * max(0, int(lead * SAMPLE_RATE)))
    t_cur = len(out_samples) / SAMPLE_RATE
    lines_meta: list[dict] = []

    for i, (ln, clip) in enumerate(zip(script["lines"], line_clips)):
        start_s = round(t_cur, 3)
        out_samples.extend(clip)
        clip_dur = len(clip) / SAMPLE_RATE
        end_s = round(t_cur + clip_dur, 3)
        lines_meta.append(
            {
                "i": i,
                "text": ln["text"],
                "start": start_s,
                "end": max(round(start_s + 0.1, 3), end_s),
            }
        )
        gap_s = float(ln.get("gap", default_gap))
        gap_n = max(0, int(gap_s * SAMPLE_RATE))
        if gap_n:
            out_samples.extend([0] * gap_n)
        t_cur = len(out_samples) / SAMPLE_RATE

    outro_n = max(0, int(outro * SAMPLE_RATE))
    if outro_n:
        out_samples.extend([0] * outro_n)

    if len(out_samples) == 0:
        out_samples.extend([0] * SAMPLE_RATE)

    peak = max((abs(s) for s in out_samples), default=0)
    if peak > 0:
        target_peak = int(0.9 * 32767)
        scale = target_peak / peak
        for idx, s in enumerate(out_samples):
            v = int(round(s * scale))
            if v > 32767:
                v = 32767
            elif v < -32767:
                v = -32767
            out_samples[idx] = v

    data_dir = proj_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    narration_wav = data_dir / "narration.wav"
    _write_pcm16_mono(narration_wav, out_samples)

    total_dur = round(len(out_samples) / SAMPLE_RATE, 3)
    (data_dir / "lines.json").write_text(
        json.dumps(
            {
                "duration": total_dur,
                "provider": provider,
                "voice": voice,
                "lines": lines_meta,
            },
            indent=1,
        )
    )
    _run_words_alignment(proj_dir)
    print(f"   ✅ Synthesized {narration_wav} ({total_dur:.2f}s, provider={provider}, voice={voice})", flush=True)
    return narration_wav


def _extract_audio_b64_from_item(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    item_type = str(item.get("type") or "").lower()
    mime = str(item.get("mime_type") or item.get("mimeType") or "").lower()
    if item.get("data") and (item_type == "audio" or mime.startswith("audio/")):
        return str(item["data"])
    inline = item.get("inlineData") or item.get("inline_data")
    if isinstance(inline, dict) and inline.get("data"):
        return str(inline["data"])
    return None


def _extract_gemini_audio_bytes(data: dict) -> bytes | None:
    audio_b64 = None
    # 1. Standard Gemini Interactions top-level outputs array
    for item in data.get("outputs", []):
        audio_b64 = _extract_audio_b64_from_item(item)
        if not audio_b64 and isinstance(item, dict):
            for sub in item.get("content", []):
                audio_b64 = _extract_audio_b64_from_item(sub)
                if audio_b64:
                    break
        if audio_b64:
            break

    # 2. Gemini Interactions steps array (both typed model_output and untyped steps)
    if not audio_b64:
        for step in data.get("steps", []):
            if not isinstance(step, dict):
                continue
            for item in step.get("content", []):
                audio_b64 = _extract_audio_b64_from_item(item)
                if audio_b64:
                    break
            if audio_b64:
                break

    # 3. Standard generateContent candidates[].content.parts[]
    if not audio_b64:
        for cand in data.get("candidates", []):
            parts = cand.get("content", {}).get("parts", [])
            for part in parts:
                inline = part.get("inlineData") or part.get("inline_data") or {}
                if inline.get("data"):
                    audio_b64 = inline["data"]
                    break
            if audio_b64:
                break

    # 4. Google TTS audioContent fallback
    if not audio_b64 and data.get("audioContent"):
        audio_b64 = data["audioContent"]
    if not audio_b64:
        return None
    raw = base64.b64decode(audio_b64)
    return raw if len(raw) >= 44 else None


def _synthesize_gemini(proj_dir: Path, script: dict, style: str, voice: str) -> Path:
    keys = load_gemini_keys()
    if not keys:
        raise RuntimeError(
            "GEMINI_API_KEY (or GEMINI_API_KEYS) is not configured for --tts-provider=gemini."
        )
    base_url = (os.environ.get("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com").rstrip("/")
    model = (os.environ.get("GEMINI_TTS_MODEL") or DEFAULT_GEMINI_MODEL).strip()
    endpoint = f"{base_url}/v1beta/interactions"
    delivery_style = f"clear engaging {style} short-form video narrator"

    clips: list[array.array] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for i, ln in enumerate(script["lines"]):
            clean_text = _clean_tts_text(ln["text"])
            payload = json.dumps(
                {
                    "model": model,
                    "input": [
                        {
                            "type": "user_input",
                            "content": [
                                {
                                    "type": "text",
                                    "text": clean_text,
                                    "annotations": [
                                        {"type": "speech_metadata", "style": delivery_style}
                                    ],
                                }
                            ],
                        }
                    ],
                    "response_format": {"type": "audio"},
                    "generation_config": {"speech_config": [{"voice": voice}]},
                }
            ).encode("utf-8")

            raw_bytes: bytes | None = None
            last_err: Exception | None = None
            max_attempts = max(len(keys) * 2, 3)
            for attempt in range(max_attempts):
                key = keys[(i + attempt) % len(keys)]
                req = urllib.request.Request(
                    endpoint,
                    data=payload,
                    headers={
                        "x-goog-api-key": key,
                        "Content-Type": "application/json",
                        "Api-Revision": "2026-05-20",
                    },
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=90) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                    raw_bytes = _extract_gemini_audio_bytes(body)
                    if not raw_bytes:
                        raise RuntimeError(f"Gemini TTS returned empty/invalid audio for line {i}")
                    break
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode("utf-8", "ignore")[:240]
                    last_err = RuntimeError(f"Gemini TTS HTTP {e.code}: {err_body}")
                    if e.code == 400:
                        raise last_err
                    if e.code in (401, 403) and attempt + 1 >= len(keys):
                        raise last_err
                    time.sleep(min(2.0, 0.3 * (attempt + 1)))
                except Exception as e:
                    last_err = e
                    time.sleep(min(2.0, 0.3 * (attempt + 1)))

            if not raw_bytes:
                raise RuntimeError(f"Gemini TTS failed on line {i}: {last_err}")

            raw_file = tmp / f"gemini_{i}.bin"
            wav_file = tmp / f"gemini_{i}.wav"
            raw_file.write_bytes(raw_bytes)
            _transcode_to_pcm24k_mono(raw_file, wav_file)
            clips.append(_trim_silence_pcm(_read_pcm16_mono(wav_file)))

    return _assemble_wav_and_lines(proj_dir, script, clips, provider="gemini", voice=voice)


def _synthesize_elevenlabs(proj_dir: Path, script: dict, voice: str) -> Path:
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not is_real_secret(api_key):
        raise RuntimeError("ELEVENLABS_API_KEY is not configured for --tts-provider=elevenlabs.")
    base_url = (os.environ.get("ELEVENLABS_BASE_URL") or "https://api.elevenlabs.io").rstrip("/")
    model_id = (os.environ.get("ELEVENLABS_MODEL_ID") or DEFAULT_ELEVENLABS_MODEL_ID).strip()
    endpoint = f"{base_url}/v1/text-to-speech/{urllib.parse.quote(voice, safe='')}"

    clips: list[array.array] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for i, ln in enumerate(script["lines"]):
            clean_text = _clean_tts_text(ln["text"])
            payload = json.dumps(
                {
                    "text": clean_text,
                    "model_id": model_id,
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                }
            ).encode("utf-8")

            raw_bytes: bytes | None = None
            last_err: Exception | None = None
            for attempt in range(3):
                req = urllib.request.Request(
                    endpoint,
                    data=payload,
                    headers={
                        "xi-api-key": api_key,
                        "Content-Type": "application/json",
                        "Accept": "audio/mpeg",
                    },
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=90) as resp:
                        raw_bytes = resp.read()
                    if not raw_bytes or len(raw_bytes) < 44:
                        raise RuntimeError(f"ElevenLabs returned insufficient audio ({len(raw_bytes or b'')} bytes)")
                    break
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode("utf-8", "ignore")[:240]
                    last_err = RuntimeError(f"ElevenLabs TTS HTTP {e.code}: {err_body}")
                    if e.code in (400, 401, 403, 404):
                        raise last_err
                    time.sleep(min(2.0, 0.3 * (attempt + 1)))
                except Exception as e:
                    last_err = e
                    time.sleep(min(2.0, 0.3 * (attempt + 1)))

            if not raw_bytes:
                raise RuntimeError(f"ElevenLabs TTS failed on line {i}: {last_err}")

            raw_file = tmp / f"el_{i}.mp3"
            wav_file = tmp / f"el_{i}.wav"
            raw_file.write_bytes(raw_bytes)
            _transcode_to_pcm24k_mono(raw_file, wav_file)
            clips.append(_trim_silence_pcm(_read_pcm16_mono(wav_file)))

    return _assemble_wav_and_lines(proj_dir, script, clips, provider="elevenlabs", voice=voice)


def _synthesize_kokoro(proj_dir: Path, voice: str) -> Path:
    fhome = get_faceless_home()
    kdir = fhome / "kokoro"
    auto_dl = os.environ.get("KOKORO_AUTO_DOWNLOAD", "0") == "1"
    if not kokoro_models_present(fhome) and not auto_dl:
        raise RuntimeError(
            f"Kokoro models not found in {kdir}. Run faceless-shorts setup.sh or set KOKORO_AUTO_DOWNLOAD=1."
        )
    py = resolve_python_bin(("kokoro_onnx", "numpy", "scipy"))
    if not _python_has_modules(Path(py), ("kokoro_onnx", "numpy", "scipy")):
        raise RuntimeError(
            "kokoro_onnx / numpy / scipy not installed in active Python or FACELESS_HOME venv."
        )
    env = os.environ.copy()
    env["FACELESS_HOME"] = str(fhome)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [py, "-B", str(SKILL_DIR / "scripts" / "voice.py"), str(proj_dir)]
    if voice:
        cmd.extend(["--voice", voice])
    subprocess.run(cmd, env=env, check=True)
    _run_words_alignment(proj_dir)
    return proj_dir / "data" / "narration.wav"


def _synthesize_edge_via_subprocess(lines: list[dict], tmp_dir: Path, primary_voice: str) -> bool:
    py = resolve_python_bin(("edge_tts",))
    if not _python_has_modules(Path(py), ("edge_tts",)):
        return False
    job_spec = [
        {"i": i, "text": _clean_tts_text(ln["text"]), "out": str(tmp_dir / f"edge_{i}.mp3")}
        for i, ln in enumerate(lines)
    ]
    spec_path = tmp_dir / "edge_jobs.json"
    spec_path.write_text(json.dumps(job_spec))
    helper = (
        "import asyncio, json, sys, edge_tts\n"
        "jobs = json.loads(open(sys.argv[1]).read())\n"
        "voices = [sys.argv[2], 'en-US-ChristopherNeural', 'en-US-GuyNeural', 'en-US-BrianNeural']\n"
        "async def run():\n"
        "  for j in jobs:\n"
        "    ok = False\n"
        "    for idx, v in enumerate(voices):\n"
        "      try:\n"
        "        await edge_tts.Communicate(j['text'], v, rate=('+5%' if idx == 0 else '+0%')).save(j['out'])\n"
        "        import os\n"
        "        if os.path.exists(j['out']) and os.path.getsize(j['out']) > 200:\n"
        "          ok = True; break\n"
        "      except Exception:\n"
        "        await asyncio.sleep(0.4)\n"
        "    if not ok:\n"
        "      raise RuntimeError('edge-tts failed for line ' + str(j['i']))\n"
        "asyncio.run(run())\n"
    )
    res = subprocess.run([py, "-B", "-c", helper, str(spec_path), primary_voice], check=False)
    return res.returncode == 0


def _synthesize_os_or_cadence_fallback(proj_dir: Path, script: dict, voice: str) -> Path:
    """Offline safety net used ONLY when provider='default' and online TTS is unreachable."""
    print("   ⚠️ Online edge-tts/gTTS unreachable; using offline fallback audio synthesis.", flush=True)
    say_bin = shutil.which("say")
    espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
    if say_bin or espeak_bin:
        try:
            clips: list[array.array] = []
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                for i, ln in enumerate(script["lines"]):
                    clean_text = _clean_tts_text(ln["text"])
                    raw_out = tmp / f"os_{i}.aiff" if say_bin else tmp / f"os_{i}.wav"
                    wav_out = tmp / f"os_24k_{i}.wav"
                    if say_bin:
                        subprocess.run([say_bin, "-o", str(raw_out), clean_text], check=True)
                    else:
                        subprocess.run([espeak_bin, "-w", str(raw_out), clean_text], check=True)
                    _transcode_to_pcm24k_mono(raw_out, wav_out)
                    clips.append(_trim_silence_pcm(_read_pcm16_mono(wav_out)))
            return _assemble_wav_and_lines(proj_dir, script, clips, provider="default-offline", voice=voice)
        except Exception as e:
            print(f"   ⚠️ Local OS TTS fallback skipped ({e}); using cadence WAV.", flush=True)

    # Pure stdlib deterministic non-silent cadence WAV matching estimate.py timings
    subprocess.run(
        [resolve_python_bin(), "-B", str(SKILL_DIR / "scripts" / "estimate.py"), str(proj_dir)],
        check=True,
    )
    lines_data = json.loads((proj_dir / "data" / "lines.json").read_text())
    dur = max(0.5, float(lines_data.get("duration", 1.0)))
    n_total = int(dur * SAMPLE_RATE)
    samples = array.array("h", [0] * n_total)
    for ln in lines_data.get("lines", []):
        i0 = max(0, int(float(ln["start"]) * SAMPLE_RATE))
        i1 = min(n_total, int(float(ln["end"]) * SAMPLE_RATE))
        for k in range(i0, i1):
            t = (k - i0) / SAMPLE_RATE
            env = math.sin(math.pi * (k - i0) / max(1, i1 - i0))
            val = math.sin(2 * math.pi * 220.0 * t) * 0.18 + math.sin(2 * math.pi * 330.0 * t) * 0.08
            samples[k] = int(max(-32767, min(32767, val * env * 32767)))
    out_wav = proj_dir / "data" / "narration.wav"
    _write_pcm16_mono(out_wav, samples)
    return out_wav


def _synthesize_edge_or_offline(proj_dir: Path, script: dict, voice: str) -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        ok_edge = _synthesize_edge_via_subprocess(script["lines"], tmp, voice)
        if not ok_edge:
            # Try Google Translate TTS HTTP fallback
            try:
                for i, ln in enumerate(script["lines"]):
                    q = urllib.parse.quote(_clean_tts_text(ln["text"])[:200])
                    url = f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=en&q={q}"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    mp3_bytes = urllib.request.urlopen(req, timeout=15).read()
                    if len(mp3_bytes) < 100:
                        raise RuntimeError("Empty gTTS response")
                    (tmp / f"edge_{i}.mp3").write_bytes(mp3_bytes)
                ok_edge = True
            except Exception:
                ok_edge = False

        if not ok_edge:
            return _synthesize_os_or_cadence_fallback(proj_dir, script, voice)

        clips: list[array.array] = []
        for i in range(len(script["lines"])):
            mp3_path = tmp / f"edge_{i}.mp3"
            wav_path = tmp / f"edge_{i}.wav"
            _transcode_to_pcm24k_mono(mp3_path, wav_path)
            clips.append(_trim_silence_pcm(_read_pcm16_mono(wav_path)))

    return _assemble_wav_and_lines(proj_dir, script, clips, provider="default", voice=voice)


def synthesize_project_audio(
    proj_dir: Path | str,
    style: str = "deep-dive",
    provider: str | None = None,
    voice: str | None = None,
    default_mode: str = "auto",
) -> dict:
    proj_path = Path(proj_dir)
    script = json.loads((proj_path / "script.json").read_text())
    resolved_provider = resolve_tts_provider(provider)
    backend = resolved_provider if resolved_provider != "default" else _detect_default_backend(default_mode)
    resolved_voice = resolve_voice(
        resolved_provider,
        style=style,
        cli_voice=voice,
        script_voice=script.get("voice"),
        default_mode=default_mode,
    )

    print(
        f"   🎙️ TTS provider={resolved_provider} (backend={backend}, voice={resolved_voice})",
        flush=True,
    )

    if backend == "kokoro":
        wav_path = _synthesize_kokoro(proj_path, resolved_voice)
    elif backend == "gemini":
        wav_path = _synthesize_gemini(proj_path, script, style, resolved_voice)
    elif backend == "elevenlabs":
        wav_path = _synthesize_elevenlabs(proj_path, script, resolved_voice)
    else:
        wav_path = _synthesize_edge_or_offline(proj_path, script, resolved_voice)

    return {
        "provider": resolved_provider,
        "backend": backend,
        "voice": resolved_voice,
        "narration_wav": str(wav_path),
    }
