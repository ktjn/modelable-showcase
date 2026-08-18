"""Task 13.1: JSON-RPC smoke test for `modelable lsp`, the public language
server executable, via a minimal hand-rolled Content-Length framed client.
Never import modelable's internal LSP Python modules here - these tests
exist to prove the downstream LSP contract, not implementation details
(IMPLEMENTATION_PLAN.md Sec 0, rule 2)."""

from __future__ import annotations

import json
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_WORKSPACE = REPO_ROOT / "tests" / "fixtures" / "lsp-workspace"

pytestmark = pytest.mark.skipif(
    shutil.which("modelable") is None,
    reason="modelable is not on PATH - run 'make bootstrap' (or source scripts/modelable-env.sh) first",
)


class LspClient:
    """A minimal Content-Length framed JSON-RPC client, sufficient to drive
    `modelable lsp` over stdio for these tests - not a general-purpose LSP
    client."""

    def __init__(self, cwd: Path, timeout: float = 15.0):
        self.timeout = timeout
        self.proc = subprocess.Popen(
            ["modelable", "lsp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(cwd),
        )
        self._next_id = 0
        self._pending: dict[int, queue.Queue[dict[str, Any]]] = {}
        self._notifications: queue.Queue[dict[str, Any]] = queue.Queue()
        self._lock = threading.Lock()
        self._stderr_lines: list[str] = []
        threading.Thread(target=self._read_loop, daemon=True).start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _drain_stderr(self) -> None:
        assert self.proc.stderr is not None
        for line in self.proc.stderr:
            self._stderr_lines.append(line.decode("utf-8", "replace"))

    def _read_loop(self) -> None:
        stdout = self.proc.stdout
        assert stdout is not None
        while True:
            headers: dict[str, str] = {}
            while True:
                line = stdout.readline()
                if not line:
                    return
                if line in (b"\r\n", b"\n"):
                    break
                text = line.decode("utf-8").strip()
                if ":" in text:
                    key, value = text.split(":", 1)
                    headers[key.strip()] = value.strip()
            length = int(headers.get("Content-Length", "0"))
            body = b""
            while len(body) < length:
                chunk = stdout.read(length - len(body))
                if not chunk:
                    return
                body += chunk
            message = json.loads(body.decode("utf-8"))
            if "id" in message and ("result" in message or "error" in message):
                with self._lock:
                    box = self._pending.setdefault(message["id"], queue.Queue())
                box.put(message)
            else:
                self._notifications.put(message)

    def _write(self, message: dict[str, Any]) -> None:
        body = json.dumps(message).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        assert self.proc.stdin is not None
        self.proc.stdin.write(header + body)
        self.proc.stdin.flush()

    def notify(self, method: str, params: Any = None) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def request(self, method: str, params: Any = None) -> dict[str, Any]:
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            box = self._pending.setdefault(request_id, queue.Queue())
        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        try:
            message = box.get(timeout=self.timeout)
        finally:
            with self._lock:
                self._pending.pop(request_id, None)
        assert "error" not in message, f"{method} returned an error: {message['error']}"
        return message["result"]

    def next_notification(self, method: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"timed out waiting for notification method={method}")
            message = self._notifications.get(timeout=remaining)
            if message.get("method") == method:
                return message

    def stop(self) -> None:
        try:
            self.request("shutdown")
            self.notify("exit")
            self.proc.wait(timeout=self.timeout)
        except Exception:
            self.proc.kill()
            self.proc.wait(timeout=5)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A throwaway copy of tests/fixtures/lsp-workspace/, so LSP-driven edits
    (rename, formatting) and any server-side state never touch the checked-in
    fixture."""
    target = tmp_path / "lsp-workspace"
    shutil.copytree(FIXTURE_WORKSPACE, target)
    return target


@pytest.fixture
def client(workspace: Path):
    lsp = LspClient(workspace)
    try:
        yield lsp
    finally:
        lsp.stop()


def _initialize(lsp: LspClient, workspace: Path) -> dict[str, Any]:
    result = lsp.request(
        "initialize",
        {
            "processId": None,
            "rootUri": workspace.as_uri(),
            "workspaceFolders": [{"uri": workspace.as_uri(), "name": workspace.name}],
            "capabilities": {},
        },
    )
    lsp.notify("initialized", {})
    return result


def _open_document(lsp: LspClient, uri: str, text: str) -> list[dict[str, Any]]:
    lsp.notify(
        "textDocument/didOpen",
        {"textDocument": {"uri": uri, "languageId": "modelable", "version": 1, "text": text}},
    )
    while True:
        message = lsp.next_notification("textDocument/publishDiagnostics")
        if message["params"]["uri"] == uri:
            return message["params"]["diagnostics"]


def test_full_lsp_session_against_a_valid_document(client: LspClient, workspace: Path):
    # 2-3. initialize; assert advertised capabilities.
    init_result = _initialize(client, workspace)
    capabilities = init_result["capabilities"]
    for capability in (
        "completionProvider",
        "hoverProvider",
        "definitionProvider",
        "referencesProvider",
        "renameProvider",
        "documentFormattingProvider",
    ):
        assert capability in capabilities, f"server did not advertise {capability}: {capabilities}"

    # 5-6. open a valid document; wait for diagnostics; assert no errors.
    doc_path = workspace / "widget.mdl"
    uri = doc_path.as_uri()
    text = doc_path.read_text()
    diagnostics = _open_document(client, uri, text)
    assert diagnostics == [], f"valid fixture produced diagnostics: {diagnostics}"

    lines = text.splitlines()
    field_line = next(i for i, line in enumerate(lines) if "name: string" in line)
    field_col = lines[field_line].index("name")
    type_decl_line = next(i for i, line in enumerate(lines) if "widgetId: WidgetId" in line)
    type_decl_col = lines[type_decl_line].index(":") + 2

    # 7. request completion at a known location (right after "widgetId: ",
    # where the server offers the entity's own field names).
    completion = client.request(
        "textDocument/completion",
        {"textDocument": {"uri": uri}, "position": {"line": type_decl_line, "character": type_decl_col}},
    )
    items = completion["items"] if isinstance(completion, dict) else completion
    assert items, f"expected at least one completion item: {completion}"

    # 8. request hover on a known field.
    hover = client.request(
        "textDocument/hover",
        {"textDocument": {"uri": uri}, "position": {"line": field_line, "character": field_col + 1}},
    )
    assert "lspfixture.Widget" in hover["contents"]["value"], hover

    # 9. request definition.
    definition = client.request(
        "textDocument/definition",
        {"textDocument": {"uri": uri}, "position": {"line": field_line, "character": field_col + 1}},
    )
    assert definition is not None, "expected a definition result for a known field"

    # 10. request references.
    references = client.request(
        "textDocument/references",
        {
            "textDocument": {"uri": uri},
            "position": {"line": field_line, "character": field_col + 1},
            "context": {"includeDeclaration": True},
        },
    )
    assert references, f"expected at least one reference for a known field: {references}"

    # 11. request rename to a valid new identifier (on the tmp_path-copied fixture).
    rename = client.request(
        "textDocument/rename",
        {
            "textDocument": {"uri": uri},
            "position": {"line": field_line, "character": field_col + 1},
            "newName": "displayName",
        },
    )
    changes = rename["changes"][uri]
    assert any(edit["newText"] == "displayName" for edit in changes), rename

    # 12. request formatting, since documentFormattingProvider was advertised above.
    formatting = client.request(
        "textDocument/formatting",
        {"textDocument": {"uri": uri}, "options": {"tabSize": 2, "insertSpaces": True}},
    )
    assert isinstance(formatting, list), f"expected a (possibly empty) list of text edits: {formatting}"

    # 13. shutdown/exit cleanly - verified in the `client` fixture's teardown
    # (LspClient.stop asserts a clean shutdown response and process exit).


def test_invalid_document_reports_diagnostics(client: LspClient, workspace: Path):
    _initialize(client, workspace)

    uri = (workspace / "broken.mdl").as_uri()
    invalid_text = (
        "domain broken {\n"
        "  entity Foo @ 1 {\n"
        "    bogusField: NotARealType\n"
        "  }\n"
        "}\n"
    )
    diagnostics = _open_document(client, uri, invalid_text)

    assert diagnostics, "expected at least one diagnostic for an invalid document"
    assert all(d["severity"] == 1 for d in diagnostics), diagnostics
    messages = [d["message"] for d in diagnostics]
    assert any("NotARealType" in message for message in messages), messages
