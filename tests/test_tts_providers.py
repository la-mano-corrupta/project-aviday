from __future__ import annotations

import array
import base64
import http.server
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
import tts_providers  # noqa: E402
sys.path.pop(0)


def _make_sample_wav_bytes(duration_s: float = 0.25, sr: int = 24000) -> bytes:
    n = int(duration_s * sr)
    buf = io.BytesIO()
    samples = array.array("h", [int(0.4 * 32767 * math.sin(2 * math.pi * 440.0 * i / sr)) for i in range(n)])
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


class TestTtsProviders(unittest.TestCase):
    def _clean_env(self, tmp: str, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for k in (
            "GEMINI_API_KEY",
            "GEMINI_API_KEYS",
            "ELEVENLABS_API_KEY",
            "TTS_PROVIDER",
            "TTS_VOICE",
            "META_PAGE_ACCESS_TOKEN",
            "IG_BUSINESS_ACCOUNT_ID",
            "YOUTUBE_CLIENT_ID",
            "YOUTUBE_CLIENT_SECRET",
            "YOUTUBE_REFRESH_TOKEN",
            "AVIDAY_WORKER_URL",
        ):
            env.pop(k, None)
        env["PROJECTS_DIR"] = tmp
        env["FACELESS_HOME"] = tmp
        if extra:
            env.update(extra)
        return env

    def test_provider_validation_and_all_four_dry_runs(self):
        self.assertEqual(tts_providers.TTS_PROVIDERS, ("default", "kokoro", "gemini", "elevenlabs"))
        with self.assertRaises(ValueError):
            tts_providers.resolve_tts_provider("invalid-provider")

        with tempfile.TemporaryDirectory() as tmp:
            # 1. default exits 0 even with zero keys and empty FACELESS_HOME
            for script in ("generate_custom_topic_reel.py", "synth_and_render.py"):
                res = subprocess.run(
                    [sys.executable, "-B", str(REPO_ROOT / script), "--tts-provider", "default", "--dry-run", "--no-upload"],
                    cwd=str(REPO_ROOT),
                    env=self._clean_env(tmp),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(res.returncode, 0, f"{script} default: {res.stderr}")
                payload = json.loads(res.stdout)
                self.assertEqual(payload["tts_provider"], "default")

            # 2. explicit non-default providers exit non-zero when missing creds/models
            missing_cases = (
                ("elevenlabs", "ELEVENLABS_API_KEY"),
                ("gemini", "GEMINI_API_KEY"),
                ("kokoro", "kokoro"),
            )
            for prov, expected_token in missing_cases:
                for script in ("generate_custom_topic_reel.py", "synth_and_render.py"):
                    res = subprocess.run(
                        [sys.executable, "-B", str(REPO_ROOT / script), "--tts-provider", prov, "--dry-run", "--no-upload"],
                        cwd=str(REPO_ROOT),
                        env=self._clean_env(tmp),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(res.returncode, 0, f"{script} {prov} unexpectedly exited 0")
                    combined = (res.stdout + "\n" + res.stderr).lower()
                    self.assertIn(expected_token.lower(), combined, f"{script} {prov}: {combined}")

            # 3. explicit providers exit 0 when valid non-placeholder keys/models are provided
            valid_cases = [
                ("elevenlabs", {"ELEVENLABS_API_KEY": "valid-el-key-123"}),
                ("gemini", {"GEMINI_API_KEY": "valid-gem-key-123"}),
            ]
            # Also test kokoro dry-run 0 exit when models + kokoro_onnx are present
            kdir = Path(tmp) / "kokoro"
            kdir.mkdir(parents=True, exist_ok=True)
            (kdir / "kokoro-v1.0.onnx").write_bytes(b"mock")
            (kdir / "voices-v1.0.bin").write_bytes(b"mock")
            if tts_providers.check_provider_readiness("kokoro")["credentials_present"] or (
                Path.home() / ".faceless-shorts" / "venv" / "bin" / "python"
            ).is_file():
                valid_cases.append(("kokoro", {}))

            for prov, env_extra in valid_cases:
                for script in ("generate_custom_topic_reel.py", "synth_and_render.py"):
                    res = subprocess.run(
                        [sys.executable, "-B", str(REPO_ROOT / script), "--tts-provider", prov, "--dry-run", "--no-upload"],
                        cwd=str(REPO_ROOT),
                        env=self._clean_env(tmp, env_extra),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(res.returncode, 0, f"{script} {prov} with creds failed: {res.stderr}")
                    payload = json.loads(res.stdout)
                    self.assertEqual(payload["tts_provider"], prov)
                    self.assertTrue(payload["credentials_present"])

    def test_extract_gemini_audio_bytes_outputs_untyped_steps_and_fallbacks(self):
        wav_bytes = _make_sample_wav_bytes(0.1)
        b64 = base64.b64encode(wav_bytes).decode("ascii")

        # 1. Interactions outputs[] (type == "audio")
        self.assertEqual(
            tts_providers._extract_gemini_audio_bytes(
                {"outputs": [{"type": "audio", "data": b64, "mime_type": "audio/wav"}]}
            ),
            wav_bytes,
        )
        # 2. Interactions outputs[] (mimeType audio/* without type="audio")
        self.assertEqual(
            tts_providers._extract_gemini_audio_bytes(
                {"outputs": [{"mimeType": "audio/pcm", "data": b64}]}
            ),
            wav_bytes,
        )
        # 3. Untyped steps[] (no step["type"] key, matching e2e_tests/stubs.py)
        self.assertEqual(
            tts_providers._extract_gemini_audio_bytes(
                {"steps": [{"content": [{"type": "audio", "data": b64, "mime_type": "audio/wav"}]}]}
            ),
            wav_bytes,
        )
        # 4. Typed model_output steps[]
        self.assertEqual(
            tts_providers._extract_gemini_audio_bytes(
                {"steps": [{"type": "model_output", "content": [{"type": "audio", "data": b64}]}]}
            ),
            wav_bytes,
        )
        # 5. candidates[].content.parts[].inlineData
        self.assertEqual(
            tts_providers._extract_gemini_audio_bytes(
                {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/wav", "data": b64}}]}}]}
            ),
            wav_bytes,
        )
        # 6. audioContent
        self.assertEqual(
            tts_providers._extract_gemini_audio_bytes({"audioContent": b64}),
            wav_bytes,
        )
        # 7. Empty / too short rejected
        self.assertIsNone(tts_providers._extract_gemini_audio_bytes({}))
        short_b64 = base64.b64encode(b"tiny").decode("ascii")
        self.assertIsNone(tts_providers._extract_gemini_audio_bytes({"outputs": [{"type": "audio", "data": short_b64}]}))

    def test_voice_precedence_and_placeholder_rejection(self):
        with mock.patch.dict(
            os.environ,
            {
                "TTS_VOICE": "env_tts_voice",
                "KOKORO_VOICE": "af_bella",
                "GEMINI_TTS_VOICE": "Kore",
                "ELEVENLABS_VOICE_ID": "el_env_id",
            },
            clear=True,
        ):
            self.assertEqual(tts_providers.resolve_voice("gemini", "deep-dive", cli_voice="Fenrir"), "Fenrir")
            self.assertEqual(tts_providers.resolve_voice("gemini", "deep-dive"), "env_tts_voice")

        with mock.patch.dict(os.environ, {"ELEVENLABS_VOICE_ID": "el_specific"}, clear=True):
            self.assertEqual(tts_providers.resolve_voice("elevenlabs", "deep-dive"), "el_specific")

        self.assertFalse(tts_providers.is_real_secret("YOUR_GOOGLE_AI_STUDIO_API_KEY"))
        self.assertFalse(tts_providers.is_real_secret("CHANGE_ME_TOKEN"))
        self.assertFalse(tts_providers.is_real_secret(""))
        self.assertTrue(tts_providers.is_real_secret("demo-nonempty-token-1234"))

    def test_missing_keys_and_kokoro_models_fail_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "proj"
            p.mkdir()
            (p / "script.json").write_text(json.dumps({"lines": [{"text": "Hello world."}]}))

            with mock.patch.dict(os.environ, {"FACELESS_HOME": tmp}, clear=True):
                with self.assertRaises(RuntimeError):
                    tts_providers.synthesize_project_audio(p, "deep-dive", provider="gemini")
                with self.assertRaises(RuntimeError):
                    tts_providers.synthesize_project_audio(p, "deep-dive", provider="elevenlabs")
                with self.assertRaises(RuntimeError):
                    tts_providers.synthesize_project_audio(p, "deep-dive", provider="kokoro")

    def test_gemini_and_elevenlabs_mock_http_and_audio_contract(self):
        wav_bytes = _make_sample_wav_bytes(0.3)
        b64_audio = base64.b64encode(wav_bytes).decode("ascii")
        recorded_requests: list[dict] = []

        class MockTtsHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
                recorded_requests.append({"path": self.path, "body": json.loads(raw_body)})
                if self.path == "/v1beta/interactions":
                    resp = {
                        "outputs": [{"type": "audio", "data": b64_audio, "mime_type": "audio/wav"}],
                        "steps": [
                            {
                                "content": [{"type": "audio", "data": b64_audio, "mime_type": "audio/wav"}],
                            }
                        ],
                    }
                    out = json.dumps(resp).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(out)))
                    self.end_headers()
                    self.wfile.write(out)
                elif self.path.startswith("/v1/text-to-speech/"):
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Content-Length", str(len(wav_bytes)))
                    self.end_headers()
                    self.wfile.write(wav_bytes)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                return

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockTtsHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            base = f"http://127.0.0.1:{port}"
            for prov, env_extra in (
                ("gemini", {"GEMINI_API_KEY": "test-gemini-key", "GEMINI_BASE_URL": base}),
                ("elevenlabs", {"ELEVENLABS_API_KEY": "test-el-key", "ELEVENLABS_BASE_URL": base}),
            ):
                recorded_requests.clear()
                with tempfile.TemporaryDirectory() as tmp:
                    p = Path(tmp) / f"proj_{prov}"
                    p.mkdir()
                    (p / "script.json").write_text(
                        json.dumps(
                            {
                                "lead": 0.1,
                                "outro": 0.1,
                                "gap": 0.1,
                                "lines": [
                                    {"text": "Wait *for this."},
                                    {"text": "Second line works!"},
                                ],
                            }
                        )
                    )
                    with mock.patch.dict(os.environ, env_extra, clear=False):
                        res = tts_providers.synthesize_project_audio(p, "deep-dive", provider=prov, voice="TestVoice")
                    self.assertEqual(res["provider"], prov)
                    self.assertEqual(res["voice"], "TestVoice")

                    # Verify asterisk stripping
                    self.assertEqual(len(recorded_requests), 2)
                    for req in recorded_requests:
                        self.assertNotIn("*", json.dumps(req["body"]))

                    # Verify 24kHz mono 16-bit PCM WAV contract
                    narration = p / "data" / "narration.wav"
                    self.assertTrue(narration.is_file())
                    with wave.open(str(narration), "rb") as wf:
                        self.assertEqual(wf.getnchannels(), 1)
                        self.assertEqual(wf.getsampwidth(), 2)
                        self.assertEqual(wf.getframerate(), 24000)
                        self.assertGreater(wf.getnframes(), 0)

                    # Verify lines.json & words.json schema
                    lines_json = json.loads((p / "data" / "lines.json").read_text())
                    self.assertGreater(lines_json["duration"], 0)
                    self.assertEqual(len(lines_json["lines"]), 2)
                    words_json = json.loads((p / "data" / "words.json").read_text())
                    self.assertGreater(len(words_json), 0)
                    for w in words_json:
                        self.assertIn("w", w)
                        self.assertIn("line", w)
                        self.assertIn("s", w)
                        self.assertIn("e", w)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
