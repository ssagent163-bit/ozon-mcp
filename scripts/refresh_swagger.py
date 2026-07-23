#!/usr/bin/env python3
"""Refresh bundled Ozon swagger snapshots (replacement for missing parse_swagger.py).

Added 2026-07-20 for the ozon-mcp fork (original "parser repo / drop-zone"
from README was never published upstream).

Usage (from repo root):
  python3 scripts/refresh_swagger.py --from-files seller.json perf.json
      Install already-downloaded specs (recommended: download both files
      in a normal browser session, docs.ozon.ru is behind an anti-bot).
  python3 scripts/refresh_swagger.py
      Try to download both specs directly (works only if docs.ozon.ru
      lets the request through; otherwise use --from-files).

What it does:
  1. Validates each spec: JSON, has "paths" and "components", title
     mentions Seller/Performance, sane method count (>=350 / >=35).
  2. Writes src/ozon_mcp/data/{seller_swagger.json,perf_swagger.json}
     compactly (same formatting as bundled snapshots).
  3. Regenerates swagger_meta.json (refreshed_at, version, method_count,
     sha256 over written bytes).
  4. Prints old -> new method counts. Old files are recoverable via git.

After refreshing, run the test suite (golden snapshots may need updating):
  uv run pytest tests/ --ignore=tests/live
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "src" / "ozon_mcp" / "data"

SELLER_URL = "https://docs.ozon.ru/api/seller/swagger.json"
PERF_URL = "https://docs.ozon.ru/api/performance/swagger.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

CHECKS = {
    "seller": {"title_must_contain": "Seller", "min_methods": 350},
    "performance": {"title_must_contain": "Performance", "min_methods": 35},
}


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


_HTTP_VERBS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _count_methods(spec: dict) -> int:
    """Count operations (path+verb pairs) — matches the original meta numbers."""
    return sum(1 for item in spec["paths"].values()
               for verb in item if verb in _HTTP_VERBS)


def _load_and_validate(raw: bytes, kind: str) -> dict:
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"[{kind}] not valid JSON (anti-bot page instead of spec?): {exc}")
    for section in ("paths", "components", "info"):
        if section not in spec:
            sys.exit(f"[{kind}] missing OpenAPI section '{section}'")
    title = str(spec["info"].get("title", ""))
    want = CHECKS[kind]["title_must_contain"]
    if want.lower() not in title.lower():
        sys.exit(f"[{kind}] unexpected title {title!r} (expected to contain {want!r})")
    n = _count_methods(spec)
    if n < CHECKS[kind]["min_methods"]:
        sys.exit(f"[{kind}] only {n} operations — looks truncated, aborting")
    return spec


def _install(spec: dict, filename: str) -> tuple[int, str, object]:
    out = DATA_DIR / filename
    old_count = None
    if out.exists():
        try:
            old_count = _count_methods(json.loads(out.read_text("utf-8")))
        except Exception:
            pass
    data = json.dumps(spec, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    out.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    count = _count_methods(spec)
    print(f"  {filename}: {old_count} -> {count} methods, sha256={sha[:12]}…")
    return count, sha, spec["info"].get("version")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-files", nargs=2, metavar=("SELLER", "PERF"),
                    help="use already-downloaded spec files instead of downloading")
    args = ap.parse_args()

    if args.from_files:
        seller_raw = Path(args.from_files[0]).read_bytes()
        perf_raw = Path(args.from_files[1]).read_bytes()
    else:
        print(f"downloading {SELLER_URL} …")
        seller_raw = _download(SELLER_URL)
        print(f"downloading {PERF_URL} …")
        perf_raw = _download(PERF_URL)

    seller = _load_and_validate(seller_raw, "seller")
    perf = _load_and_validate(perf_raw, "performance")

    print("installing:")
    s_count, s_sha, s_ver = _install(seller, "seller_swagger.json")
    p_count, p_sha, p_ver = _install(perf, "perf_swagger.json")

    meta = {
        "refreshed_at": _dt.datetime.now(_dt.timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seller": {"version": s_ver, "method_count": s_count, "sha256": s_sha},
        "performance": {"version": p_ver, "method_count": p_count, "sha256": p_sha},
    }
    (DATA_DIR / "swagger_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print("swagger_meta.json updated:", meta["refreshed_at"])
    print("done. Now run: uv run pytest tests/ --ignore=tests/live")


if __name__ == "__main__":
    main()
