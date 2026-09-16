"""Synthetic security/operation regressions. No live accounts, phone pairing or sends."""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from managed import control as c, runtime as r, adapters as a, install, backup as b
from managed.store import Store, DeskError, atomic_json

ADMIN_ONE, ADMIN_TWO, ANA, OUTSIDER = "+12025550101", "+12025550102", "+12025550103", "+12025550104"
GROUP = "1234567890@g.us"
NOW = 2_000_000_000


def actor(number=ADMIN_ONE, group=None):
    return {"channel": "whatsapp", "account": "default", "sender": number, "conversation": group or number}


class ManagedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = (Path(self.temp.name) / "company").resolve()
        self.store = Store(self.root)
        config = json.loads((ROOT / "managed/company.example.json").read_text())
        self.state = c.initial(config, NOW)
        self.state["install"] = {"release": str(self.root / "release"), "port": 18791,
                                 "gateway_token": "synthetic-test-token", "source_revision": "fixture", "staging": True}
        self.store.initialize(self.state)
        self.call("setup.open", {"minutes": 30})

    def call(self, op, args=None, sender=ADMIN_ONE, group=None, **kwargs):
        return c.dispatch(self.store, actor(sender, group), op, args, now=NOW, **kwargs)

    def resource(self, name="sales", writable=False):
        self.call("resource.put", {"name": name, "resource": {"kind": "google-sheets", "connection": "google-main",
                  "spreadsheet_id": "synthetic123456", "range": "Sales!A1:B2", "writable": writable}})

    def staff(self, permissions=None, group=True):
        self.call("person.put", {"number": ANA, "name": "Ana", "tester": True, "resources": permissions or {}})
        if group: self.call("group.put", {"id": GROUP, "name": "Staff", "members": [ANA], "resources": permissions or {}})
        with self.store.locked() as state: state["gateway_pending"] = False

    def test_both_founders_can_act_independently(self):
        self.call("setup.open", {"minutes": 15}, ADMIN_TWO)
        self.call("company.update", {"agent_name": "Alex"}, ADMIN_TWO)
        with self.assertRaises(DeskError): self.call("company.update", {"agent_name": "Sparx"})
        self.call("setup.open")
        self.call("company.update", {"agent_name": "Sparx"})
        self.assertEqual(self.store.read()["company"]["agent_name"], "Sparx")

    def test_staff_quoted_founder_and_unknown_fail(self):
        self.staff()
        for sender in (ANA, OUTSIDER):
            with self.assertRaises(DeskError): self.call("setup.open", {"asked_by": ADMIN_ONE}, sender)
        for changed in ({"sender": None}, {"channel": "telegram"}, {"account": "other"}, {"conversation": OUTSIDER}):
            with self.assertRaises(DeskError): c.dispatch(self.store, {**actor(), **changed}, "status", now=NOW)

    def test_staff_unready_timeout_and_pending_gates(self):
        self.staff()
        self.assertFalse(self.call("status", sender=ANA)["ready"])
        with self.assertRaises(DeskError): c.dispatch(self.store, actor(ANA), "status", now=NOW+1900)
        self.assertFalse(self.store.read()["ready"])
        with self.store.locked() as s: s["gateway_pending"] = True
        with self.assertRaises(DeskError): self.call("status", sender=ANA)

    def test_founder_controls_private_only(self):
        self.staff()
        with self.assertRaises(DeskError): self.call("person.remove", {"number": ANA}, group=GROUP)
        self.assertNotIn("people", self.call("status", group=GROUP))

    def test_scoped_data_and_group_privacy(self):
        self.resource("sales")
        self.resource("finance")
        self.staff({"sales": ["read"]})
        with patch.object(a, "read", return_value={"account":"synthetic","rows":[[1]]}) as read:
            self.call("resource.read", {"resource":"sales"}, ANA, GROUP)
            for sender, group in ((ANA, None), (ANA, GROUP), (ADMIN_ONE, GROUP)):
                with self.assertRaises(DeskError): self.call("resource.read", {"resource":"finance"}, sender, group)
            self.assertEqual(read.call_count, 1)

    def test_nonmember_of_approved_group_fails(self):
        self.staff()
        self.call("person.put", {"number": OUTSIDER, "name":"Other", "tester":True})
        with self.store.locked() as s: s["gateway_pending"] = False
        with self.assertRaises(DeskError): self.call("status", sender=OUTSIDER, group=GROUP)

    def test_notes_belong_only_to_their_sender(self):
        self.staff()
        self.call("note.save", {"name":"private-note", "text":"owner-private test"})
        self.assertEqual(self.call("note.list", sender=ANA)["private_notes"], {})
        with self.assertRaises(DeskError): self.call("note.list", group=GROUP)
        self.assertNotIn("owner-private", "".join(r.workspace_files(self.store.read()).values()))

    def test_old_history_blocked_after_permission_change(self):
        self.staff()
        c.session_gate(self.store, actor(ANA), "old", now=NOW)
        self.call("person.put", {"number":ANA,"name":"Ana","tester":True})
        with self.store.locked() as s: s["gateway_pending"] = False
        with self.assertRaisesRegex(DeskError, "/new"): c.session_gate(self.store, actor(ANA), "old", now=NOW)
        with self.assertRaisesRegex(DeskError, "/new"): c.session_gate(self.store, actor(ANA), "unrecorded", True, now=NOW)
        c.session_gate(self.store, actor(ANA), "new", now=NOW)

    def test_remove_revokes_jobs_and_group_membership(self):
        self.staff()
        self.call("job.add", {"text":"Hi", "schedule":{"every_minutes":1}}, ANA)
        self.call("person.remove", {"number":ANA})
        s = self.store.read()
        self.assertNotIn(ANA, s["groups"][GROUP]["members"])
        self.assertTrue(all(not j["enabled"] for j in s["jobs"].values()))
        with self.assertRaises(DeskError): self.call("status", sender=ANA)

    def test_lost_founder_phone_and_last_founder(self):
        self.call("founder.remove", {"number":ADMIN_ONE}, ADMIN_TWO)
        with self.assertRaises(DeskError): self.call("status")
        with self.assertRaises(DeskError): self.call("founder.remove", {"number":ADMIN_TWO}, ADMIN_TWO)
        self.assertTrue(self.store.read()["founders"][ADMIN_TWO]["active"])

    def test_idempotent_change_and_revision_conflict(self):
        first = self.call("person.put", {"number":ANA,"name":"Ana"}, request_id="request-1")
        second = self.call("person.put", {"number":ANA,"name":"Ana"}, request_id="request-1")
        self.assertEqual(first, second)
        with self.assertRaises(DeskError): self.call("person.remove", {"number":ANA}, request_id="request-1")
        with self.assertRaises(DeskError): self.call("desk.pause", expected_revision=1)

    def test_write_crash_cannot_repeat(self):
        self.resource(writable=True)
        with patch.object(a, "sheet_write", side_effect=DeskError("uncertain")) as write:
            with self.assertRaises(DeskError): self.call("resource.write", {"resource":"sales", "rows":[[1,2],[3,4]]}, request_id="write-1")
            result = self.call("resource.write", {"resource":"sales", "rows":[[1,2],[3,4]]}, request_id="write-1")
            self.assertEqual(result["status"], "unverified")
            self.assertEqual(write.call_count, 1)

    def test_not_ready_without_real_acceptance(self):
        with self.assertRaisesRegex(DeskError, "Not Ready"): self.call("setup.close")
        with self.store.locked() as s:
            s["gateway_pending"] = False
            s["checks"] = {name:{"passed":True,"config":c.configuration_digest(s)} for name in c.CHECKS}
        self.call("setup.close")
        self.assertTrue(self.store.read()["ready"])

    def test_startup_closes_temporary_setup(self):
        r.startup(self.store, "new-boot")
        s = self.store.read()
        self.assertIsNone(s["setup"])
        self.assertFalse(s["ready"])

    def test_reminder_sent_once_and_uncertain_never_retried(self):
        self.staff()
        self.call("job.add", {"text":"Reminder", "schedule":{"at":"2033-05-18T03:34:20+00:00"}}, ANA)
        with self.store.locked() as s: s["outbox"] = {}
        sent = []
        def deliver(*args): sent.append(args); return "transport-1"
        r.tick(self.store, NOW+100, deliver)
        r.tick(self.store, NOW+101, deliver)
        self.assertEqual(len(sent), 1)
        self.assertEqual(next(iter(self.store.read()["jobs"].values()))["runs"][0]["status"], "sent")
        self.call("job.add", {"text":"Second", "schedule":{"every_minutes":1}}, ANA)
        def uncertain_for_staff(root, account, target, content):
            if target == ANA: raise DeskError("uncertain")
            return "notice-receipt"
        with patch.object(r, "send", side_effect=uncertain_for_staff) as fail:
            r.tick(self.store, NOW+61, fail)
            r.tick(self.store, NOW+62, fail)
            self.assertEqual(sum(call.args[2] == ANA for call in fail.call_args_list), 1)

    def test_applied_file_waits_for_actual_runtime_acknowledgement(self):
        with patch.object(r, "command", return_value='{"valid":true}'):
            self.assertFalse(r.apply(self.store)["applied"])
            self.assertFalse(r.apply(self.store)["applied"])  # readonly files can be replaced safely
        self.assertTrue(self.store.read()["gateway_pending"])
        self.assertFalse(r.acknowledge(self.store,{})["settings_applied"])
        config = r.managed_config(self.store.read(),self.root.resolve(),self.root.resolve()/"release")
        self.assertTrue(r.acknowledge(self.store,config)["settings_applied"])

    def test_unchanged_founder_can_finish_multi_step_setup(self):
        c.session_gate(self.store,actor(),"owner",now=NOW)
        self.call("person.put",{"number":ANA,"name":"Ana"})
        self.assertTrue(c.session_gate(self.store,actor(),"owner",now=NOW)["allowed"])
        self.call("founder.remove",{"number":ADMIN_ONE},ADMIN_TWO)
        with self.assertRaises(DeskError): c.session_gate(self.store,actor(),"owner",now=NOW)

    def test_staff_cannot_schedule_for_another_person(self):
        self.staff()
        with self.assertRaises(DeskError): self.call("job.add", {"to":ADMIN_ONE,"text":"x","schedule":{"every_minutes":1}}, ANA)

    def test_group_report_cannot_use_private_resource(self):
        self.resource("finance")
        self.staff()
        with self.assertRaises(DeskError): self.call("job.add", {"to":GROUP,"resource":"finance","schedule":{"every_minutes":1}})

    def test_config_keeps_code_out_of_workspace_and_no_shell(self):
        self.staff()
        config = r.managed_config(self.store.read(), self.root, self.root / "release")
        self.assertIn(ANA, config["channels"]["whatsapp"]["groupAllowFrom"])
        self.assertEqual(config["session"]["dmScope"], "per-channel-peer")
        self.assertEqual(config["tools"]["allow"], ["puestario"])
        self.assertEqual(config["agents"]["defaults"]["sandbox"]["workspaceAccess"], "ro")
        self.assertNotIn("release", config["agents"]["defaults"]["workspace"])

    def test_bad_credentials_are_not_a_connected_app(self):
        self.resource()
        with patch.object(a, "read", side_effect=DeskError("HTTP 401")):
            with self.assertRaises(DeskError): self.call("connection.check", {"resource":"sales"})

    def test_apply_failure_keeps_previous_config_and_pending(self):
        atomic_json(self.root / "gateway/openclaw.json", {"old":"safe"})
        with patch.object(r, "command", side_effect=DeskError("invalid")):
            with self.assertRaises(DeskError): r.apply(self.store)
        self.assertEqual(json.loads((self.root / "gateway/openclaw.json").read_text()), {"old":"safe"})
        self.assertTrue(self.store.read()["gateway_pending"])

    def test_adapters_reject_wide_ranges_and_credential_redirects(self):
        with self.assertRaises(DeskError): a.validate_resource({"kind":"stripe","connection":"stripe-main","writable":"false"})
        for span in ("Sales!A5:B1", "Sales!A1:ZZ99999"):
            with self.assertRaises(DeskError): a.validate_resource({"kind":"google-sheets","connection":"google-main","spreadsheet_id":"synthetic123456","range":span})
        with self.assertRaises(DeskError): a.NoRedirect().redirect_request(None,None,None,None,None,"https://attacker.invalid")

    def test_sheet_write_requires_exact_range_and_readback(self):
        resource = {"kind":"google-sheets","connection":"google-main","spreadsheet_id":"synthetic123456","range":"Sales!A1:B1","writable":True}
        with self.assertRaises(DeskError): a.sheet_write(self.root, resource, [[1]])
        with patch.object(a,"load_secret",return_value={}), patch.object(a,"google_token",return_value="fake"), patch.object(a,"request",side_effect=[{}, {"values":[[1,2]]}]):
            self.assertEqual(a.sheet_write(self.root, resource, [[1,2]])["status"], "succeeded")
        with patch.object(a,"load_secret",return_value={}), patch.object(a,"google_token",return_value="fake"), patch.object(a,"request",side_effect=[{}, {"values":[[0,2]]}]):
            with self.assertRaisesRegex(DeskError,"uncertain"): a.sheet_write(self.root, resource, [[1,2]])


class InstallAndBackupTests(unittest.TestCase):
    def test_release_inventory_excludes_ignored_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)
            subprocess.run(["git","init",str(source)],capture_output=True,check=True)
            (source/"managed").mkdir()
            (source/"managed/known.py").write_text("# reviewed\n")
            (source/"managed/.env").write_text("SYNTHETIC_SECRET=do-not-copy\n")
            (source/".gitignore").write_text(".env\n")
            subprocess.run(["git","add","managed/known.py",".gitignore"],cwd=source,check=True)
            self.assertEqual(list(install.source_files(source)),[Path("managed/known.py")])

    def test_staging_install_is_idempotently_refused_not_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/"company"
            config = json.loads((ROOT / "managed/company.example.json").read_text())
            result = install.initialize(root, ROOT, config, "fixture", staging=True)
            self.assertFalse(result["ready"])
            config_on_disk = json.loads((root/"gateway/openclaw.json").read_text())
            logger = Path(config_on_disk["plugins"]["entries"]["action-log"]["config"]["script"])
            self.assertEqual(logger, root.resolve()/"release/managed/action_log.py")
            self.assertTrue(logger.is_file())
            self.assertEqual(logger.read_bytes(), (ROOT/"managed/action_log.py").read_bytes())
            before = (root/"control.json").read_bytes()
            with self.assertRaises(DeskError): install.initialize(root, ROOT, config, "fixture", staging=True)
            self.assertEqual(before, (root/"control.json").read_bytes())
            self.assertNotIn("core", [p.name for p in (root/"workspace").iterdir()])

    def test_backup_traversal_and_links_are_not_valid_names(self):
        for name in ("../escape", "/etc/passwd", "gateway/../../escape", "secrets\\escape", "unexpected/file"):
            with self.assertRaises(DeskError): b.safe_name(name)

    def test_retention_only_matches_our_company_and_preserves_newest(self):
        def row(id, name, company="example", marker="age-v1"):
            return {"id":id,"name":name,"createdTime":"2020-01-01T00:00:00Z","appProperties":{"puestarioCompany":company,"puestarioBackup":marker}}
        files = [row("1","puestario-example-first.age"),row("2","puestario-example-last.age"),
                 row("3","important.docx"),row("4","puestario-other-old.age","other"),row("5","puestario-example-wrong.age",marker="other")]
        self.assertEqual(b.retention_candidates(files,"example",14, NOW), ["1"])
        with self.assertRaises(DeskError): b.retention_candidates(files,"example",0)


if __name__ == "__main__": unittest.main()
