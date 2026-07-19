"""Share of seeder-tracked endpoints that never completed a VERSION handshake.

Reads the latest archived seeds.txt dumps of the two live dnsseedrs crawlers
(fish.foo and achow101) and reports, per network and in total, how many of
the exported endpoints have ``last_seen == 0``, i.e. the crawler has tried
them (dnsseedrs exports only rows with try_count > 0) but never received a
VERSION message.

Interpretation caveats, in decreasing order of importance:
- dnsseedrs deletes never-successful rows after more than 10 failed attempts
  (src/crawl.rs), so this is a rolling window over recently gossiped
  endpoints, not a lifetime count.
- These are current-database state values from two vantage points; they are
  not a reproduction of an active recrawl measurement.
- The frozen sipa and virtu dumps use different retention semantics and are
  deliberately excluded.

Outputs (analysis/output/): seeder_never_version.csv, plus a summary printed
to stdout.

Usage:
    python analysis/seeder_never_version.py
"""

from __future__ import annotations

import csv
import gzip
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DUMPS = REPO / "data" / "dumps"
OUT = REPO / "analysis" / "output"

SEEDERS = {"fishfoo": "fish.foo", "achow101": "achow101"}
NETWORKS = ("ipv4", "ipv6", "onion", "i2p", "cjdns")


def classify_network(address: str) -> str:
    if ".onion:" in address:
        return "onion"
    if ".b32.i2p:" in address:
        return "i2p"
    if address.startswith("["):
        return "cjdns" if address[1:3].lower() == "fc" else "ipv6"
    return "ipv4"


def count_dump(path: Path) -> Counter:
    """Count (network, never|seen) pairs in one dnsseedrs seeds.txt dump."""
    counts: Counter = Counter()
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            never = parts[2] == "0"
            counts[classify_network(parts[0]), "never" if never else "seen"] += 1
    return counts


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for source, label in SEEDERS.items():
        path = sorted((DUMPS / source).glob("*.txt.gz"))[-1]
        day = path.name[:10]
        counts = count_dump(path)
        for network in (*NETWORKS, "total"):
            if network == "total":
                never = sum(counts[net, "never"] for net in NETWORKS)
                seen = sum(counts[net, "seen"] for net in NETWORKS)
            else:
                never = counts[network, "never"]
                seen = counts[network, "seen"]
            total = never + seen
            if total == 0:
                continue
            rows.append({
                "source": label,
                "dump_day": day,
                "network": network,
                "tracked_endpoints": total,
                "never_version": never,
                "never_version_share": never / total,
            })
        total_row = rows[-1]
        print(
            f"{label} ({day}): {total_row['never_version']:,} of "
            f"{total_row['tracked_endpoints']:,} tracked endpoints never sent "
            f"VERSION ({float(total_row['never_version_share']):.1%})"
        )

    with open(OUT / "seeder_never_version.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("wrote", OUT / "seeder_never_version.csv")


if __name__ == "__main__":
    main()
