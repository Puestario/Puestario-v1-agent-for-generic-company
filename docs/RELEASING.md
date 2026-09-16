# Release checklist

Use a `-pilot` prerelease until the real acceptance evidence exists. A tag identifies code; it does not certify a live installation.

1. Review changes against the documented product limits. No live company data may be in the diff.
2. Check version pins and compatibility. The runtime remains OpenClaw 2026.5.27 until a newer version is separately qualified.
3. Run all tests with Node and age 1.3.2 installed. Run `python3 tests/ci_checks.py all` and `python3 tests/public_scan.py --history`.
4. Check a clean checkout: the installer must create every referenced plugin, protected file and all seven workspace files. Example company information must be refused for a normal install.
5. Complete the isolated runtime validation where available. Record missing Docker, phone or app tests honestly.
6. Merge the reviewed branch after CI passes. Create an annotated `v0.2.0-pilot` tag at that exact commit and publish a GitHub prerelease with the changelog, versions, test results and unverified items.
7. Update the Puestario website guide from this exact public commit. Verify hashes, generated examples, file explanations and EN/ES links. Keep its revision visible.
8. Only a real [acceptance run](ACCEPTANCE.md) can qualify a specific company for handover. Record private evidence outside GitHub.

For later releases, use a new version and tag; never move a published tag to different code. The installer requires a clean Git checkout, so use `git clone` and a reviewed tag/commit rather than a downloaded ZIP for installation.
