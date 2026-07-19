from __future__ import annotations

import json
import os
import stat
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class CommandCenterNotPaired(RuntimeError):
    """The client has no usable browser-issued workspace token."""


class CommandCenterClient:
    def __init__(self) -> None:
        self.base = os.getenv("COMMAND_CENTER_URL", "http://127.0.0.1:8000").rstrip("/")
        self.pair_code = os.getenv("COMMAND_CENTER_PAIR_CODE")
        state = Path(os.getenv(
            "COMMAND_CENTER_STATE_DIR",
            str(Path.home() / ".command-center"),
        )).expanduser()
        self.token_path = state / "codex-workspace-token"
        self.token = self._read_token()

    def _read_token(self) -> str | None:
        try:
            value = self.token_path.read_text(encoding="utf-8").strip()
            return value or None
        except OSError:
            return None

    def _refresh_token(self) -> bool:
        value = self._read_token()
        changed = value != self.token
        self.token = value
        return changed

    def _save_token(self, value: str) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(value, encoding="utf-8")
        self.token_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        self.token = value

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None,
    ) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Command-Center-Token"] = self.token
        request = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method,
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())

    def login(self) -> None:
        if not self.pair_code:
            raise CommandCenterNotPaired(
                "Command Center is not paired; use Pair Codex in the browser "
                "and run the pairing helper in a terminal."
            )
        request = urllib.request.Request(
            self.base + "/api/v1/auth/pair",
            data=json.dumps({"code": self.pair_code}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
            token = result.get("workspace_token")
            if not token:
                raise RuntimeError("Command Center did not issue a workspace token")
            self._save_token(str(token))

    def request(
        self, method: str, path: str, body: dict[str, Any] | None = None,
    ) -> Any:
        self._refresh_token()
        if not self.token:
            if self.pair_code:
                self.login()
            else:
                raise CommandCenterNotPaired(
                    "Command Center is not paired; use Pair Codex in the "
                    "browser and run the pairing helper in a terminal."
                )
        try:
            return self._request(method, path, body)
        except urllib.error.HTTPError as error:
            if error.code == 401:
                previous = self.token
                self._refresh_token()
                if self.token and self.token != previous:
                    return self._request(method, path, body)
                raise CommandCenterNotPaired(
                    "The stored Command Center token is invalid or revoked; "
                    "pair this Codex session again."
                ) from error
            detail = error.read().decode(errors="replace")
            raise RuntimeError(f"Command Center HTTP {error.code}: {detail}") from error

    def context_pack(
        self, prompt: str, repository: str | None = None, token_budget: int = 2000,
    ) -> Any:
        """Compatibility wrapper for the isolated v2 task-pack contract."""
        return self.task_pack(prompt, repository, token_budget)

    def mcp_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        response = self.request("POST", "/mcp", {
            "jsonrpc": "2.0",
            "id": "codex-plugin",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        if response.get("error"):
            raise RuntimeError(
                response["error"].get("message", "Command Center MCP tool failed")
            )
        result = response.get("result") or {}
        if "structuredContent" in result:
            return result["structuredContent"]
        content = result.get("content") or []
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        raise RuntimeError("Command Center MCP returned no tool result")

    def task_pack(
        self, prompt: str, repository: str | None = None, token_budget: int = 2000,
    ) -> Any:
        return self.mcp_tool("build_task_pack", {
            "prompt": prompt,
            "repository": repository,
            "token_budget": token_budget,
        })

    def architecture_brief(
        self,
        repository: str,
        *,
        mode: str = "boot",
        prompt: str = "",
        token_budget: int = 1_200,
    ) -> Any:
        return self.request("POST", "/api/v1/architecture/brief", {
            "repository": repository,
            "mode": mode,
            "prompt": prompt,
            "token_budget": token_budget,
        })

    def evidence(self, source_id: str) -> Any:
        return self.mcp_tool("get_evidence", {"source_id": source_id})

    def timeline(self, project: str | None, limit: int) -> Any:
        query = urllib.parse.urlencode({
            key: value for key, value in {"project": project, "limit": limit}.items()
            if value is not None
        })
        return self.request("GET", "/api/v1/timeline?" + query)
