from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_py(script: str, args: list[str], env_override: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for k in (
        "META_PAGE_ACCESS_TOKEN",
        "IG_BUSINESS_ACCOUNT_ID",
        "FB_PAGE_ID",
        "YOUTUBE_CLIENT_ID",
        "YOUTUBE_CLIENT_SECRET",
        "YOUTUBE_REFRESH_TOKEN",
        "GEMINI_API_KEY",
        "GEMINI_API_KEYS",
        "ELEVENLABS_API_KEY",
        "AVIDAY_WORKER_URL",
        "TTS_PROVIDER",
        "TTS_VOICE",
    ):
        env.pop(k, None)
    if env_override:
        env.update(env_override)
    return subprocess.run(
        [sys.executable, "-B", str(REPO_ROOT / script), *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class TestCliAndDecoupling(unittest.TestCase):
    def test_generate_cli_help_exposes_all_contract_flags(self):
        res = _run_py("generate_custom_topic_reel.py", ["--help"])
        self.assertEqual(res.returncode, 0, res.stderr)
        for flag in (
            "--style",
            "--topic",
            "--script",
            "--tts-provider",
            "--voice",
            "--no-upload",
            "--publish",
            "--dry-run",
            "--caption",
            "--job-id",
            "--existing-youtube-url",
            "--pool",
        ):
            self.assertIn(flag, res.stdout)

    def test_synth_cli_help_exposes_all_contract_flags(self):
        res = _run_py("synth_and_render.py", ["--help"])
        self.assertEqual(res.returncode, 0, res.stderr)
        for flag in ("--style", "--tts-provider", "--voice", "--no-upload", "--publish", "--dry-run", "--pool"):
            self.assertIn(flag, res.stdout)

    def test_root_python_modules_import_cleanly(self):
        for mod in (
            "tts_providers",
            "youtube_shorts_uploader",
            "synth_and_render",
            "generate_custom_topic_reel",
            "webhook_server",
            "reel_queue_daemon",
        ):
            res = subprocess.run(
                [sys.executable, "-B", "-c", f"import {mod}"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, f"import {mod} failed on {sys.version}: {res.stderr}")

    def test_publish_flag_and_placeholder_worker_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            res_pub = _run_py(
                "generate_custom_topic_reel.py",
                ["--style", "deep-dive", "--dry-run", "--publish"],
                env_override={"PROJECTS_DIR": tmp, "FACELESS_HOME": tmp, "AVIDAY_WORKER_URL": "YOUR_WORKER_URL"},
            )
            self.assertEqual(res_pub.returncode, 0, res_pub.stderr)
            d_pub = json.loads(res_pub.stdout)
            self.assertTrue(d_pub["publish"])
            self.assertEqual(d_pub["upload"], "skipped")

            res_no_up = _run_py(
                "generate_custom_topic_reel.py",
                ["--style", "deep-dive", "--dry-run", "--publish", "--no-upload"],
                env_override={"PROJECTS_DIR": tmp, "FACELESS_HOME": tmp, "AVIDAY_WORKER_URL": "https://worker.example.com"},
            )
            self.assertEqual(res_no_up.returncode, 0, res_no_up.stderr)
            d_no_up = json.loads(res_no_up.stdout)
            self.assertFalse(d_no_up["publish"])
            self.assertEqual(d_no_up["upload"], "skipped")

    def test_youtube_cli_help_exposes_all_contract_flags(self):
        res = _run_py("youtube_shorts_uploader.py", ["--help"])
        self.assertEqual(res.returncode, 0, res.stderr)
        for flag in ("--auth", "--client-secrets", "--video", "--title", "--description", "--style", "--cover"):
            self.assertIn(flag, res.stdout)

    def test_invalid_style_exits_nonzero(self):
        res = _run_py("generate_custom_topic_reel.py", ["--style", "nonexistent-style", "--dry-run"])
        self.assertNotEqual(res.returncode, 0)

    def test_dry_run_zero_keys_exits_zero_and_skips_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = _run_py(
                "generate_custom_topic_reel.py",
                ["--style", "deep-dive", "--topic", "Test topic", "--dry-run", "--no-upload"],
                env_override={"PROJECTS_DIR": tmp, "FACELESS_HOME": tmp},
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            data = json.loads(res.stdout)
            self.assertTrue(data["dry_run"])
            self.assertEqual(data["tts_provider"], "default")
            self.assertEqual(data["upload"], "skipped")
            self.assertEqual(data["script_source"], "template_fallback")
            self.assertEqual(data["projects_dir"], str(Path(tmp)))
            self.assertEqual(data["faceless_home"], str(Path(tmp)))

    def test_script_override_valid_malformed_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            good_script = Path(tmp) / "good.json"
            good_script.write_text(
                json.dumps(
                    {
                        "title": "Custom Test",
                        "lines": [
                            {"text": "First line.", "caps": ["*FIRST", "*LINE"]},
                            {"text": "Second line.", "caps": "*SECOND LINE"},
                        ],
                    }
                )
            )
            res = _run_py(
                "generate_custom_topic_reel.py",
                ["--style", "deep-dive", "--script", str(good_script), "--dry-run"],
                env_override={"PROJECTS_DIR": tmp, "FACELESS_HOME": tmp},
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            data = json.loads(res.stdout)
            self.assertEqual(data["script_source"], "script_file")
            self.assertEqual(data["title"], "Custom Test")

            bad_script = Path(tmp) / "bad.json"
            bad_script.write_text("{not valid json")
            res_bad = _run_py(
                "generate_custom_topic_reel.py",
                ["--style", "deep-dive", "--script", str(bad_script), "--dry-run"],
            )
            self.assertNotEqual(res_bad.returncode, 0)

            res_missing = _run_py(
                "generate_custom_topic_reel.py",
                ["--style", "deep-dive", "--script", str(Path(tmp) / "missing.json"), "--dry-run"],
            )
            self.assertNotEqual(res_missing.returncode, 0)

    def test_caps_list_normalization_and_stale_data_cleanup(self):
        sys.path.insert(0, str(REPO_ROOT))
        try:
            import generate_custom_topic_reel as gctr
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "proj"
            (p / "data").mkdir(parents=True)
            for fname in ("lines.json", "words.json", "cues.json", "narration.wav", "mix.wav"):
                (p / "data" / fname).write_text("stale")
            gctr.clear_stale_project_data(p)
            for fname in ("lines.json", "words.json", "cues.json", "narration.wav", "mix.wav"):
                self.assertFalse((p / "data" / fname).exists())

            normed = gctr.normalize_script_lines([{"text": "Hello world", "caps": ["*HELLO", "*WORLD"]}])
            self.assertEqual(normed[0]["caps"], "*HELLO | *WORLD")

    def test_youtube_uploader_missing_secret_and_creds_path_safety(self):
        sys.path.insert(0, str(REPO_ROOT))
        try:
            import youtube_shorts_uploader as ysu
        finally:
            sys.path.pop(0)

        # Partial env vars (missing YOUTUBE_CLIENT_SECRET) must NOT raise KeyError
        with mock.patch.dict(
            os.environ,
            {"YOUTUBE_CLIENT_ID": "cid-only", "YOUTUBE_REFRESH_TOKEN": "ref-only"},
            clear=True,
        ):
            res = ysu.upload_youtube_short("nonexistent.mp4")
            self.assertFalse(res["ok"])
            self.assertTrue(res["skipped"])

        with tempfile.TemporaryDirectory() as tmp:
            creds_file = Path(tmp) / "missing_creds.json"
            with mock.patch.dict(os.environ, {}, clear=True):
                res2 = ysu.upload_youtube_short("a.mp4", creds_path=creds_file)
                self.assertFalse(res2["ok"])
                self.assertTrue(res2["skipped"])

    def test_publish_social_uploads_no_upload_and_missing_keys_make_zero_network_calls(self):
        sys.path.insert(0, str(REPO_ROOT))
        try:
            import synth_and_render as sr
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            mp4 = Path(tmp) / "video.mp4"
            mp4.write_bytes(b"fake-mp4")
            spec = {"style": "deep-dive", "title": "Test", "caption": "Cap"}
            with mock.patch("urllib.request.urlopen", side_effect=AssertionError("Network call must not happen")):
                res1 = sr.publish_social_uploads(mp4, spec, no_upload=True)
                self.assertTrue(res1["youtube"]["skipped"])
                self.assertTrue(res1["instagram"]["skipped"])

                with mock.patch.dict(os.environ, {}, clear=True):
                    res2 = sr.publish_social_uploads(mp4, spec, no_upload=False)
                    self.assertTrue(res2["youtube"]["skipped"])
                    self.assertTrue(res2["instagram"]["skipped"])


if __name__ == "__main__":
    unittest.main()
