#!/usr/bin/env python3
"""Local release / deploy helper for the Cekar add-on.

Run with:  python3 -I .dev/release_deploy.py <command> [options]

  release --message TEXT [--dry-run]   bump patch version, changelog, commit, tag, push
  status                               read-only: add-on slug, state, versions
  deploy [--check-only] [--expect V]   store reload + add-on update, wait for new version
  screenshot [--theme dark|light|both] headless browser shots of the panel in HA

Stdlib only (screenshot shells out to `uv run --no-project --with playwright`).
"""
import argparse
import base64
import contextlib
import csv
import datetime as dt
import difflib
import http.client
import io
import json
import os
import re
import shlex
import socket
import struct
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSH_HOST = "linux-turbo"
INCUS_INSTANCE = "haos-test"
ENV_FILE = Path(os.environ.get("CEKAR_TEST_ENV") or Path.home() / ".config/cekar-test/ha.env").expanduser()

CONFIG_YAML = ROOT / "addon/cekar/config.yaml"
PYPROJECT = ROOT / "pyproject.toml"
DOCKERFILE = ROOT / "addon/cekar/Dockerfile"
CHANGELOG = ROOT / "addon/cekar/CHANGELOG.md"


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, **kw)


# --------------------------------------------------------------------------
# release
# --------------------------------------------------------------------------
VERSION_PATTERNS = {
    CONFIG_YAML: re.compile(r'^(version:\s*")([^"]+)(")', re.M),
    PYPROJECT: re.compile(r'^(version\s*=\s*")([^"]+)(")', re.M),
    DOCKERFILE: re.compile(r"^(ARG SOURCE_REF=v)(\S+)()", re.M),
}


def read_version(path):
    matches = VERSION_PATTERNS[path].findall(path.read_text())
    if len(matches) != 1:
        die(f"expected exactly one version in {path.relative_to(ROOT)}, found {len(matches)}")
    return matches[0][1]


def bump_patch(version):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not m:
        die(f"cannot bump non-semver version {version!r}")
    return f"{m[1]}.{m[2]}.{int(m[3]) + 1}"


def cmd_release(args):
    dry = args.dry_run
    problems = []

    branch = run(["git", "branch", "--show-current"]).stdout.strip()
    if branch != "master":
        problems.append(f"not on master (on {branch!r})")
    dirty = run(["git", "status", "--porcelain"]).stdout.strip()
    if dirty:
        problems.append("working tree not clean:\n    " + dirty.replace("\n", "\n    "))

    versions = {p: read_version(p) for p in VERSION_PATTERNS}
    if len(set(versions.values())) != 1:
        problems.append("versions disagree: " + ", ".join(
            f"{p.relative_to(ROOT)}={v}" for p, v in versions.items()))
    old = versions[CONFIG_YAML]
    new = bump_patch(old)
    if run(["git", "rev-parse", "-q", "--verify", f"refs/tags/v{new}"]).returncode == 0:
        problems.append(f"tag v{new} already exists")

    if problems:
        label = "WARNING (would abort a real run)" if dry else "error"
        for p in problems:
            print(f"{label}: {p}", file=sys.stderr)
        if not dry:
            sys.exit(1)

    print(f"version {old} -> {new}")

    # compute new file contents
    new_texts = {}
    for path, pat in VERSION_PATTERNS.items():
        new_texts[path] = pat.sub(lambda m: m[1] + new + m[3], path.read_text(), count=1)
    if not CHANGELOG.exists():
        die(f"{CHANGELOG.relative_to(ROOT)} not found")
    lines = [l.strip() for l in args.message.strip().splitlines() if l.strip()]
    bullets = "\n".join(l if l.startswith("- ") else f"- {l}" for l in lines)
    entry = f"## {new}\n\n{bullets}\n\n"
    text = CHANGELOG.read_text()
    m = re.search(r"^## ", text, re.M)
    if not m:
        die("no '## ' heading found in changelog")
    new_texts[CHANGELOG] = text[:m.start()] + entry + text[m.start():]
    old_texts = {p: (p.read_text() if p.exists() else "") for p in new_texts}

    if dry:
        for p, t in new_texts.items():
            rel = str(p.relative_to(ROOT))
            sys.stdout.writelines(difflib.unified_diff(
                old_texts[p].splitlines(True), t.splitlines(True),
                f"a/{rel}", f"b/{rel}"))
        print()

    steps = [
        ["uv", "run", "pytest", "-q"],
        ["uv", "lock"],
        ["git", "add", "addon/cekar/config.yaml", "pyproject.toml", "uv.lock",
         "addon/cekar/Dockerfile", "addon/cekar/CHANGELOG.md"],
        ["git", "commit", "-m", f"Release {new}"],
        ["git", "tag", f"v{new}"],
        ["git", "push", "origin", "master"],
        ["git", "push", "origin", f"v{new}"],
    ]
    if dry:
        print("dry run: nothing changed. A real run would write the files above and run:")
        for s in steps:
            print("  $", shlex.join(s))
        return

    # tests first, before touching anything
    print("$", shlex.join(steps[0]))
    if subprocess.run(steps[0], cwd=ROOT).returncode != 0:
        die("tests failed; nothing changed")
    for p, t in new_texts.items():
        p.write_text(t)
    for s in steps[1:]:
        print("$", shlex.join(s))
        if subprocess.run(s, cwd=ROOT).returncode != 0:
            die(f"step failed: {' '.join(s)} (files already modified; fix and finish by hand)")
    print(f"released v{new}")


# --------------------------------------------------------------------------
# tunnel + HA access
# --------------------------------------------------------------------------
def find_vm_ip():
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", SSH_HOST, "incus", "list", INCUS_INSTANCE,
         "-f", "csv", "-c", "4"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        die(f"incus list failed: {r.stderr.strip()}")
    cell = next(csv.reader(io.StringIO(r.stdout)))[0]
    for line in cell.splitlines():
        m = re.match(r"(\d+\.\d+\.\d+\.\d+)\s*\((\w+)\)", line.strip())
        if m and m[2] == "enp5s0" and not m[1].startswith("172.30."):
            return m[1]
    die(f"no enp5s0 address found in incus output: {cell!r}")


@contextlib.contextmanager
def tunnel():
    """Yield the local base URL of the HA instance; close the tunnel on exit."""
    ip = find_vm_ip()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        ["ssh", "-o", "BatchMode=yes", "-o", "ControlPath=none", "-N",
         "-o", "ExitOnForwardFailure=yes",
         "-L", f"{port}:{ip}:80", SSH_HOST],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for _ in range(100):
            if proc.poll() is not None:
                die(f"ssh tunnel exited: {proc.stderr.read().decode().strip()}")
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.2)
        else:
            die("ssh tunnel did not come up")
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


def load_credentials():
    vals = {}
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip("'\"")
    try:
        return vals["HA_USER"], vals["HA_PASSWORD"]
    except KeyError as e:
        die(f"{e.args[0]} missing in {ENV_FILE}")


def http_json(base, method, path, body=None, form=None, token=None):
    u = urllib.parse.urlparse(base)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=60)
    headers = {}
    data = None
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body), "application/json"
    if form is not None:
        data, headers["Content-Type"] = (urllib.parse.urlencode(form),
                                         "application/x-www-form-urlencoded")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    conn.request(method, path, data, headers)
    resp = conn.getresponse()
    raw = resp.read().decode()
    conn.close()
    if resp.status >= 400:
        die(f"{method} {path} -> HTTP {resp.status}")
    return raw


def get_access_token(base):
    user, password = load_credentials()
    client_id = base + "/"
    flow = json.loads(http_json(base, "POST", "/auth/login_flow", {
        "client_id": client_id, "handler": ["homeassistant", None],
        "redirect_uri": client_id + "?auth_callback=1"}))
    res = json.loads(http_json(base, "POST", f"/auth/login_flow/{flow['flow_id']}", {
        "client_id": client_id, "username": user, "password": password}))
    if res.get("type") != "create_entry":
        die(f"login failed (flow step {res.get('type')}, errors {res.get('errors')})")
    tok = json.loads(http_json(base, "POST", "/auth/token", form={
        "grant_type": "authorization_code", "code": res["result"], "client_id": client_id}))
    return tok["access_token"]


class WS:
    """Minimal RFC 6455 client (text frames, client-side masking)."""

    def __init__(self, base, token):
        u = urllib.parse.urlparse(base)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=300)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            f"GET /api/websocket HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                die("websocket handshake closed")
            buf += chunk
        head, self.buf = buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            die(f"websocket upgrade refused: {head.split(b'\r\n')[0].decode()}")
        self.next_id = 1
        if self.recv().get("type") != "auth_required":
            die("unexpected websocket greeting")
        self.send({"type": "auth", "access_token": token})
        if self.recv().get("type") != "auth_ok":
            die("websocket auth failed")

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                die("websocket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, obj):
        payload = json.dumps(obj).encode()
        n = len(payload)
        hdr = b"\x81"
        if n < 126:
            hdr += bytes([0x80 | n])
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(hdr + mask + masked)

    def recv(self):
        message = b""
        while True:
            b0, b1 = self._read(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            data = self._read(n)  # server frames are unmasked
            op = b0 & 0x0F
            if op == 0x8:
                die("websocket closed by server")
            if op == 0x9:  # ping -> pong
                self.sock.sendall(b"\x8a\x80" + os.urandom(4))
                continue
            if op == 0xA:
                continue
            message += data
            if b0 & 0x80:
                return json.loads(message)

    def call(self, **msg):
        msg["id"] = self.next_id
        self.next_id += 1
        self.send(msg)
        while True:
            r = self.recv()
            if r.get("id") == msg["id"] and r.get("type") == "result":
                if not r["success"]:
                    raise RuntimeError(f"{msg.get('endpoint') or msg['type']}: {r['error']}")
                return r["result"]

    def supervisor(self, endpoint, method="get", **extra):
        return self.call(type="supervisor/api", endpoint=endpoint, method=method, **extra)

    def close(self):
        with contextlib.suppress(OSError):
            self.sock.close()


def find_slug(ws):
    addons = ws.supervisor("/addons")["addons"]
    matches = [a for a in addons if a["slug"].endswith("_cekar")]
    if len(matches) != 1:
        die(f"expected one *_cekar add-on, found {[a['slug'] for a in addons]}")
    return matches[0]["slug"]


def addon_info(ws, slug):
    return ws.supervisor(f"/addons/{slug}/info")


def print_status(info):
    print(f"slug:      {info['slug']}")
    print(f"state:     {info['state']}")
    print(f"installed: {info['version']}")
    print(f"available: {info['version_latest']}")


def expected_version():
    return read_version(CONFIG_YAML)


def cmd_status(args):
    with tunnel() as base:
        token = get_access_token(base)
        ws = WS(base, token)
        try:
            print_status(addon_info(ws, find_slug(ws)))
        finally:
            ws.close()


def cmd_deploy(args):
    expect = args.expect or expected_version()
    with tunnel() as base:
        token = get_access_token(base)
        ws = WS(base, token)
        try:
            if not args.check_only:
                print("reloading store ...")
                ws.supervisor("/store/reload", "post")
            slug = find_slug(ws)
            info = addon_info(ws, slug)
            print_status(info)
            print(f"expected:  {expect}")
            if args.check_only:
                print("check-only: no reload, no update.")
                return
            if info["version"] != expect:
                if info["version_latest"] != expect:
                    die(f"store offers {info['version_latest']}, expected {expect} "
                        "(is the tag pushed and the repository refreshed?)")
                print(f"updating {info['version']} -> {expect} ...")
                ws.call(type="hassio/update/addon", addon=slug, backup=False)
            deadline = time.time() + args.timeout
            while time.time() < deadline:
                info = addon_info(ws, slug)
                if info["state"] == "started" and info["version"] == expect:
                    print(f"OK: {slug} started on {expect}")
                    return
                time.sleep(3)
            print_status(info)
            print("--- add-on log tail ---", file=sys.stderr)
            try:
                logs = http_json(base, "GET", f"/api/hassio/addons/{slug}/logs", token=token)
                print("\n".join(logs.splitlines()[-40:]), file=sys.stderr)
            except SystemExit:
                print("(could not fetch logs)", file=sys.stderr)
            die(f"timed out after {args.timeout}s waiting for started/{expect}")
        finally:
            ws.close()


# --------------------------------------------------------------------------
# screenshot
# --------------------------------------------------------------------------
PLAYWRIGHT_SCRIPT = r'''
import glob, json, os, sys
from playwright.sync_api import sync_playwright
cfg = json.loads(sys.argv[1])
exe = sorted(glob.glob(os.path.expanduser(
    "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell")))[-1]
user, pw = os.environ["HA_USER"], os.environ["HA_PASSWORD"]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    for theme in cfg["themes"]:
        for name, vp in cfg["viewports"].items():
            ctx = b.new_context(viewport=vp, device_scale_factor=1)
            # HA reads the browser-local theme choice from localStorage (no profile change).
            ctx.add_init_script("localStorage.setItem('selectedTheme', JSON.stringify({dark: %s}));"
                                % ("true" if theme == "dark" else "false"))
            page = ctx.new_page()
            page.goto(cfg["base"] + "/", wait_until="networkidle")
            page.fill("input[name=username]", user)
            page.fill("input[name=password]", pw)
            page.press("input[name=password]", "Enter")
            page.wait_for_url(lambda u: "auth/authorize" not in u, timeout=30000)
            page.wait_for_selector("home-assistant", timeout=30000)
            page.goto(cfg["base"] + cfg["panel"], wait_until="networkidle")
            page.wait_for_timeout(cfg["wait_ms"])
            out = "%s/%s-%s-%s.png" % (cfg["outdir"], cfg["stamp"], theme, name)
            page.screenshot(path=out)
            print(out)
            ctx.close()
    b.close()
'''


def cmd_screenshot(args):
    outdir = ROOT / ".mockups/ha-v2/screenshots"
    outdir.mkdir(parents=True, exist_ok=True)
    user, password = load_credentials()
    with tunnel() as base:
        token = get_access_token(base)
        ws = WS(base, token)
        try:
            slug = find_slug(ws)
            # The sidebar panel of an ingress add-on lives at /<url_path> (verified via get_panels).
            panels = ws.call(type="get_panels")
            panel = next((v["url_path"] for v in panels.values()
                          if (v.get("config") or {}).get("addon") == slug), None)
            if not panel:
                die(f"no sidebar panel found for {slug}")
        finally:
            ws.close()
        cfg = {
            "base": base, "panel": f"/{panel}", "outdir": str(outdir),
            "stamp": dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
            "themes": ["dark", "light"] if args.theme == "both" else [args.theme],
            "viewports": {"desktop": {"width": 1400, "height": 900},
                          "phone": {"width": 390, "height": 844}},
            "wait_ms": args.wait_ms,
        }
        env = dict(os.environ, HA_USER=user, HA_PASSWORD=password)
        r = subprocess.run(
            ["uv", "run", "--no-project", "--with", "playwright", "python", "-I", "-c",
             PLAYWRIGHT_SCRIPT, json.dumps(cfg)], env=env, cwd="/tmp")
        if r.returncode != 0:
            die("screenshot run failed")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("release")
    p.add_argument("--message", required=True, help="CHANGELOG text for the new version")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_release)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    p = sub.add_parser("deploy")
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--expect", help="expected version (default: version in config.yaml)")
    p.add_argument("--timeout", type=int, default=600)
    p.set_defaults(fn=cmd_deploy)
    p = sub.add_parser("screenshot")
    p.add_argument("--theme", choices=["dark", "light", "both"], default="both")
    p.add_argument("--wait-ms", type=int, default=3000)
    p.set_defaults(fn=cmd_screenshot)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
