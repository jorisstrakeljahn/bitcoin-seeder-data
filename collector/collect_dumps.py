"""Archive the full crawler dumps published by Bitcoin seeder operators.

Downloads each ``seeds.txt.gz`` crawler dump and the Blockchair nodes API
response, stores them unmodified (raw preservation) under
``data/dumps/<source>/YYYY-MM-DD.<ext>`` (UTC date), and appends a
manifest line with URL, size and SHA-256 for later citation/integrity.

Idempotent per day: sources that already have today's file are skipped,
so a rerun after a partial failure only fetches what is missing.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from seeds import API_SOURCES, CRAWLER_DUMPS

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "dumps"
USER_AGENT = "bitcoin-seeder-data-collector (research archive)"
TIMEOUT = 120


def fetch(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, resp.read()


def main() -> int:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    manifest_path = DATA_DIR / "manifest.jsonl"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    targets = []
    for name, meta in CRAWLER_DUMPS.items():
        targets.append((name, meta["url"], "txt.gz", False))
    for name, meta in API_SOURCES.items():
        targets.append((name, meta["url"], "json.gz", True))

    failures = 0
    for name, url, ext, needs_gzip in targets:
        outdir = DATA_DIR / name
        outfile = outdir / f"{day}.{ext}"
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
