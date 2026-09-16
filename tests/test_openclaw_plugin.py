"""Outbound OpenClaw log gate: real Node hooks and Python log, synthetic events."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from managed import action_log  # noqa: E402

PLUGIN = ROOT / "runtimes/openclaw/plugins/action-log"
NODE = shutil.which("node")

DRIVER = r"""
import { createActionLogHooks, CANCEL_REASON } from FILE_URL;
const spec = JSON.parse(process.argv[1]);
const log = { warnings: [], warn(m) { this.warnings.push(String(m)); } };
const hooks = createActionLogHooks({ pluginConfig: spec.pluginConfig ?? {}, env: process.env, log });
const out = [];
for (const step of spec.steps) {
  if (step.kind === "sending") out.push({ kind: "sending", result: hooks.messageSending(step.event, step.ctx) ?? null });
  else out.push({ kind: "sent", result: hooks.messageSent(step.event, step.ctx) ?? null });
}
console.log(JSON.stringify({ out, warnings: log.warnings, cancelReason: CANCEL_REASON, config: hooks.config, pending: hooks.pending.size }));
"""


@unittest.skipIf(NODE is None, "node is required to test the OpenClaw runtime pieces")
class ActionLogPluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = Path(self.temp.name) / "state" / "security" / "action-log.jsonl"
        self.base_env = {k: v for k, v in os.environ.items()
                         if k not in ("ACTION_LOG", "ACTION_LOG_SCRIPT", "OPENCLAW_STATE_DIR", "HERMES_HOME")}

    def drive(self, steps, env=None, plugin_config=None):
        script = DRIVER.replace("FILE_URL", json.dumps((PLUGIN / "hooks.js").as_uri()))
        run = subprocess.run([NODE, "--input-type=module", "-e", script, json.dumps({"steps": steps, "pluginConfig": plugin_config})],
                             capture_output=True, text=True, env={**self.base_env, **(env or {})}, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout.strip().splitlines()[-1])

    def lines(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def sending(self, to="15555550100", content="SENSITIVE hello", channel="whatsapp"):
        return {"kind": "sending", "event": {"to": to, "content": content}, "ctx": {"channelId": channel}}

    def sent(self, success=True, to="15555550100", content="SENSITIVE hello", channel="whatsapp"):
        return {"kind": "sent", "event": {"to": to, "content": content, "success": success}, "ctx": {"channelId": channel}}

    def configured_env(self):
        return {"ACTION_LOG_SCRIPT": str(ROOT / "managed/action_log.py"),
                "OPENCLAW_STATE_DIR": str(Path(self.temp.name) / "state")}

    def test_configured_plugin_logs_before_send_and_outcome_after(self):
        result = self.drive([self.sending(), self.sent()], env=self.configured_env())
        self.assertEqual([step["result"] for step in result["out"]], [None, None], result["warnings"])
        records = self.lines()
        self.assertEqual([r["type"] for r in records], ["action", "outcome"])
        self.assertEqual(records[0]["action"], "whatsapp.send")
        self.assertEqual(records[0]["target"], "15555550100")
        self.assertEqual(records[0]["sha256"], action_log.sha256_hex("SENSITIVE hello".encode()))
        self.assertEqual(records[0]["consent"], "openclaw:message_sending")
        self.assertEqual(records[1]["status"], "sent")
        self.assertNotIn("SENSITIVE", self.log.read_text())
        self.assertTrue(action_log.verify(self.log)["ok"])
        self.assertEqual(result["pending"], 0)

    def test_failed_delivery_records_failed(self):
        self.drive([self.sending(), self.sent(success=False)], env=self.configured_env())
        self.assertEqual(self.lines()[1]["status"], "failed")

    def test_unwritable_log_cancels_the_send(self):
        blocker = Path(self.temp.name) / "blocker"
        blocker.write_text("")
        env = {**self.configured_env(), "ACTION_LOG": str(blocker / "log.jsonl")}
        result = self.drive([self.sending(), self.sent()], env=env)
        decision = result["out"][0]["result"]
        self.assertTrue(decision["cancel"])
        self.assertEqual(decision["cancelReason"], "action_log_unwritable")
        self.assertFalse(self.log.exists())
        self.assertEqual(result["out"][1]["result"], None)

    def test_unconfigured_plugin_cancels_every_send(self):
        for env in ({}, {"OPENCLAW_STATE_DIR": str(Path(self.temp.name) / "state")}):
            with self.subTest(env=env):
                result = self.drive([self.sending()], env=env)
                decision = result["out"][0]["result"]
                self.assertTrue(decision["cancel"], result)
                self.assertEqual(decision["cancelReason"], "action_log_unwritable")
        self.assertFalse(self.log.exists())

    def test_plugin_config_overrides_env_and_log_path_can_be_explicit(self):
        explicit = Path(self.temp.name) / "explicit.jsonl"
        result = self.drive([self.sending()], env={"OPENCLAW_STATE_DIR": str(Path(self.temp.name) / "state")},
                            plugin_config={"script": str(ROOT / "managed/action_log.py"),
                                           "logPath": str(explicit), "consent": "owner:test"})
        self.assertEqual(result["out"][0]["result"], None, result["warnings"])
        self.assertTrue(explicit.exists())
        self.assertFalse(self.log.exists())
        self.assertEqual(json.loads(explicit.read_text().splitlines()[0])["consent"], "owner:test")

    def test_outcome_for_unknown_message_is_ignored_and_rewritten_content_still_matches(self):
        steps = [self.sent(), self.sending(content="original"), self.sent(content="rewritten by a later hook")]
        result = self.drive(steps, env=self.configured_env())
        self.assertEqual([step["result"] for step in result["out"]], [None, None, None])
        records = self.lines()
        self.assertEqual([r["type"] for r in records], ["action", "outcome"])
        self.assertEqual(records[0]["sha256"], action_log.sha256_hex(b"original"))

    def test_target_is_sanitised_never_dropped(self):
        result = self.drive([self.sending(to="123\nfake line", content="x")], env=self.configured_env())
        self.assertEqual(result["out"][0]["result"], None, result["warnings"])
        self.assertEqual(self.lines()[0]["target"], "123 fake line")

    def test_plugin_files_are_well_formed(self):
        manifest = json.loads((PLUGIN / "openclaw.plugin.json").read_text())
        self.assertEqual(manifest["id"], "action-log")
        self.assertFalse(manifest["configSchema"]["additionalProperties"])
        package = json.loads((PLUGIN / "package.json").read_text())
        self.assertEqual(package["openclaw"]["extensions"], ["./index.js"])
        entry = (PLUGIN / "index.js").read_text()
        self.assertIn('from "openclaw/plugin-sdk/plugin-entry"', entry)
        self.assertIn('api.on("message_sending"', entry)
        self.assertIn('api.on("message_sent"', entry)
        for text in ((PLUGIN / "hooks.js").read_text(), entry):
            self.assertNotIn(".openclaw", text)
            self.assertNotIn("homedir", text)



if __name__ == "__main__":
    unittest.main()
