from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STYLES_ALL = ("deep-dive", "inside-out", "night-file", "paper-atlas", "stick-story", "tall-tale")


class TestRenderingAndConfigs(unittest.TestCase):
    def test_all_root_python_files_parse_cleanly(self):
        py_files = sorted(REPO_ROOT.glob("*.py")) + sorted((REPO_ROOT / "tests").glob("*.py"))
        self.assertGreater(len(py_files), 5)
        for p in py_files:
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))

    def test_all_js_mjs_and_capture_scripts_pass_node_check(self):
        js_files = [
            REPO_ROOT / "cloudflare-worker-24-7.js",
            REPO_ROOT / "src" / "index.js",
            REPO_ROOT / "render_viral_thumbnail.mjs",
            REPO_ROOT / "setup-server.mjs",
            REPO_ROOT / "sync_ig_session.mjs",
            REPO_ROOT / "make-permanent-token.mjs",
        ]
        for style in STYLES_ALL:
            cap = REPO_ROOT / "faceless-shorts-skill" / "faceless-shorts" / "styles" / style / "example" / "tools" / "capture.mjs"
            js_files.append(cap)
            content = cap.read_text(encoding="utf-8")
            for required_flag in (
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--use-angle=swiftshader",
            ):
                self.assertIn(required_flag, content, f"{cap} missing {required_flag}")
            self.assertIn("SIGINT", content, f"{cap} missing SIGINT cleanup")
            self.assertIn("SIGTERM", content, f"{cap} missing SIGTERM cleanup")
            self.assertIn("&res=0.6&aa=0&shadow=1024", content, f"{cap} missing SOFTWARE_GL QS default")

        for f in js_files:
            res = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0, f"node --check failed for {f}: {res.stderr}")

    def test_invalid_chrome_env_override_fails_fast(self):
        env = os.environ.copy()
        env["CHROME"] = "/nonexistent/chrome_bin"
        with tempfile.TemporaryDirectory() as tmp:
            res_thumb = subprocess.run(
                ["node", str(REPO_ROOT / "render_viral_thumbnail.mjs"), tmp, "2.0"],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(res_thumb.returncode, 0)
            self.assertIn("Chrome", res_thumb.stderr)

        for style in STYLES_ALL:
            ex = REPO_ROOT / "faceless-shorts-skill" / "faceless-shorts" / "styles" / style / "example"
            res_cap = subprocess.run(
                ["node", "tools/capture.mjs", "check"],
                cwd=str(ex),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(res_cap.returncode, 0, f"{style} capture.mjs silently fell back to system Chrome")
            self.assertIn("Chrome", res_cap.stderr)

    def test_render_viral_thumbnail_missing_args_exits_nonzero(self):
        res = subprocess.run(
            ["node", str(REPO_ROOT / "render_viral_thumbnail.mjs")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(res.returncode, 0)

    def test_timing_js_safe_for_short_scripts(self):
        for style in STYLES_ALL:
            tjs = (
                REPO_ROOT
                / "faceless-shorts-skill"
                / "faceless-shorts"
                / "styles"
                / style
                / "example"
                / "src"
                / "core"
                / "timing.js"
            )
            txt = tjs.read_text(encoding="utf-8")
            self.assertNotIn("throw new Error(`no line", txt, f"{tjs} still throws on short scripts")

    def test_workflow_yml_contract(self):
        wf = (REPO_ROOT / ".github" / "workflows" / "faceless-reels.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", wf)
        for key in ("style:", "topic:", "tts_provider:", "voice:", "caption:", "publish:"):
            self.assertIn(key, wf)
        self.assertIn("default: false", wf)
        self.assertIn("runs-on: ubuntu-latest", wf)
        self.assertIn("SOFTWARE_GL: '1'", wf)
        self.assertIn("PROJECTS_DIR:", wf)
        self.assertIn("google-chrome-stable", wf)
        self.assertIn("fonts-noto-color-emoji", wf)
        self.assertIn("actions/upload-artifact@v4", wf)
        self.assertIn("--no-upload", wf)
        # Schedule must remain commented out
        for line in wf.splitlines():
            stripped = line.strip()
            self.assertFalse(stripped.startswith("schedule:"), "Uncommented schedule trigger found")

    def test_env_examples_requirements_and_package_json(self):
        env_ex = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        for key in (
            "GEMINI_API_KEY",
            "TTS_PROVIDER",
            "TTS_VOICE",
            "ELEVENLABS_API_KEY",
            "FACELESS_HOME",
            "PROJECTS_DIR",
            "META_PAGE_ACCESS_TOKEN",
            "YOUTUBE_CLIENT_ID",
        ):
            self.assertIn(f"{key}=", env_ex)

        dev_vars = (REPO_ROOT / ".dev.vars.example").read_text(encoding="utf-8")
        worker_js = (REPO_ROOT / "cloudflare-worker-24-7.js").read_text(encoding="utf-8")
        for key in ("FB_PAGE_ID", "GROQ_API_KEY", "META_PAGE_ACCESS_TOKEN", "GEMINI_API_KEY"):
            self.assertIn(f"{key}=", dev_vars)
            self.assertIn(key, worker_js)

        reqs = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("numpy", reqs)
        self.assertIn("scipy", reqs)
        self.assertIn("edge-tts", reqs)

        pkg = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["name"], "project-aviday")
        self.assertNotIn("test-simulator.mjs", json.dumps(pkg))


if __name__ == "__main__":
    unittest.main()
