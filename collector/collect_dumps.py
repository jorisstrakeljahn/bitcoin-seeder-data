"""Archive the full crawler dumps published by Bitcoin seeder operators.

Downloads each ``seeds.txt.gz`` crawler dump, the JSON API snapshots
(Blockchair, btcnodes.io), the dated bitnod.es CSV, and the newest KIT
dossier from its directory index; stores them unmodified (raw
preservation, JSON/CSV gzipped) under
``data/dumps/<source>/YYYY-MM-DD.<ext>`` (UTC date), and appends a
manifest line with URL, size and SHA-256 for later citation/integrity.

Idempotent per day: sources that already have today's file are skipped,
so a rerun after a partial failure only fetches what is missing.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from seeds import API_SOURCES, CRAWLER_DUMPS, DATED_SOURCES, INDEXED_SOURCES

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "dumps"
USER_AGENT = "bitcoin-seeder-data-collector (research archive)"
TIMEOUT = 120


def fetch(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, resp.read()


def resolve_dated(name: str, meta: dict) -> tuple[str, str] | None:
    """Return (url, date) for the newest available dated file, or None."""
    today = datetime.now(timezone.utc).date()
    for offset in range(meta["lookback_days"] + 1):
        date = (today - timedelta(days=offset)).isoformat()
        if (DATA_DIR / name / f"{date}.{meta['kind']}.gz").exists():
            return None  # newest available file already archived
        url = meta["url_template"].format(date=date)
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30):
                return url, date
        except urllib.error.HTTPError:
            continue
    return None


def resolve_indexed(name: str, meta: dict) -> tuple[str, str] | None:
    """Scrape the directory index, return (url, date) of the newest file.

    The pattern's first group must capture the file's YYYYMMDD date. Files
    already archived for that date are skipped like the dated sources.
    """
    _, body = fetch(meta["index_url"])
    matches = list(re.finditer(meta["file_pattern"],
                               body.decode("utf-8", "replace")))
    if not matches:
        return None
    newest = max(matches, key=lambda m: m.group(1))
    date = datetime.strptime(newest.group(1), "%Y%m%d").date().isoformat()
    if (DATA_DIR / name / f"{date}.{meta['kind']}.gz").exists():
        return None
    return meta["index_url"] + newest.group(0), date


def main() -> int:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    manifest_path = DATA_DIR / "manifest.jsonl"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # (name, url, filename, gzip the body before storing?)
    targets = []
    for name, meta in CRAWLER_DUMPS.items():
        targets.append((name, meta["url"], f"{day}.txt.gz", False))
    for name, meta in API_SOURCES.items():
        targets.append((name, meta["url"], f"{day}.json.gz", True))
    for name, meta in DATED_SOURCES.items():
        resolved = resolve_dated(name, meta)
        if resolved is None:
            print(f"{name}: no new dated file available, skipping")
            continue
        url, date = resolved
        targets.append((name, url, f"{date}.{meta['kind']}.gz", True))
    for name, meta in INDEXED_SOURCES.items():
        try:
            resolved = resolve_indexed(name, meta)
        except Exception as exc:
            print(f"{name}: index scrape failed ({exc})", file=sys.stderr)
            continue
        if resolved is None:
            print(f"{name}: no new indexed file available, skipping")
            continue
        url, date = resolved
        targets.append((name, url, f"{date}.{meta['kind']}.gz", True))

    failures = 0
    for name, url, filename, needs_gzip in targets:
        outdir = DATA_DIR / name
        outfile = outdir / filename
        if outfile.exists():
            print(f"{name}: {outfile.name} already exists, skipping")
            continue

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "date": day,
            "source": name,
            "url": url,
        }
        try:
            status, body = fetch(url)
        except Exception as exc:
            failures += 1
            entry.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            print(f"{name}: FAILED ({entry['error']})", file=sys.stderr)
        else:
            if needs_gzip:
                body = gzip.compress(body, mtime=0)
            outdir.mkdir(parents=True, exist_ok=True)
            outfile.write_bytes(body)
            entry.update({
                "ok": True,
                "http_status": status,
                "file": str(outfile.relative_to(DATA_DIR.parent.parent)),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            })
            print(f"{name}: {len(body)} bytes -> {outfile}")

        with manifest_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")

    # Partial failures must not fail the run: whatever was fetched is
    # committed, and the manifest records what is missing.
    return 0 if failures < len(targets) else 1


if __name__ == "__main__":
    sys.exit(main())
