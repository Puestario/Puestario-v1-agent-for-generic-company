"""Real age encryption with synthetic fixtures. No company backups or keys are used."""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from managed import backup as b, install, control as c
from managed.store import Store, DeskError


@unittest.skipUnless(shutil.which("age") and shutil.which("age-keygen"), "age and age-keygen required for real encrypted backup tests")
class EncryptedBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.root=self.folder/"company"
        self.key=self.folder/"recovery-key.txt"
        subprocess.run(["age-keygen","-o",str(self.key)],check=True,capture_output=True)
        self.recipient=subprocess.run(["age-keygen","-y",str(self.key)],check=True,capture_output=True,text=True).stdout.strip()
        install.initialize(self.root,ROOT,json.loads((ROOT/"managed/company.example.json").read_text()),"fixture",staging=True)
        self.store=Store(self.root)
        with self.store.locked() as s:
            s["notes"]={"+12025550101":{"private":"SYNTHETIC PRIVATE NOTE"}}
            s["jobs"]={"test":{"enabled":True,"creator":"+12025550101","to":"+12025550101","runs":[{"status":"sending"}]}}
        self.archive=self.folder/"snapshot.age"

    def test_pre_cleanup_logger_path_survives_encrypted_restore(self):
        old = self.root / "release/core/scripts/action_log.py"
        old.parent.mkdir(parents=True)
        (self.root / "release/managed/action_log.py").rename(old)
        manifest_path = self.root / "release-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["core/scripts/action_log.py"] = manifest["files"].pop("managed/action_log.py")
        manifest_path.write_text(json.dumps(manifest))
        b.backup(self.store, self.recipient, self.archive, check_stopped=False)
        restored = self.folder / "old-restored"
        b.restore(restored, self.archive, self.key)
        config = json.loads((restored / "gateway/openclaw.json").read_text())
        logger = Path(config["plugins"]["entries"]["action-log"]["config"]["script"])
        self.assertEqual(logger, restored.resolve() / "release/core/scripts/action_log.py")
        self.assertTrue(logger.is_file())
        self.assertTrue(Store(restored).read()["paused"])

    def test_encrypt_restore_complete_and_paused(self):
        b.backup(self.store,self.recipient,self.archive,check_stopped=False)
        self.assertNotIn(b"SYNTHETIC PRIVATE NOTE",self.archive.read_bytes())
        self.assertEqual(list(self.folder.glob("*.tar*")),[])
        restored=self.folder/"restored"
        result=b.restore(restored,self.archive,self.key)
        self.assertTrue(result["paused"])
        state=Store(restored).read()
        self.assertEqual(state["notes"]["+12025550101"]["private"],"SYNTHETIC PRIVATE NOTE")
        self.assertFalse(state["jobs"]["test"]["enabled"])
        self.assertEqual(state["jobs"]["test"]["runs"][0]["status"],"unverified")
        self.assertEqual(state["checks"],{})
        self.assertNotEqual(state["install"]["gateway_token"],self.store.read()["install"]["gateway_token"])
        config=json.loads((restored/"gateway/openclaw.json").read_text())
        self.assertEqual(Path(config["agents"]["defaults"]["workspace"]),(restored/"workspace").resolve())
        self.assertEqual((restored/"release/managed/control.py").read_bytes(),(ROOT/"managed/control.py").read_bytes())

    def test_encrypt_failure_never_publishes_or_prunes(self):
        self.archive.write_bytes(b"previous archive")
        with self.assertRaises(DeskError): b.backup(self.store,self.recipient,self.archive,False)
        self.assertEqual(self.archive.read_bytes(),b"previous archive")
        self.archive.unlink()
        with patch.dict(os.environ,{"PATH":"/does-not-exist"}):
            with self.assertRaises(OSError): b.backup(self.store,self.recipient,self.archive,False)
        self.assertFalse(self.archive.exists())
        self.assertEqual(list(self.folder.glob(".encrypted-*")),[])

    def test_symlink_backup_is_rejected(self):
        (self.root/"workspace/link").symlink_to(self.key)
        with self.assertRaises(DeskError): b.backup(self.store,self.recipient,self.archive,False)
        self.assertFalse(self.archive.exists())

    def test_restore_refuses_existing_target_and_bad_key(self):
        b.backup(self.store,self.recipient,self.archive,False)
        with self.assertRaises(DeskError): b.restore(self.root,self.archive,self.key)
        wrong=self.folder/"wrong-key.txt"
        subprocess.run(["age-keygen","-o",str(wrong)],check=True,capture_output=True)
        with self.assertRaises((DeskError,tarfile.TarError)): b.restore(self.folder/"wrong",self.archive,wrong)
        self.assertFalse((self.folder/"wrong").exists())

    def test_restore_rejects_encrypted_traversal_and_symlink(self):
        for name,linked in (("../outside",False),("workspace/link",True)):
            stream=io.BytesIO()
            with tarfile.open(fileobj=stream,mode="w:gz") as archive:
                item=tarfile.TarInfo(name)
                if linked: item.type,item.linkname=tarfile.SYMTYPE,"/etc/passwd"
                else: item.size=1
                archive.addfile(item,None if linked else io.BytesIO(b"x"))
            encrypted=subprocess.run(["age","-r",self.recipient],input=stream.getvalue(),capture_output=True,check=True).stdout
            self.archive.write_bytes(encrypted)
            with self.assertRaises(DeskError): b.restore(self.folder/"bad",self.archive,self.key)
            self.assertFalse((self.folder/"bad").exists())
            self.assertFalse((self.folder/"outside").exists())


if __name__ == "__main__": unittest.main()
