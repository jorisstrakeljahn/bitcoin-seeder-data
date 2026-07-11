# bitcoin-seeder-data

A longitudinal archive of Bitcoin DNS seeder and network crawler data, collected automatically via GitHub Actions. It is the foundation for a comparative analysis of the sources the network relies on for bootstrapping: what each seeder and crawler actually serves, how they differ, and which one deserves to be called ground truth.

## What is collected

**Layer A: DNS responses** (`data/dns/`, every 6 hours). What a bootstrapping node actually sees. Each mainnet seed from Bitcoin Core's `chainparams.cpp` plus one community seeder is queried for A and AAAA records on all supported service-bit subdomains, three times per run. One JSON line per query, including failures; a dead seed is a data point, not an error.

**Layer B: crawler dumps** (daily). The full network view published by seeder and crawler operators, including all three sources Core's `makeseeds.py` uses for fixed-seed generation. The files are large, so they are uploaded unmodified to a monthly GitHub release (`dumps-YYYY-MM`) instead of git. `data/dumps/manifest.jsonl` records URL, size and SHA-256 for every download, so each asset stays verifiable.

Current sources: the seeds.txt dumps of sipa, achow101, virtu and fish.foo, the BitMEX node CSV, btcnodes.io snapshots, KIT DSN research dossiers, the Blockchair nodes API and the octavio.xyz seed monitor. Full table with operators, formats and caveats: [SOURCES.md](SOURCES.md).

## Analysis

`analysis/compare_sources.py` normalizes every source to a comparable view and rebuilds all tables and charts in `analysis/output/` from the raw archives on each run, so everything grows automatically as more days accumulate. It covers population sizes per network, pairwise IP overlap, ASN concentration (HHI, CR5) from the KIT data, and a DNS seed quality view that cross-checks the addresses each seed serves against independent crawler and reachability measurements.

```
python3 -m venv .venv && .venv/bin/pip install -r analysis/requirements.txt
.venv/bin/python analysis/compare_sources.py --fetch
```

`--fetch` pulls missing release assets via the GitHub CLI, so a fresh checkout reproduces the full analysis. Results land in `analysis/output/summary.md`.

## Collecting manually

```
python3 collector/collect_dns.py    # requires dig
python3 collector/collect_dumps.py
```

Both collectors are Python stdlib only, idempotent per day and append-only. Source configuration lives in `collector/seeds.py`.

## Caveats

- Collection started 2026-07-07; btcnodes is backfilled to 2026-05-10 and KIT keeps its own history online back to 2015.
- DNS responses are sampled from a single vantage point (GitHub Actions runners in US datacenters), so per-seed address counts are lower bounds and GeoDNS effects are invisible.
- Operators refresh their dumps on their own schedules; identical fetches are detectable via the manifest checksums.
- The sipa and virtu dumps are frozen upstream (details in SOURCES.md); both DNS seeds themselves remain live.
