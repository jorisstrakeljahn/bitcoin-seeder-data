"""Historical addrman metrics from bitcoin-data/getrawaddrman snapshots.

The upstream dataset (https://github.com/bitcoin-data/getrawaddrman, maintained
by 0xB10C) stores daily ``getrawaddrman`` RPC exports of the two
demo.peer.observer nodes ``hal`` and ``len`` by replacing two JSON files in
git. This script reads every historical version directly with ``git show``
and computes two metrics for the *new* table, using nothing but the snapshots
themselves (they contain no connection outcomes, so none of this is a
reachability measurement):

1. Timestamp freshness: share of new-table entries whose gossip timestamp is
   less than 7 days old at snapshot time. The timestamp is supplied through
   address gossip and does not prove a live node.
2. Daily endpoint turnover: share of today's unique (network, host, port)
   endpoints that were not present in the previous snapshot, divided by the
   number of elapsed days. Over multi-day snapshot gaps this is a linear
   average and underestimates true per-day churn.

It also tracks cohort survival: how many of the new-table endpoints present
on a reference day are still present in later snapshots.

Known dataset caveats:
- No snapshots Feb 15 - Mar 3 (hal until Mar 11), and len misses Jul 14-17.
- On May 29 and Jul 1 both nodes lost and refilled 1-3k slots within days
  (restart-like events); the turnover spikes on those days are artifacts.

Outputs (analysis/output/): addrman_history.csv, addrman_cohort_survival.csv,
addrman_freshness_vs_churn.png, addrman_cohort_survival.png.

Usage:
    python analysis/addrman_history.py --addrman-repo ../getrawaddrman
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "analysis" / "output"

NODES = ("hal", "len")
FILES = {node: f"getrawaddrman-{node}.json" for node in NODES}
FLOOD_START = date(2026, 4, 10)
UNSOLICITED_DROP = date(2026, 7, 15)
COHORT_DAYS = (
    date(2026, 2, 8),
    date(2026, 4, 15),
    date(2026, 6, 1),
    date(2026, 7, 14),
)
COHORT_COLORS = ("#4c72b0", "#d45a3a", "#e7a23d", "#16856b")

Endpoint = tuple[str, str, int]


@dataclass(frozen=True)
class SnapshotRef:
    commit: str
    timestamp: datetime


def run_git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=text)


def daily_versions(repo: Path, filename: str) -> dict[date, SnapshotRef]:
    """Return the last version of a file committed on each UTC day."""
    output = run_git(repo, "log", "--format=%H%x09%aI", "--", filename)
    by_day: dict[date, SnapshotRef] = {}
    for line in str(output).splitlines():
        commit, timestamp_raw = line.split("\t", 1)
        timestamp = datetime.fromisoformat(timestamp_raw).astimezone(timezone.utc)
        day = timestamp.date()
        current = by_day.get(day)
        if current is None or timestamp > current.timestamp:
            by_day[day] = SnapshotRef(commit=commit, timestamp=timestamp)
    return by_day


def normalize_host(host: str) -> str:
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return host.lower()


def load_new_table(repo: Path, ref: SnapshotRef, filename: str) -> list[dict]:
    raw = run_git(repo, "show", f"{ref.commit}:{filename}", text=False)
    return list(json.loads(raw)["new"].values())


def new_table_metrics(
    rows: list[dict], snapshot_timestamp: datetime
) -> tuple[set[Endpoint], float]:
    endpoints = {
        (row["network"], normalize_host(row["address"]), int(row["port"]))
        for row in rows
    }
    now = snapshot_timestamp.timestamp()
    ages = [max(0.0, now - int(row["time"])) for row in rows if int(row.get("time", 0)) > 0]
    fresh_7d_share = sum(age <= 7 * 86400 for age in ages) / len(ages)
    return endpoints, fresh_7d_share


def write_csv(name: str, rows: list[dict[str, object]]) -> None:
    with open(OUT / name, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def mark_events(ax: plt.Axes) -> None:
    ax.axvline(FLOOD_START, color="#d45a3a", linestyle="--", linewidth=1)
    ax.axvline(UNSOLICITED_DROP, color="#555555", linestyle=":", linewidth=1)


def plot_freshness_vs_churn(rows: list[dict[str, object]]) -> None:
    by_day: dict[date, list[dict[str, object]]] = {}
    for row in rows:
        by_day.setdefault(date.fromisoformat(str(row["day"])), []).append(row)

    fresh_days, freshness = [], []
    churn_days, churn = [], []
    for day, day_rows in sorted(by_day.items()):
        fresh_days.append(day)
        freshness.append(
            sum(float(row["new_fresh_7d_share"]) for row in day_rows)
            / len(day_rows) * 100
        )
        churn_values = [
            float(row["new_influx_per_day"])
            for row in day_rows
            if row["new_influx_per_day"] != ""
        ]
        if churn_values:
            churn_days.append(day)
            churn.append(sum(churn_values) / len(churn_values) * 100)

    fig, (ax_fresh, ax_churn) = plt.subplots(2, 1, figsize=(10, 6.8), sharex=True)
    ax_fresh.plot(fresh_days, freshness, color="#d45a3a", linewidth=2.0)
    ax_fresh.set_ylabel("new entries <7 days old")
    ax_fresh.yaxis.set_major_formatter(PercentFormatter())
    ax_fresh.set_title(
        "Direct addrman measurements: gossip-timestamp freshness and daily turnover"
    )
    ax_churn.plot(churn_days, churn, color="#4c72b0", linewidth=2.0)
    ax_churn.set_ylabel("new endpoints replaced per day")
    ax_churn.yaxis.set_major_formatter(PercentFormatter())
    ax_churn.set_xlabel("snapshot date (UTC)")
    for ax in (ax_fresh, ax_churn):
        mark_events(ax)
        ax.grid(alpha=0.25)
    ax_fresh.text(
        FLOOD_START, 0.04, " 10 Apr: observed flood starts",
        transform=ax_fresh.get_xaxis_transform(),
        rotation=90, va="bottom", ha="right", fontsize=8, color="#983921",
    )
    ax_fresh.text(
        UNSOLICITED_DROP, 0.04, " 15 Jul: KIT volume drops",
        transform=ax_fresh.get_xaxis_transform(),
        rotation=90, va="bottom", ha="right", fontsize=8, color="#555555",
    )
    ax_churn.text(
        0.01, 0.92,
        "Mean across hal and len; computed from the snapshots alone. "
        "Turnover spikes on May 29 / Jul 1 are restart-like events.",
        transform=ax_churn.transAxes, fontsize=8.5, va="top",
        bbox={"facecolor": "white", "alpha": 0.88, "edgecolor": "#cccccc"},
    )
    ax_churn.xaxis.set_major_locator(mdates.MonthLocator())
    ax_churn.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.tight_layout()
    fig.savefig(OUT / "addrman_freshness_vs_churn.png", dpi=180)
    plt.close(fig)


def plot_cohort_survival(cohort_rows: list[dict[str, object]]) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.2))
    for cohort_day, color in zip(COHORT_DAYS, COHORT_COLORS):
        by_day: dict[date, list[float]] = {}
        nodes_seen: set[str] = set()
        for row in cohort_rows:
            if str(row["cohort_day"]) != cohort_day.isoformat():
                continue
            nodes_seen.add(str(row["node"]))
            by_day.setdefault(
                date.fromisoformat(str(row["day"])), []
            ).append(float(row["survival_share"]))
        days = sorted(by_day)
        shares = [sum(by_day[day]) / len(by_day[day]) * 100 for day in days]
        label = f"new entries present on {cohort_day.isoformat()}"
        if nodes_seen != set(NODES):
            label += f" ({'/'.join(sorted(nodes_seen))} only)"
        ax.plot(days, shares, color=color, linewidth=2.0, label=label)
    mark_events(ax)
    ax.set_ylim(0, 102)
    ax.yaxis.set_major_formatter(PercentFormatter())
    ax.set_ylabel("still present in new table")
    ax.set_xlabel("snapshot date (UTC)")
    ax.set_title("Survival of new-table cohorts (mean across available nodes)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.25)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.tight_layout()
    fig.savefig(OUT / "addrman_cohort_survival.png", dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--addrman-repo",
        type=Path,
        default=REPO.parent / "getrawaddrman",
        help="local clone of bitcoin-data/getrawaddrman",
    )
    args = parser.parse_args()
    addrman_repo = args.addrman_repo.resolve()
    if not (addrman_repo / ".git").exists():
        raise SystemExit(f"not a git clone: {addrman_repo}")

    OUT.mkdir(parents=True, exist_ok=True)
    versions = {node: daily_versions(addrman_repo, FILES[node]) for node in NODES}
    all_days = sorted(set().union(*(set(node_days) for node_days in versions.values())))

    history_rows: list[dict[str, object]] = []
    cohort_rows: list[dict[str, object]] = []
    previous_new: dict[str, tuple[date, set[Endpoint]]] = {}
    cohort_sets: dict[tuple[str, date], set[Endpoint]] = {}
    for index, day in enumerate(all_days, 1):
        for node in NODES:
            ref = versions[node].get(day)
            if ref is None:
                continue
            rows = load_new_table(addrman_repo, ref, FILES[node])
            endpoints, fresh_7d_share = new_table_metrics(rows, ref.timestamp)
            row: dict[str, object] = {
                "day": day.isoformat(),
                "timestamp": ref.timestamp.isoformat(),
                "node": node,
                "commit": ref.commit,
                "new_slots": len(rows),
                "new_unique_endpoints": len(endpoints),
                "new_fresh_7d_share": fresh_7d_share,
            }

            prev = previous_new.get(node)
            if prev is not None:
                prev_day, prev_endpoints = prev
                elapsed = max(1, (day - prev_day).days)
                influx = len(endpoints - prev_endpoints) / len(endpoints)
                row["new_influx_per_day"] = influx / elapsed
            else:
                row["new_influx_per_day"] = ""
            previous_new[node] = (day, endpoints)

            if day in COHORT_DAYS:
                cohort_sets[(node, day)] = endpoints
            for cohort_day in COHORT_DAYS:
                cohort = cohort_sets.get((node, cohort_day))
                if cohort is not None and day >= cohort_day:
                    cohort_rows.append({
                        "node": node,
                        "cohort_day": cohort_day.isoformat(),
                        "day": day.isoformat(),
                        "survival_share": len(endpoints & cohort) / len(cohort),
                    })
            history_rows.append(row)
        print(f"[{index}/{len(all_days)}] {day}")

    write_csv("addrman_history.csv", history_rows)
    write_csv("addrman_cohort_survival.csv", cohort_rows)
    plot_freshness_vs_churn(history_rows)
    plot_cohort_survival(cohort_rows)
    for name in (
        "addrman_history.csv",
        "addrman_cohort_survival.csv",
        "addrman_freshness_vs_churn.png",
        "addrman_cohort_survival.png",
    ):
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
