"""Compare the archived crawler dumps and DNS responses across sources.

Reads the raw archives under ``data/dumps/`` and ``data/dns/`` and
regenerates every table and chart under ``analysis/output/`` from
scratch, so the outputs grow automatically as more days accumulate.

Usage:
    python3 analysis/compare_sources.py [--fetch]

``--fetch`` first downloads any release assets (dumps-YYYY-MM) missing
from ``data/dumps/`` via the GitHub CLI, so a fresh checkout can
reproduce the full analysis.

Methodology: every source defines "a node" differently, so raw totals
are not comparable. The per-source "reachable" definitions used here:

- seeds.txt dumps (achow101, fishfoo; sipa and virtu are frozen
  upstream): the seeder's own ``good`` flag.
- btcnodes.io: the snapshot itself is the reachable set of that crawl.
- bitnod.es (BitMEX): cumulative last-seen CSV; rows seen within
  BITMEX_FRESH_DAYS of the newest export date count as reachable.
- KIT dossier: keyed by anonymized hashes, no IP addresses, so KIT can
  never join IP-overlap comparisons. It carries whois/ASN on nearly all
  nodes and therefore powers the ASN view. ``lastConnect`` spreads over
  months, so counts are reported per freshness window.
- Blockchair: a small "recently active" subset, kept as a cross-check
  and excluded from coverage denominators.

Outputs (analysis/output/):
- summary.md                  all tables, links the charts
- timeseries.csv              per day and source: node counts by network
- seed_quality.csv            per day and seed: coverage and reachability
- counts_clearnet.png         reachable clearnet nodes over time
- network_composition.png     network breakdown per source, latest day
- overlap_jaccard.png         pairwise clearnet IP overlap, latest day
- dns_unique_addrs.png        unique addresses served per seed per day
- seed_coverage.png           share of served addresses in btcnodes
- seed_reachable_share.png    octavio active reachability per seed
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DUMPS_DIR = REPO / "data" / "dumps"
DNS_DIR = REPO / "data" / "dns"
OUT_DIR = REPO / "analysis" / "output"

#: Sources whose upstream dump stopped updating (see SOURCES.md). They
#: are still charted, flagged as frozen, but excluded from same-day
#: overlap and coverage comparisons.
FROZEN_SOURCES = frozenset({"sipa", "virtu"})

#: Sources too small to serve as a coverage denominator.
SUBSET_SOURCES = frozenset({"blockchair"})

#: bitnod.es rows count as reachable if last seen within this many days
#: of the newest export date in the file.
BITMEX_FRESH_DAYS = 1

#: Freshness windows (days) for KIT lastConnect counts. The 7 day
#: window doubles as KIT's "reachable" population.
KIT_WINDOWS = (1, 7, 30)
KIT_REACHABLE_WINDOW = 7

NETWORKS = ("ipv4", "ipv6", "onion", "i2p", "cjdns")
CLEARNET = ("ipv4", "ipv6")

#: Reference crawler for the seed coverage time series: the only source
#: with a true daily snapshot and history back to 2026-05-10.
COVERAGE_REFERENCE = "btcnodes"


# --------------------------------------------------------------------- model

@dataclass(frozen=True)
class SourceDay:
    """One source's archive for one day, normalized for comparison."""

    total: Counter          # all known addresses, by network
    reachable: Counter      # source-specific reachable subset, by network
    hosts: frozenset[str] = frozenset()   # reachable clearnet hosts, no port
    note: str = ""
    kit_windows: dict[int, Counter] | None = None
    kit_asns: Counter | None = None

    @property
    def clearnet_reachable(self) -> int:
        return sum(self.reachable.get(net, 0) for net in CLEARNET)


@dataclass
class SeedDay:
    """One DNS seed's responses collected during one day."""

    a_records: set[str] = field(default_factory=set)
    aaaa_records: set[str] = field(default_factory=set)
    queries: int = 0
    failures: int = 0

    @property
    def unique_addresses(self) -> int:
        return len(self.a_records | self.aaaa_records)


# ------------------------------------------------------------------- parsing

def classify_network(addr: str) -> str:
    """Classify an ``address:port`` string into a network type."""
    if ".onion:" in addr:
        return "onion"
    if ".b32.i2p:" in addr:
        return "i2p"
    if addr.startswith("["):
        # CJDNS addresses come from fc00::/8 and look like IPv6 literals.
        return "cjdns" if addr[1:3].lower() == "fc" else "ipv6"
    return "ipv4"


def host_of(addr: str) -> str:
    """Return the lowercased host part of an ``address:port`` string."""
    if addr.startswith("["):
        return addr[1 : addr.index("]")].lower()
    return addr.rsplit(":", 1)[0].lower()


def parse_seeds_txt(path: Path) -> SourceDay:
    """bitcoin-seeder dump: one line per known address with a good flag."""
    total: Counter = Counter()
    good: Counter = Counter()
    hosts: set[str] = set()
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            net = classify_network(parts[0])
            total[net] += 1
            if parts[1] == "1":
                good[net] += 1
                if net in CLEARNET:
                    hosts.add(host_of(parts[0]))
    return SourceDay(total=total, reachable=good, hosts=frozenset(hosts),
                     note="reachable = seeder's own good flag")


def parse_btcnodes(path: Path) -> SourceDay:
    """btcnodes.io snapshot: the node list is the reachable set."""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        snapshot = json.load(fh)
    counts: Counter = Counter()
    hosts: set[str] = set()
    for addr in snapshot["nodes"]:
        net = classify_network(addr)
        counts[net] += 1
        if net in CLEARNET:
            hosts.add(host_of(addr))
    return SourceDay(total=counts, reachable=counts,
                     hosts=frozenset(hosts),
                     note="snapshot = reachable set of one crawl round")


def parse_bitmex(path: Path) -> SourceDay:
    """bitnod.es CSV: cumulative last-seen list, needs a freshness cut."""
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    newest = max(row["export_date"] for row in rows)
    cutoff = (date.fromisoformat(newest)
              - timedelta(days=BITMEX_FRESH_DAYS)).isoformat()
    total: Counter = Counter()
    fresh: Counter = Counter()
    hosts: set[str] = set()
    for row in rows:
        host = row["ip_address"].lower()
        net = "ipv6" if ":" in host else "ipv4"
        total[net] += 1
        if row["export_date"] >= cutoff:
            fresh[net] += 1
            hosts.add(host)
    return SourceDay(total=total, reachable=fresh, hosts=frozenset(hosts),
                     note=f"reachable = last seen on or after {cutoff}")


def parse_blockchair(path: Path) -> SourceDay:
    """Blockchair nodes API: a small recently-active subset."""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        payload = json.load(fh)
    counts: Counter = Counter()
    hosts: set[str] = set()
    for addr in payload.get("data", {}).get("nodes", {}):
        host = host_of(addr)
        net = "ipv6" if ":" in host else "ipv4"
        counts[net] += 1
        hosts.add(host)
    return SourceDay(total=counts, reachable=counts,
                     hosts=frozenset(hosts),
                     note="recently-active subset, cross-check only")


def parse_kit(path: Path) -> SourceDay:
    """KIT dossier: anonymized hashes, no IPs; counts and ASN only."""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        dossier = json.load(fh)
    file_day = datetime.strptime(path.name[:10], "%Y-%m-%d")
    total: Counter = Counter()
    windows: dict[int, Counter] = {w: Counter() for w in KIT_WINDOWS}
    asns: Counter = Counter()
    for node in dossier.values():
        net = "ipv4" if node.get("ip", {}).get("version") == 4 else "ipv6"
        total[net] += 1
        last_connect = node.get("lastConnect")
        if last_connect:
            age_days = (file_day - datetime.fromisoformat(last_connect)).days
            for window in KIT_WINDOWS:
                if age_days <= window:
                    windows[window][net] += 1
        asn = (node.get("whois") or {}).get("asn")
        if asn:
            asns[asn] += 1
    return SourceDay(
        total=total, reachable=windows[KIT_REACHABLE_WINDOW],
        note=f"no IPs in dossier; reachable = lastConnect within "
             f"{KIT_REACHABLE_WINDOW}d",
        kit_windows=windows, kit_asns=asns)


PARSERS: dict[str, Callable[[Path], SourceDay]] = {
    "achow101": parse_seeds_txt,
    "fishfoo": parse_seeds_txt,
    "sipa": parse_seeds_txt,
    "virtu": parse_seeds_txt,
    "btcnodes": parse_btcnodes,
    "bitmex": parse_bitmex,
    "blockchair": parse_blockchair,
    "kit": parse_kit,
}


# ------------------------------------------------------------------- loading

def fetch_releases() -> None:
    """Download release assets missing locally into data/dumps/."""
    try:
        tags = subprocess.run(
            ["gh", "release", "list", "--json", "tagName",
             "--jq", ".[].tagName"],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout.split()
    except FileNotFoundError:
        sys.exit("--fetch requires the GitHub CLI (gh) on PATH")
    cache = REPO / "analysis" / ".release-cache"
    for tag in tags:
        if not tag.startswith("dumps-"):
            continue
        tag_dir = cache / tag
        tag_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["gh", "release", "download", tag, "--dir", str(tag_dir),
             "--skip-existing"],
            cwd=REPO, check=True)
        for asset in tag_dir.iterdir():
            source, _, filename = asset.name.partition("-")
            if source not in PARSERS and source != "octavio":
                continue
            target = DUMPS_DIR / source / filename
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(asset.read_bytes())
    print("release assets synced into data/dumps/")


def load_dumps() -> dict[str, dict[str, SourceDay]]:
    """Parse every archived dump. Returns source -> day -> SourceDay."""
    dumps: dict[str, dict[str, SourceDay]] = {}
    for source, parser in PARSERS.items():
        source_dir = DUMPS_DIR / source
        if not source_dir.is_dir():
            continue
        by_day: dict[str, SourceDay] = {}
        for path in sorted(source_dir.glob("*.gz")):
            day = path.name[:10]
            try:
                by_day[day] = parser(path)
            except Exception as exc:  # noqa: BLE001 - skip corrupt archives
                print(f"warning: skipping {source} {day}: {exc}",
                      file=sys.stderr)
        if by_day:
            dumps[source] = by_day
    return dumps


def load_dns() -> dict[str, dict[str, SeedDay]]:
    """Parse the DNS response log. Returns day -> seed -> SeedDay.

    The current UTC day is skipped: its collection runs are still in
    progress, so per-day aggregates would be misleadingly low.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    days: dict[str, dict[str, SeedDay]] = {}
    for path in sorted(DNS_DIR.glob("*.jsonl")):
        if path.stem >= today:
            continue
        per_seed: dict[str, SeedDay] = defaultdict(SeedDay)
        for line in path.open(encoding="utf-8"):
            entry = json.loads(line)
            seed_day = per_seed[entry["seed"]]
            seed_day.queries += 1
            if entry["status"] == "NOERROR" and entry["records"]:
                records = {r.lower() for r in entry["records"]}
                if entry["qtype"] == "A":
                    seed_day.a_records |= records
                else:
                    seed_day.aaaa_records |= records
            elif entry["status"] not in ("NOERROR", "NXDOMAIN"):
                seed_day.failures += 1
        days[path.stem] = dict(per_seed)
    return days


def load_octavio() -> dict[str, dict[str, float]]:
    """Octavio's active per-seed reachability. Returns day -> seed -> share.

    Every API response carries the monitor's full history, so only the
    newest archived file is read. Multiple measurements per day are
    resolved to the last one.
    """
    files = sorted((DUMPS_DIR / "octavio").glob("*.json.gz"))
    if not files:
        return {}
    with gzip.open(files[-1], "rt", encoding="utf-8") as fh:
        history = json.load(fh)
    days: dict[str, dict[str, float]] = defaultdict(dict)
    for measurement in history:
        day = measurement["timestamp"][:10]
        for seed in measurement["seeds"]:
            if seed["advertised"]:
                days[day][seed["seed_hostname"]] = (
                    seed["reachable"] / seed["advertised"])
    return dict(days)


# ------------------------------------------------------------------ analysis

def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def hhi(counts: Counter) -> float:
    """Herfindahl-Hirschman index of a count distribution (0..1)."""
    total = sum(counts.values())
    if not total:
        return 0.0
    return sum((n / total) ** 2 for n in counts.values())


def short_seed_name(seed: str) -> str:
    for prefix in ("seed.bitcoin.", "seed.mainnet.", "seed.btc.",
                   "dnsseed.bitcoin.", "dnsseed.", "seed."):
        if seed.startswith(prefix):
            return seed[len(prefix):]
    return seed


def latest_day(dumps: dict[str, dict[str, SourceDay]]) -> dict[str, str]:
    return {source: max(by_day) for source, by_day in dumps.items()}


def comparable_sources(dumps: dict[str, dict[str, SourceDay]],
                       latest: dict[str, str]) -> list[str]:
    """Sources usable for same-day overlap and coverage comparisons."""
    return [source for source in sorted(dumps)
            if source not in FROZEN_SOURCES
            and source not in SUBSET_SOURCES
            and dumps[source][latest[source]].hosts]


def coverage(addresses: set[str], hosts: frozenset[str]) -> float | None:
    """Share of served addresses present in a crawler's reachable set."""
    if not addresses:
        return None
    return len(addresses & hosts) / len(addresses)


# ----------------------------------------------------------------- reporting

def markdown_table(headers: Sequence[str],
                   rows: Iterable[Sequence[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |"
              for row in rows]
    return "\n".join(lines) + "\n"


def write_timeseries_csv(dumps: dict[str, dict[str, SourceDay]]) -> None:
    fieldnames = ["date", "source", "total", "reachable",
                  *(f"reachable_{net}" for net in NETWORKS)]
    with (OUT_DIR / "timeseries.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for source in sorted(dumps):
            for day, sd in sorted(dumps[source].items()):
                writer.writerow({
                    "date": day, "source": source,
                    "total": sum(sd.total.values()),
                    "reachable": sum(sd.reachable.values()),
                    **{f"reachable_{net}": sd.reachable.get(net, 0)
                       for net in NETWORKS}})


def write_seed_quality_csv(dns_days: dict[str, dict[str, SeedDay]],
                           dumps: dict[str, dict[str, SourceDay]],
                           octavio: dict[str, dict[str, float]]) -> None:
    reference = dumps.get(COVERAGE_REFERENCE, {})
    with (OUT_DIR / "seed_quality.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "seed", "unique_a_records",
                         f"coverage_{COVERAGE_REFERENCE}",
                         "octavio_reachable_share"])
        days = sorted(set(dns_days) | set(octavio))
        for day in days:
            seeds = (set(dns_days.get(day, {}))
                     | set(octavio.get(day, {})))
            for seed in sorted(seeds):
                seed_day = dns_days.get(day, {}).get(seed)
                cov = None
                if seed_day and day in reference:
                    cov = coverage(seed_day.a_records,
                                   reference[day].hosts)
                octavio_share = octavio.get(day, {}).get(seed)
                writer.writerow([
                    day, seed,
                    seed_day.unique_addresses if seed_day else "",
                    f"{cov:.3f}" if cov is not None else "",
                    f"{octavio_share:.3f}"
                    if octavio_share is not None else ""])


def build_summary(dumps: dict[str, dict[str, SourceDay]],
                  latest: dict[str, str],
                  dns_days: dict[str, dict[str, SeedDay]],
                  octavio: dict[str, dict[str, float]]) -> str:
    parts: list[str] = []
    add = parts.append
    now = datetime.now(timezone.utc)
    add("# Source comparison summary\n")
    add(f"Generated {now:%Y-%m-%d %H:%M} UTC by "
        "`analysis/compare_sources.py`. Every table and chart is rebuilt "
        "from the raw archives on each run.\n")

    # Population sizes, latest day per source.
    add("## Population sizes (latest day per source)\n")
    add("Each source defines reachable differently; the note column "
        "states the definition used.\n")
    rows = []
    for source in sorted(dumps):
        day = latest[source]
        sd = dumps[source][day]
        note = sd.note + (", frozen upstream"
                          if source in FROZEN_SOURCES else "")
        rows.append([source, day, sum(sd.total.values()),
                     sum(sd.reachable.values()),
                     *(sd.reachable.get(net, 0) for net in NETWORKS),
                     note])
    add(markdown_table(
        ["source", "day", "known total", "reachable", *NETWORKS, "note"],
        rows))

    # KIT freshness windows and ASN concentration.
    if "kit" in latest:
        kit = dumps["kit"][latest["kit"]]
        add("\n## KIT dossier freshness windows\n")
        add("The dossier accumulates nodes over months, so a raw count "
            "is not a same-day population.\n")
        assert kit.kit_windows is not None and kit.kit_asns is not None
        window_rows = [[f"lastConnect within {w}d",
                        c.get("ipv4", 0), c.get("ipv6", 0),
                        sum(c.values())]
                       for w, c in sorted(kit.kit_windows.items())]
        window_rows.append(["all", kit.total.get("ipv4", 0),
                            kit.total.get("ipv6", 0),
                            sum(kit.total.values())])
        add(markdown_table(["window", "ipv4", "ipv6", "total"],
                           window_rows))

        asns = kit.kit_asns
        asn_total = sum(asns.values())
        cr5 = (sum(n for _, n in asns.most_common(5)) / asn_total
               if asn_total else 0.0)
        add("\n## KIT ASN view (only source with per-node ASN)\n")
        add(f"Nodes with ASN: {asn_total} of {sum(kit.total.values())}. "
            f"Unique ASes: {len(asns)}. "
            f"HHI: {hhi(asns):.4f}. CR5: {cr5:.1%}.\n")
        add(markdown_table(
            ["rank", "ASN", "nodes", "share"],
            [[rank, f"AS{asn}", count, f"{count / asn_total:.1%}"]
             for rank, (asn, count) in enumerate(asns.most_common(10), 1)]))

    # Pairwise clearnet IP overlap.
    overlap_sources = comparable_sources(dumps, latest)
    if len(overlap_sources) >= 2:
        add("\n## Pairwise clearnet IP overlap (latest day)\n")
        add("Hosts only, ports stripped. KIT cannot participate because "
            "the dossier carries no IPs; frozen and subset sources are "
            "excluded.\n")
        rows = []
        for i, a in enumerate(overlap_sources):
            for b in overlap_sources[i + 1:]:
                sa = dumps[a][latest[a]].hosts
                sb = dumps[b][latest[b]].hosts
                inter = len(sa & sb)
                rows.append([a, b, len(sa), len(sb), inter,
                             f"{jaccard(sa, sb):.3f}",
                             f"{inter / len(sa):.1%}",
                             f"{inter / len(sb):.1%}"])
        add(markdown_table(
            ["A", "B", "size A", "size B", "intersection", "Jaccard",
             "share of A", "share of B"], rows))

    # Seed quality: coverage in crawler views plus active reachability.
    if dns_days:
        dns_latest = max(dns_days)
        octavio_latest = max(octavio) if octavio else None
        add(f"\n## DNS seed quality ({dns_latest})\n")
        add("Coverage: share of the IPv4 addresses a seed served that "
            "appear in each crawler's reachable set. Octavio: "
            "independent active reachability measurement "
            "(octavio.xyz DNS seed monitor)"
            + (f", {octavio_latest}" if octavio_latest else "")
            + ". Low values indicate a seed serving stale addresses.\n")
        rows = []
        for seed, seed_day in sorted(dns_days[dns_latest].items()):
            cells: list[object] = [short_seed_name(seed),
                                   len(seed_day.a_records)]
            for source in overlap_sources:
                cov = coverage(seed_day.a_records,
                               dumps[source][latest[source]].hosts)
                cells.append(f"{cov:.0%}" if cov is not None else "-")
            share = (octavio.get(octavio_latest, {}).get(seed)
                     if octavio_latest else None)
            cells.append(f"{share:.0%}" if share is not None else "-")
            rows.append(cells)
        add(markdown_table(
            ["seed", "unique A", *overlap_sources, "octavio"], rows))

        failures = {short_seed_name(seed): sd.failures
                    for seed, sd in dns_days[dns_latest].items()
                    if sd.failures}
        add("\nQuery failures on that day: "
            + (", ".join(f"{s}: {n}" for s, n in sorted(failures.items()))
               or "none") + "\n")

    add("\n## Charts\n")
    for name in ("counts_clearnet", "network_composition",
                 "overlap_jaccard", "dns_unique_addrs",
                 "seed_coverage", "seed_reachable_share"):
        add(f"![{name}]({name}.png)\n")
    return "\n".join(parts)


# -------------------------------------------------------------------- charts

def render_charts(dumps: dict[str, dict[str, SourceDay]],
                  latest: dict[str, str],
                  dns_days: dict[str, dict[str, SeedDay]],
                  octavio: dict[str, dict[str, float]]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    def new_figure(title: str, ylabel: str):
        fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
        return fig, ax

    def save(fig, name: str) -> None:
        fig.savefig(OUT_DIR / f"{name}.png", dpi=150)
        plt.close(fig)

    def as_dates(days: Iterable[str]) -> list[datetime]:
        return [datetime.strptime(d, "%Y-%m-%d") for d in days]

    def format_date_axis(ax) -> None:
        locator = mdates.AutoDateLocator(interval_multiples=True)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    # 1. Reachable clearnet nodes over time.
    fig, ax = new_figure("Reachable clearnet nodes per source",
                         "nodes (IPv4 + IPv6)")
    for source in sorted(dumps):
        if source in SUBSET_SOURCES:
            continue  # a 300-node subset would flatten the scale
        days = sorted(dumps[source])
        counts = [dumps[source][d].clearnet_reachable for d in days]
        frozen = source in FROZEN_SOURCES
        ax.plot(as_dates(days), counts, marker="o", markersize=3,
                label=source + (" (frozen)" if frozen else ""),
                linestyle="--" if frozen else "-",
                alpha=0.5 if frozen else 1.0)
    ax.legend()
    format_date_axis(ax)
    save(fig, "counts_clearnet")

    # 2. Network composition per source, latest day.
    fig, ax = new_figure("Reachable nodes by network (latest day per source)",
                         "nodes")
    sources = sorted(dumps)
    bottoms = [0.0] * len(sources)
    for net in NETWORKS:
        values = [dumps[s][latest[s]].reachable.get(net, 0)
                  for s in sources]
        ax.bar(sources, values, bottom=bottoms, label=net)
        bottoms = [b + v for b, v in zip(bottoms, values)]
    ax.legend()
    save(fig, "network_composition")

    # 3. Pairwise clearnet IP overlap heatmap, latest day.
    overlap_sources = comparable_sources(dumps, latest)
    if len(overlap_sources) >= 2:
        n = len(overlap_sources)
        matrix = [[jaccard(dumps[a][latest[a]].hosts,
                           dumps[b][latest[b]].hosts)
                   for b in overlap_sources] for a in overlap_sources]
        fig, ax = plt.subplots(figsize=(1.4 * n + 2, 1.2 * n + 1.5),
                               layout="constrained")
        image = ax.imshow(matrix, vmin=0, vmax=1, cmap="viridis")
        ax.set_xticks(range(n), overlap_sources, rotation=30, ha="right")
        ax.set_yticks(range(n), overlap_sources)
        for i in range(n):
            for j in range(n):
                ax.text(j, i, f"{matrix[i][j]:.2f}", ha="center",
                        va="center",
                        color="white" if matrix[i][j] < 0.6 else "black")
        ax.set_title("Clearnet IP overlap (Jaccard), latest day\n"
                     "KIT absent: dossier has no IPs")
        fig.colorbar(image, shrink=0.8)
        save(fig, "overlap_jaccard")

    # 4. Unique addresses served per DNS seed per day.
    fig, ax = new_figure("Unique addresses served per DNS seed per day\n"
                         "lower bound: sampled every 6h, 3 repeats",
                         "unique A+AAAA records")
    seeds = sorted({seed for day in dns_days.values() for seed in day})
    for seed in seeds:
        days = [d for d in sorted(dns_days) if seed in dns_days[d]]
        ax.plot(as_dates(days),
                [dns_days[d][seed].unique_addresses for d in days],
                marker="o", markersize=3, label=short_seed_name(seed))
    ax.legend(fontsize=8)
    format_date_axis(ax)
    save(fig, "dns_unique_addrs")

    # 5. Seed coverage: share of served A records in the reference
    #    crawler's reachable set, per day.
    reference = dumps.get(COVERAGE_REFERENCE, {})
    common_days = [d for d in sorted(dns_days) if d in reference]
    if common_days:
        fig, ax = new_figure(
            f"Share of seed-served IPv4 addresses found reachable by "
            f"{COVERAGE_REFERENCE}", "coverage")
        for seed in seeds:
            points = [
                (d, coverage(dns_days[d][seed].a_records,
                             reference[d].hosts))
                for d in common_days if seed in dns_days[d]]
            points = [(d, c) for d, c in points if c is not None]
            if points:
                ax.plot(as_dates(d for d, _ in points),
                        [c for _, c in points], marker="o", markersize=3,
                        label=short_seed_name(seed))
        ax.set_ylim(0, 1.05)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
        ax.legend(fontsize=8)
        format_date_axis(ax)
        save(fig, "seed_coverage")

    # 6. Octavio's active reachability per seed over its full history.
    if octavio:
        fig, ax = new_figure(
            "Active reachability per DNS seed\n"
            "source: octavio.xyz DNS seed monitor", "reachable share")
        octavio_seeds = sorted({s for day in octavio.values() for s in day})
        for seed in octavio_seeds:
            days = [d for d in sorted(octavio) if seed in octavio[d]]
            ax.plot(as_dates(days), [octavio[d][seed] for d in days],
                    marker="o", markersize=2, linewidth=1,
                    label=short_seed_name(seed))
        ax.set_ylim(0, 1.05)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
        ax.legend(fontsize=7)
        format_date_axis(ax)
        save(fig, "seed_reachable_share")


# ---------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild all comparison tables and charts from the "
                    "raw archives.")
    parser.add_argument("--fetch", action="store_true",
                        help="download missing release assets first "
                             "(requires the GitHub CLI)")
    if parser.parse_args().fetch:
        fetch_releases()

    dumps = load_dumps()
    if not dumps:
        print("no dump files under data/dumps/; run with --fetch or run "
              "collector/collect_dumps.py first", file=sys.stderr)
        return 1
    latest = latest_day(dumps)
    dns_days = load_dns()
    octavio = load_octavio()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_timeseries_csv(dumps)
    write_seed_quality_csv(dns_days, dumps, octavio)
    render_charts(dumps, latest, dns_days, octavio)
    (OUT_DIR / "summary.md").write_text(
        build_summary(dumps, latest, dns_days, octavio), encoding="utf-8")

    print(f"outputs written to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
