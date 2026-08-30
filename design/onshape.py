"""Minimal Onshape REST client.

The CAD for this project is driven through the API, not the browser. That is a
deliberate choice and it has already paid for itself: reading the feature tree as
JSON exposed two defects that weeks of clicking had hidden (a hinge dimension taken
to a circle's tangent instead of its centre, and a datum plane that drove no
geometry). See docs/01-next-steps.md.

Credentials are NEVER stored in the repo. They are read at call time from
~/.onshape_keys, which may be either JSON with access_key/secret_key fields or a
flat KEY=VALUE / two-line file. Nothing in this module prints, logs, or returns a
secret; only the derived Authorization header is constructed, and that stays local
to the request.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://cad.onshape.com/api/v10"

_KEYFILE = Path(os.environ.get("ONSHAPE_KEYS", Path.home() / ".onshape_keys"))

# Field names seen in the wild for the same two values.
_ACCESS_NAMES = ("access_key", "accesskey", "access", "onshape_access_key", "api_key", "key")
_SECRET_NAMES = ("secret_key", "secretkey", "secret", "onshape_secret_key", "api_secret")


def _credentials() -> tuple[str, str]:
    """Return (access_key, secret_key). Tolerates several plausible file layouts."""
    env_a, env_s = os.environ.get("ONSHAPE_ACCESS_KEY"), os.environ.get("ONSHAPE_SECRET_KEY")
    if env_a and env_s:
        return env_a, env_s

    if not _KEYFILE.exists():
        raise SystemExit(
            f"No Onshape credentials: {_KEYFILE} not found and "
            "ONSHAPE_ACCESS_KEY / ONSHAPE_SECRET_KEY are unset."
        )

    text = _KEYFILE.read_text()

    # 1. JSON object, possibly nested one level.
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        flat: dict[str, str] = {}
        for k, v in data.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    flat[k2.strip().lower()] = str(v2)
            else:
                flat[k.strip().lower()] = str(v)
        a = next((flat[n] for n in _ACCESS_NAMES if n in flat), None)
        s = next((flat[n] for n in _SECRET_NAMES if n in flat), None)
        if a and s:
            return a, s

    # 2. KEY=VALUE or KEY: VALUE lines.
    kv: dict[str, str] = {}
    bare: list[str] = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("export ").strip()
        if not line or line.startswith("#"):
            continue
        for sep in ("=", ":"):
            if sep in line:
                k, _, v = line.partition(sep)
                kv[k.strip().strip('"').lower()] = v.strip().strip('",')
                break
        else:
            bare.append(line)
    a = next((kv[n] for n in _ACCESS_NAMES if n in kv), None)
    s = next((kv[n] for n in _SECRET_NAMES if n in kv), None)
    if a and s:
        return a, s

    # 3. Two bare lines, access then secret.
    if len(bare) >= 2:
        return bare[0], bare[1]

    raise SystemExit(
        f"Could not parse Onshape credentials from {_KEYFILE}. Expected JSON with "
        "access_key/secret_key, KEY=VALUE lines, or two bare lines (access, then secret)."
    )


def _auth_header() -> str:
    a, s = _credentials()
    return "Basic " + base64.b64encode(f"{a}:{s}".encode()).decode()


# Onshape rate-limits sustained scripted use with HTTP 429, and there is no documented
# budget. A single call almost always succeeds; it is the scripts that make dozens in a
# row -- canard_sweep.py, make_hinge_stack.py, anything that walks every part's mass
# properties -- that trip it, and they then fail HALFWAY THROUGH, which for a write
# sequence is the worst possible place to stop.
#
# Retrying is safe: a 429 means the request was REJECTED, not applied, so a retried POST
# or DELETE cannot double-apply. Back off exponentially and honour Retry-After when the
# server sends one.
RETRY_STATUS = {429, 502, 503, 504}
MAX_RETRIES = 6
BACKOFF_BASE = 8.0  # seconds; 8, 16, 32, 64, 128, 256 -- about 8 minutes in total

# NEVER sleep for an arbitrary Retry-After. Onshape's 429 is not only a burst limit: it
# also enforces a LONG-WINDOW quota, and when that one is exhausted the server answers
# with a Retry-After measured in HOURS -- 49699 seconds, just under fourteen, was the
# value seen on 2026-08-30. Honouring that literally turns a script into a process that
# looks like it is working for the rest of the day.
#
# So cap it. Past the cap the right behaviour is to fail immediately and say WHEN the
# quota comes back, because that is a fact the caller can act on and a sleeping process
# is not.
MAX_RETRY_AFTER = 300.0  # seconds


def call(method: str, path: str, body: dict | None = None, query: dict | None = None):
    """One API call. `path` is relative to the API root, e.g. '/documents'.

    Retries on 429 and on transient 5xx, with exponential backoff. Everything else
    raises immediately, because a 400 will not get better by being asked again.
    """
    url = BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    payload = json.dumps(body).encode() if body is not None else None

    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(url, data=payload, method=method)
        req.add_header("Authorization", _auth_header())
        req.add_header("Accept", "application/json;charset=UTF-8;qs=0.09")
        if payload is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:2000]
            if e.code in RETRY_STATUS and attempt < MAX_RETRIES:
                wait = float(e.headers.get("Retry-After") or BACKOFF_BASE * 2 ** attempt)
                if wait > MAX_RETRY_AFTER:
                    resets = time.strftime("%a %H:%M", time.localtime(time.time() + wait))
                    raise RuntimeError(
                        f"{method} {path} -> HTTP {e.code}\n"
                        f"Onshape wants {wait:.0f}s ({wait / 3600:.1f} h) before the next "
                        f"request, which means the long-window API quota is spent, not "
                        f"that this was a burst.\nIt comes back about {resets}. Nothing "
                        f"was written by this call. Re-run then; do not sit and wait."
                    ) from None
                print(f"    [onshape] HTTP {e.code} on {method} {path.split('?')[0]}; "
                      f"retrying in {wait:.0f}s "
                      f"({attempt + 1}/{MAX_RETRIES})", flush=True)
                time.sleep(wait)
                continue
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}\n{detail}") from None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode(errors="replace")


def get(path, **query):
    return call("GET", path, query=query or None)


def post(path, body, **query):
    return call("POST", path, body=body, query=query or None)


if __name__ == "__main__":
    me = get("/users/sessioninfo")
    print("authenticated as:", me.get("name") or me.get("email", "?"))
