"""Secure transport helper for GitHub Actions -> shared controller.

Prefers a reviewed HTTPS controller URL. If no URL is configured, it creates an
SSH tunnel to the persistent orchestrator host and talks to localhost. Secrets
are never printed and redirects are never followed.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

import httpx


def _runtime_secret(name: str) -> str:
    direct = os.getenv(name, "").strip()
    if direct:
        return direct
    bundle = os.getenv("ORCH_ENV_B64", "").strip()
    if not bundle:
        return ""
    try:
        text = base64.b64decode(bundle, validate=True).decode()
    except Exception as exc:
        raise ValueError("invalid protected runtime bundle") from exc
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values.get(name, "")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class SharedTransport:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.tempdir: tempfile.TemporaryDirectory | None = None
        self.base_url = ""
        self.token = ""

    def __enter__(self):
        direct_url = os.getenv("CONTROL_SERVICE_URL", "").strip()
        direct_token = os.getenv("CONTROL_SERVICE_TOKEN", "").strip()
        if direct_url:
            parsed = urlsplit(direct_url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or not direct_token
            ):
                raise ValueError("invalid direct controller configuration")
            self.base_url = direct_url.rstrip("/")
            self.token = direct_token
            return self

        host = os.getenv("ORCH_SERVER_HOST", "").strip()
        user = os.getenv("ORCH_SERVER_USER", "").strip()
        port = os.getenv("ORCH_SERVER_PORT", "").strip() or "22"
        key = os.getenv("ORCH_SERVER_SSH_KEY", "")
        known_hosts = os.getenv("ORCH_SERVER_KNOWN_HOSTS", "")
        token = _runtime_secret("ORCHESTRATOR_TOKEN")
        if not all((host, user, key.strip(), known_hosts.strip(), token)):
            raise ValueError("shared controller transport is not configured")

        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        key_path = root / "id_ed25519"
        hosts_path = root / "known_hosts"
        key_path.write_text(key.rstrip() + "\n")
        hosts_path.write_text(known_hosts.rstrip() + "\n")
        key_path.chmod(0o600)
        hosts_path.chmod(0o600)

        local_port = _free_port()
        cmd = [
            "ssh", "-N",
            "-o", "BatchMode=yes",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=4",
            "-o", f"UserKnownHostsFile={hosts_path}",
            "-i", str(key_path),
            "-p", port,
            "-L", f"127.0.0.1:{local_port}:127.0.0.1:8080",
            f"{user}@{host}",
        ]
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("SSH controller tunnel exited early")
            try:
                with socket.create_connection(("127.0.0.1", local_port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("SSH controller tunnel did not become ready")
        self.base_url = f"http://127.0.0.1:{local_port}"
        self.token = token
        return self

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not self.base_url or not self.token:
            raise RuntimeError("controller transport is not open")
        response = httpx.request(
            method,
            self.base_url + "/" + path.lstrip("/"),
            headers={"Authorization": "Bearer " + self.token},
            json=payload,
            timeout=120,
            follow_redirects=False,
        )
        if response.status_code >= 400:
            detail = ""
            try:
                parsed = response.json()
                detail = str(parsed.get("detail") or "")
            except Exception:
                pass
            raise RuntimeError(
                f"controller request failed: HTTP {response.status_code}"
                + (f" {detail}" if detail else "")
            )
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("controller response is not an object")
        return data

    def __exit__(self, exc_type, exc, tb):
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        if self.tempdir is not None:
            self.tempdir.cleanup()


def request(method: str, path: str, payload: dict | None = None) -> dict:
    with SharedTransport() as transport:
        return transport.request(method, path, payload)
