import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from managed.drive_backup import list_backups, upload
from managed.store import DeskError


class DriveBackupTests(unittest.TestCase):
    def test_all_pages_are_read_before_retention(self):
        service=MagicMock()
        service.files.return_value.list.return_value.execute.side_effect=[
            {"files":[{"id":"first"}],"nextPageToken":"page2"},{"files":[{"id":"second"}]}]
        self.assertEqual(list_backups(service,"explicit-folder-id"),[{"id":"first"},{"id":"second"}])
        args=service.files.return_value.list.call_args_list
        self.assertEqual(args[1].kwargs["pageToken"],"page2")
        self.assertIn("'explicit-folder-id' in parents",args[0].kwargs["q"])

    def test_bad_upload_checksum_never_prunes(self):
        fake=types.ModuleType("googleapiclient.http")
        fake.MediaFileUpload=lambda *args,**kwargs: object()
        service=MagicMock()
        service.files.return_value.get.return_value.execute.return_value={"mimeType":"application/vnd.google-apps.folder","capabilities":{"canAddChildren":True}}
        service.files.return_value.create.return_value.execute.return_value={"id":"new","size":"30","md5Checksum":"wrong"}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules,{"googleapiclient.http":fake}):
            archive=Path(tmp)/"fixture.age"
            archive.write_bytes(b"age-encryption.org/v1\nsynthetic ciphertext")
            with self.assertRaises(DeskError): upload(service,archive,"example-company","explicit-folder-id",prune=True)
        service.files.return_value.update.assert_not_called()
        service.files.return_value.list.assert_not_called()


if __name__=="__main__": unittest.main()
