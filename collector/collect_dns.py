"""Collect DNS responses from all Bitcoin mainnet DNS seeds.

Queries every seed hostname (plain and supported service-bit subdomains)
for A and AAAA records via ``dig``. Each query returns a random subset of
the seeder's pool, so every hostname/qtype pair is queried REPEATS times
per run to sample the pool.

Output: one JSON line per query appended to ``data/dns/YYYY-MM-DD.jsonl``
(UTC date). Failed or empty responses are recorded too — an NXDOMAIN on a
service-bit subdomain or a dead seed is a data point, not an error.
"""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from seeds import DNS_SEEDS

REPEATS = 3
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "dns"


def dig(hostname: str, qtype: str) -> dict:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cmd = [
        "dig", "+tries=2", "+time=5", "+noall", "+answer", "+comments",
        hostname, qtype,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = proc.stdout
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ts": ts, "hostname": hostname, "qtype": qtype,
                "status": f"error:{type(exc).__name__}", "ttl": None, "records": []}

    status = "UNKNOWN"
    records: list[str] = []
    ttl: int | None = None
    for line in output.splitlines():
        if line.startswith(";;") and "status:" in line:
            status = line.split("status:")[1].split(",")[0].strip()
        if line.startswith(";"):
            continue
        parts = line.split()
        # dig answer line: <name> <ttl> IN <type> <rdata>
        if len(parts) >= 5 and parts[3] == qtype:
            records.append(parts[4])
            if ttl is None:
                try:
                    ttl = int(parts[1])
                except ValueError:
                    pass
    return {"ts": ts, "hostname": hostname, "qtype": qtype,
            "status": status, "ttl": ttl, "records": records}


def main() -> int:
    queries: list[tuple[str, str, str]] = []
    for seed, meta in DNS_SEEDS.items():
        hostnames = [seed] + [f"{bits}.{seed}" for bits in meta["service_bits"]]
        for hostname in hostnames:
            for qtype in ("A", "AAAA"):
                for _ in range(REPEATS):
                    queries.append((seed, hostname, qtype))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda q: (q[0], dig(q[1], q[2])), queries))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    outfile = DATA_DIR / f"{day}.jsonl"
    with outfile.open("a", encoding="utf-8") as fh:
        for seed, result in results:
            fh.write(json.dumps({"seed": seed, **result}, separators=(",", ":")) + "\n")

    answered = sum(1 for _, r in results if r["records"])
    total_records = sum(len(r["records"]) for _, r in results)
    print(f"{len(results)} queries, {answered} with answers, "
          f"{total_records} address records -> {outfile}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
