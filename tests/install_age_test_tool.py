"""CI-only dependency installer: fixed official age 1.3.2 archives with SHA-256 verification."""
import argparse
import hashlib
import io
import platform
import tarfile
import urllib.request
from pathlib import Path

DIGESTS = {
    "darwin-arm64":"e2020b073c44f692685a24d6abc378817eb81ffaaf49fd0531ef8565f767f2f5",
    "darwin-amd64":"1d1e4bc66e1427edad7739ae7616157de0e79db8b6d2a1497d7d9925fb06a539",
    "linux-amd64":"cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10",
    "linux-arm64":"6b8dc4333c53a5a57c9e5834e3a48f92605d7154014cd07269ff3327db5d37f4",
}

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    args=parser.parse_args()
    machine={"x86_64":"amd64","aarch64":"arm64"}.get(platform.machine(),platform.machine())
    target=platform.system().lower()+"-"+machine
    expected=DIGESTS[target]
    url=f"https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-{target}.tar.gz"
    with urllib.request.urlopen(url,timeout=45) as response: data=response.read(30_000_001)
    if hashlib.sha256(data).hexdigest()!=expected: raise SystemExit("age archive checksum mismatch")
    args.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as archive:
        for name in ("age","age-keygen"):
            entry=archive.getmember("age/"+name)
            if not entry.isfile(): raise SystemExit("Unexpected age archive entry")
            destination=args.directory/name
            if destination.is_symlink(): raise SystemExit("Refusing a linked tool path")
            destination.write_bytes(archive.extractfile(entry).read())
            destination.chmod(0o700)
    print("Verified age 1.3.2 test tools installed")
