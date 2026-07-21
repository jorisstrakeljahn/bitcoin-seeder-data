"""Evaluate data sources for the ASmap dashboard Network Tab.

Answers three questions from the archived raw data:

1. Are DNS seeder responses, accumulated over time, a viable snapshot
   source for the Network Tab metrics (coverage, HHI, bucketing,
   groups-to-50%), or do the metrics require a full crawl?
2. How large is the sampling error of each metric as a function of
   snapshot size (random subsamples of a full crawl)?
3. Why do bitnod.es (BitMEX) and btcnodes.io diverge although both
   descend from the ayeowch/bitnodes codebase, and how much do two
   instances of the same seeder software (dnsseedrs: achow101 vs
   fish.foo) diverge?

The netgroup metrics use IP-prefix proxies (/16 for the default
netgroup, /8 as a crude AS-level stand-in) because this repo carries no
ASmap builds; the *relative* size sensitivity carries over to the real
ASmap lookups. Output: ``analysis/output/network_tab_eval.md``.

Usage:
    .venv/bin/python analysis/network_tab_eval.py [--day YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
from collections import Counter, defaultdict
from datetime import date, timedelta
from ipaddress import ip_address
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DUMPS = REPO / "data" / "dumps"
DNS = REPO / "data" / "dns"
OUT = REPO / "analysis" / "output" / "network_tab_eval.md"

SAMPLE_SIZES = (100, 250, 500, 1000, 2000, 4000)
SAMPLE_DRAWS = 20
DNS_WINDOWS_DAYS = (1, 3, 7)
BITMEX_FRESH_DAYS = 1


# ------------------------------------------------------------------ helpers

def host_of(addr: str) -> str:
    if addr.startswith("["):
        return addr[1: addr.index("]")].lower()
    return addr.rsplit(":", 1)[0].lower()


def is_clearnet(addr: str) -> bool:
    lower = addr.lower()
    if ".onion" in lower or ".i2p" in lower:
        return False
    host = host_of(addr)
    if ":" in host and host.startswith("fc"):
        return False
    return True


def group_default(host: str) -> str:
    """Proxy for Core's default netgroup: /16 for IPv4, /32 for IPv6."""
    if ip_address(host).version == 4:
        a, b, *_ = host.split(".")
        return f"{a}.{b}"
    return ":".join(host.split(":")[:2])


def group_as_proxy(host: str) -> str:
    """Crude AS-level proxy: /8 for IPv4, /16 for IPv6."""
    if ip_address(host).version == 4:
        return host.split(".")[0]
    return host.split(":")[0]


def hhi(counts: Counter) -> float:
    total = sum(counts.values())
    return sum((n / total) ** 2 for n in counts.values()) if total else 0.0


def groups_to_half(counts: Counter) -> int | None:
    total = sum(counts.values())
    if not total:
        return None
    acc = 0
    for i, (_, n) in enumerate(counts.most_common(), 1):
        acc += n
        if acc >= total / 2:
            return i
    return None


def tv_distance(a: Counter, b: Counter) -> float:
    ta, tb = sum(a.values()), sum(b.values())
    if not ta or not tb:
        return 1.0
    return 0.5 * sum(abs(a.get(k, 0) / ta - b.get(k, 0) / tb)
                     for k in set(a) | set(b))


def markdown_table(headers, rows) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ loading

def newest_common_day() -> str:
    """Newest day for which btcnodes, bitmex and achow101 all exist."""
    days = None
    for src in ("btcnodes", "bitmex", "achow101", "fishfoo"):
        have = {p.name[:10] for p in (DUMPS / src).glob("*.gz")}
        days = have if days is None else days & have
    return max(days)


def load_btcnodes_hosts(day: str) -> set[str]:
    with gzip.open(DUMPS / "btcnodes" / f"{day}.json.gz", "rt") as fh:
        snap = json.load(fh)
    return {host_of(a) for a in snap["nodes"] if is_clearnet(a)}


def load_bitmex(day: str):
    with gzip.open(DUMPS / "bitmex" / f"{day}.csv.gz", "rt",
                   errors="replace") as fh:
        return list(csv.DictReader(fh))


def load_seeds_good(source: str, day: str) -> set[str]:
    hosts: set[str] = set()
    with gzip.open(DUMPS / source / f"{day}.txt.gz", "rt",
                   errors="replace") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            p = line.split()
            if len(p) >= 3 and p[1] == "1" and is_clearnet(p[0]):
                hosts.add(host_of(p[0]))
    return hosts


def load_dns_per_day(before: str) -> dict[str, dict[str, set[str]]]:
    """day -> seed -> set of lowercased A+AAAA records, up to ``before``."""
    days: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set))
    for path in sorted(DNS.glob("*.jsonl")):
        if path.stem > before:
            continue
        for line in path.open(encoding="utf-8"):
            e = json.loads(line)
            if e["status"] == "NOERROR" and e["records"]:
                days[path.stem][e["seed"]] |= {
                    r.lower() for r in e["records"]}
    return days


# ------------------------------------------------------------------ report

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=None,
                        help="reference day (default: newest common day)")
    args = parser.parse_args()
    day = args.day or newest_common_day()

    parts: list[str] = []
    add = parts.append
    add("# Network Tab source evaluation\n")
    add(f"Reference day: **{day}**. Generated by "
        "`analysis/network_tab_eval.py` from the raw archives.\n")
    add("Netgroup metrics use IP-prefix proxies (/16 default netgroup, "
        "/8 as AS stand-in) since this repo carries no ASmap builds; "
        "the size sensitivity transfers to real ASmap lookups.\n")

    btc_hosts = load_btcnodes_hosts(day)
    btc_groups = Counter(group_default(h) for h in btc_hosts)

    # 1. DNS accumulation windows vs full crawls -----------------------
    dns_days = load_dns_per_day(day)
    all_days = sorted(dns_days)
    seeds = sorted({s for d in dns_days.values() for s in d})

    def accumulate(window_days, wanted=None) -> set[str]:
        out: set[str] = set()
        for d in window_days:
            for s, recs in dns_days[d].items():
                if wanted is None or s in wanted:
                    out |= recs
        return out

    add("\n## 1. DNS seeder responses, accumulated, vs. full crawls\n")
    add(f"DNS data: {all_days[0]} .. {all_days[-1]} "
        f"({len(all_days)} days, 6h cadence, 3 repeats/query).\n")
    add(f"Reference full crawl (btcnodes {day}): "
        f"**{len(btc_hosts)}** clearnet hosts, /16-HHI "
        f"{hhi(btc_groups):.4f}, groups-to-50% "
        f"{groups_to_half(btc_groups)}, {len(btc_groups)} /16 groups.\n")

    rows = []
    variants = [("all 9 seeds", None),
                ("achownodes only", ["seed.mainnet.achownodes.xyz"]),
                ("sipa.be only", ["seed.bitcoin.sipa.be"])]
    for wdays in DNS_WINDOWS_DAYS:
        window = all_days[-wdays:]
        for label, wanted in variants:
            acc = accumulate(window, wanted)
            if not acc:
                continue
            g = Counter(group_default(h) for h in acc)
            rows.append([
                f"{wdays}d", label, len(acc),
                f"{len(acc & btc_hosts) / len(acc):.0%}",
                f"{len(acc & btc_hosts) / len(btc_hosts):.0%}",
                f"{hhi(g):.4f}", groups_to_half(g),
                f"{tv_distance(g, btc_groups):.3f}"])
    add(markdown_table(
        ["window", "seeds", "unique IPs", "precision vs btcnodes",
         "recall of btcnodes", "/16-HHI", "G50", "TVD vs btcnodes"],
        rows))
    add("\nPrecision = share of accumulated DNS IPs present in the "
        "btcnodes snapshot of the reference day; recall = share of the "
        "btcnodes snapshot covered. TVD = total variation distance "
        "between the /16 group distributions.\n")

    # per-seed yield
    add("\n### Per-seed yield\n")
    rows = []
    for s in seeds:
        day1 = len(dns_days[all_days[-1]].get(s, set()))
        total_set = accumulate(all_days, [s])
        prec = (len(total_set & btc_hosts) / len(total_set)
                if total_set else 0)
        rows.append([s, day1, len(total_set), f"{prec:.0%}"])
    add(markdown_table(
        ["seed", f"unique IPs {all_days[-1]}",
         f"unique IPs all {len(all_days)}d",
         "share in btcnodes (ref day)"], rows))

    # 2. sampling error ------------------------------------------------
    add("\n## 2. Sampling error: random subsamples of the full crawl\n")
    add("Mean over "
        f"{SAMPLE_DRAWS} uniform draws from the btcnodes clearnet set. "
        "Shows which metrics survive a small snapshot and which are "
        "structurally size-dependent.\n")
    random.seed(42)
    hosts_list = sorted(btc_hosts)
    full_default = len({group_default(h) for h in btc_hosts})
    full_as = len({group_as_proxy(h) for h in btc_hosts})
    rows = []
    for n in SAMPLE_SIZES:
        hh, g5, tv, ratio = [], [], [], []
        for _ in range(SAMPLE_DRAWS):
            sample = random.sample(hosts_list, n)
            g = Counter(group_default(h) for h in sample)
            hh.append(hhi(g))
            g5.append(groups_to_half(g) or 0)
            tv.append(tv_distance(g, btc_groups))
            ratio.append(len({group_default(h) for h in sample})
                         / len({group_as_proxy(h) for h in sample}))
        rows.append([n, f"{sum(hh) / len(hh):.4f}",
                     f"{sum(g5) / len(g5):.0f}",
                     f"{sum(ratio) / len(ratio):.2f}",
                     f"{sum(tv) / len(tv):.3f}"])
    rows.append([f"full ({len(hosts_list)})",
                 f"{hhi(btc_groups):.4f}",
                 groups_to_half(btc_groups),
                 f"{full_default / full_as:.2f}", "0.000"])
    add(markdown_table(
        ["n", "/16-HHI", "groups-to-50%",
         "bucketing ratio (/16 / /8)", "TVD"], rows))
    add("\nHHI converges by n≈1000; groups-to-50% and the bucketing "
        "reduction ratio keep growing with n and are **not comparable "
        "across snapshot sizes**.\n")

    # 3. same-code divergence -------------------------------------------
    add("\n## 3. Same codebase, different data\n")

    bm_rows = load_bitmex(day)
    newest = max(r["export_date"] for r in bm_rows)
    cutoff = (date.fromisoformat(newest)
              - timedelta(days=BITMEX_FRESH_DAYS)).isoformat()
    def _is_clearnet_host(h: str) -> bool:
        h = h.lower()
        if ".onion" in h or ".i2p" in h:
            return False
        if ":" in h and h.startswith("fc"):
            return False
        return True

    bm_hosts = {r["ip_address"].lower() for r in bm_rows
                if r["export_date"] >= cutoff
                and _is_clearnet_host(r["ip_address"])}
    only_bm = bm_hosts - btc_hosts
    only_btc = btc_hosts - bm_hosts

    # union of recent btcnodes snapshots for the windowing test
    recent = sorted(p.name[:10] for p in (DUMPS / "btcnodes").glob("*.gz")
                    if p.name[:10] <= day)[-7:]
    union7 = set()
    for d in recent:
        union7 |= load_btcnodes_hosts(d)

    add("### bitnod.es (BitMEX) vs btcnodes.io "
        "(both descend from ayeowch/bitnodes)\n")
    add(markdown_table(
        ["measure", "value"],
        [["btcnodes snapshot (one validated crawl round)",
          len(btc_hosts)],
         [f"bitmex last-seen within {BITMEX_FRESH_DAYS}d "
          f"(cut ≥ {cutoff})", len(bm_hosts)],
         ["intersection", len(bm_hosts & btc_hosts)],
         ["bitmex-only", len(only_bm)],
         ["... of which in ANY btcnodes snapshot of the last "
          f"{len(recent)} archived days",
          f"{len(only_bm & union7)} "
          f"({len(only_bm & union7) / len(only_bm):.0%})"],
         ["btcnodes-only", len(only_btc)],
         ["btcnodes hosts present in bitmex cumulative CSV (clearnet)",
          f"{len(btc_hosts & {r['ip_address'].lower() for r in bm_rows if _is_clearnet_host(r['ip_address'])}) / len(btc_hosts):.0%}"]]))
    add("\nThe divergence is dominated by snapshot semantics (single "
        "validated round vs 24h last-seen window) **plus** genuinely "
        "different crawler reach: most bitmex-only hosts never appear "
        "in a whole week of btcnodes snapshots.\n")

    ach = load_seeds_good("achow101", day)
    ff = load_seeds_good("fishfoo", day)
    add("\n### achow101 vs fish.foo (both run dnsseedrs)\n")
    add(markdown_table(
        ["measure", "value"],
        [["achow101 good clearnet", len(ach)],
         ["fish.foo good clearnet", len(ff)],
         ["Jaccard", f"{len(ach & ff) / len(ach | ff):.2f}"],
         ["achow101-only", len(ach - ff)],
         ["fish.foo-only", len(ff - ach)]]))
    add("\nTwo instances of the *same* software still disagree on "
        "roughly a third of the union: vantage point, uptime history "
        "and probe timing dominate over the codebase.\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"written {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
