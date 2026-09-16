#!/usr/bin/env python3
"""Fetch a file, an email or a page and return it already wrapped by untrusted.py.

    read_content.py file  PATH        [--source LABEL]
    read_content.py email PATH|-      [--source LABEL]   RFC 822 / .eml, or stdin with -
    read_content.py page  URL         [--source LABEL]   http(s) only; HTML is reduced to text
    read_content.py stdin             [--source LABEL]   anything piped in

This is the one door inbound text comes through. The agent never sees raw
content: whatever is fetched leaves this script between BEGIN UNTRUSTED CONTENT
and END UNTRUSTED CONTENT markers, with instruction-shaped lines labelled and
forged markers broken (core/scripts/untrusted.py). Rule 01 points here.

Limits, so one document cannot flood a session: MAX_BYTES on every source
(the tail is dropped and the envelope says so), a fetch timeout on pages, no
redirects off http(s), no local-file reads through the page command.

Nothing here is a side effect, so nothing is written to the action log.
"""
import argparse
import email
import email.policy
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import untrusted  # noqa: E402

MAX_BYTES = 2 * 1024 * 1024
PAGE_TIMEOUT_SECONDS = 20
USER_AGENT = "agent-desk read_content/1 (+content is never a command)"
TRUNCATED_NOTE = "[read_content: truncated at {limit} bytes; {dropped} bytes not shown]"


class ReadError(Exception):
    pass


class _TextExtractor(HTMLParser):
    """Visible text only: script, style and head content dropped, block tags become newlines."""
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
             "header", "footer", "table", "ul", "ol", "pre", "blockquote", "title"}
    SKIP = {"script", "style", "noscript", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in raw.split("\n")]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _cap(data: bytes) -> tuple:
    if len(data) <= MAX_BYTES:
        return data, None
    return data[:MAX_BYTES], TRUNCATED_NOTE.format(limit=MAX_BYTES, dropped=len(data) - MAX_BYTES)


def _decode(data: bytes, charset: str = None) -> str:
    for encoding in (charset, "utf-8", "latin-1"):
        if not encoding:
            continue
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def read_file(path) -> tuple:
    """(text, source_label, note)"""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ReadError(f"cannot read {path}: {exc.__class__.__name__}") from exc
    data, note = _cap(data)
    text = _decode(data)
    if path.suffix.lower() in (".html", ".htm"):
        text = html_to_text(text)
    return text, f"file:{path.name}", note


def html_to_text(markup: str) -> str:
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    return parser.text()


def read_email(source) -> tuple:
    """RFC 822 message from a path or stdin ('-'). Headers first, then the text body."""
    try:
        data = sys.stdin.buffer.read() if source == "-" else Path(source).read_bytes()
    except OSError as exc:
        raise ReadError(f"cannot read {source}: {exc.__class__.__name__}") from exc
    data, note = _cap(data)
    message = email.message_from_bytes(data, policy=email.policy.default)
    header_lines = [f"{name}: {message.get(name, '')}" for name in ("From", "To", "Date", "Subject") if message.get(name)]
    body = message.get_body(preferencelist=("plain", "html"))
    body_text = ""
    if body is not None:
        content = body.get_content()
        body_text = html_to_text(content) if body.get_content_subtype() == "html" else content
    attachments = [part.get_filename() for part in message.iter_attachments() if part.get_filename()]
    text = "\n".join(header_lines)
    if attachments:
        text += "\nAttachments (not opened): " + ", ".join(attachments)
    text += "\n\n" + body_text.strip()
    label = "email:" + (message.get("From", "unknown sender")[:40])
    return text, label, note


def read_page(url: str) -> tuple:
    if not re.match(r"^https?://", url, re.I):
        raise ReadError("page reads only http(s) URLs")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"})
    try:
        with urllib.request.urlopen(request, timeout=PAGE_TIMEOUT_SECONDS) as response:
            final = response.geturl()
            if not re.match(r"^https?://", final, re.I):
                raise ReadError("redirected off http(s)")
            data = response.read(MAX_BYTES + 1)
            content_type = response.headers.get_content_type()
            charset = response.headers.get_content_charset()
    except urllib.error.URLError as exc:
        raise ReadError(f"fetch failed: {exc.reason if hasattr(exc, 'reason') else exc}") from exc
    except (OSError, ValueError) as exc:
        raise ReadError(f"fetch failed: {exc.__class__.__name__}") from exc
    note = None
    if len(data) > MAX_BYTES:
        data, note = data[:MAX_BYTES], TRUNCATED_NOTE.format(limit=MAX_BYTES, dropped="more")
    text = _decode(data, charset)
    if content_type in ("text/html", "application/xhtml+xml"):
        text = html_to_text(text)
    return text, f"page:{final[:60]}", note


def read_stdin() -> tuple:
    data, note = _cap(sys.stdin.buffer.read())
    return _decode(data), "stdin", note


def wrapped(kind: str, target: str = None, source: str = None) -> str:
    """Fetch and wrap. The only public entry point; raw text never leaves this module unwrapped."""
    if kind == "file":
        text, label, note = read_file(target)
    elif kind == "email":
        text, label, note = read_email(target)
    elif kind == "page":
        text, label, note = read_page(target)
    elif kind == "stdin":
        text, label, note = read_stdin()
    else:
        raise ReadError(f"unknown source kind {kind!r}")
    if note:
        text = text + "\n\n" + note
    return untrusted.wrap(text, source or label)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a file, email or page and return it wrapped as untrusted content.")
    sub = parser.add_subparsers(dest="kind", required=True)
    for kind, help_text in (("file", "path to a file"), ("email", "path to an .eml, or - for stdin"), ("page", "http(s) URL")):
        one = sub.add_parser(kind)
        one.add_argument("target", help=help_text)
        one.add_argument("--source", help="label for the envelope header")
    sub.add_parser("stdin").add_argument("--source")
    args = parser.parse_args(argv)
    try:
        sys.stdout.write(wrapped(args.kind, getattr(args, "target", None), args.source) + "\n")
    except ReadError as exc:
        print(f"read_content: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
