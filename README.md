# bitcoin-seeder-data

Longitudinal archive of Bitcoin DNS seeder data, collected automatically via
GitHub Actions. Foundation for a comparative analysis of the active Bitcoin
DNS seeders and network crawlers (what data they serve, how they differ, and
which source is best suited as ground truth for ASMap validation).

## What is collected

### Layer A — DNS responses (`data/dns/`)

What a bootstrapping node actually sees. Every 6 hours (cron `17 */6 * * *`),
each mainnet DNS seed from Bitcoin Core's `src/kernel/chainparams.cpp` is
queried via `dig` for A and AAAA records — the plain hostname plus the
service-bit subdomains the seed supports (`x1`, `x5`, `x9`, `xd`, …). Since
each response is a random subset (~25 addresses) of the seeder's pool, every
hostname/qtype pair is queried 3 times per run.

Format: one JSON object per query, appended to `data/dns/YYYY-MM-DD.jsonl`
(UTC):

```json
{"seed":"seed.bitcoin.sipa.be","ts":"2026-07-07T16:00:12+00:00","hostname":"x9.seed.bitcoin.sipa.be","qtype":"A","status":"NOERROR","ttl":60,"records":["203.0.113.5","..."]}
```

Failed queries and NXDOMAIN responses are recorded as well — a seed being
down or a subdomain being unsupported is itself a data point.

Seeds collected (mirrors chainparams.cpp, checked 2026-07-07):

| Seed | Operator | Software |
|---|---|---|
| seed.bitcoin.sipa.be | Pieter Wuille | sipa/bitcoin-seeder |
| dnsseed.bluematt.me | Matt Corallo | TheBlueMatt/dnsseed |
| seed.bitcoin.jonasschnelli.ch | Jonas Schnelli | sipa fork |
| seed.btc.petertodd.net | Peter Todd | sipa fork |
| seed.bitcoin.sprovoost.nl | Sjors Provoost | sipa fork |
| dnsseed.emzy.de | Stephan Oeste | sipa fork |
| seed.bitcoin.wiz.biz | Jason Maurice | wiz/dnsseed-rust |
| seed.mainnet.achownodes.xyz | Ava Chow | achow101/dnsseedrs |

### Layer B — Full crawler dumps (`data/dumps/`)

The complete crawler view published by three seeder operators — the same
sources Bitcoin Core's `contrib/seeds/makeseeds.py` uses for fixed-seed
generation. Downloaded once per day (cron `43 5 * * *`).

The dumps are large (~40 MB/day total), so they are **not committed to
git**. The workflow uploads them unmodified as assets to a monthly GitHub
release (`dumps-YYYY-MM`, asset name `<source>-YYYY-MM-DD.txt.gz`). Only
`data/dumps/manifest.jsonl` is tracked in git; it records URL, size,
SHA-256 and HTTP status for every download (including failures), so each
release asset can be verified against the manifest. Manual runs keep the
files locally under `data/dumps/<source>/` (gitignored).

Sources:

| Source | URL |
|---|---|
| sipa | https://bitcoin.sipa.be/seeds.txt.gz |
| achow101 | https://mainnet.achownodes.xyz/seeds.txt.gz |
| virtu | https://21.ninja/seeds.txt.gz |

Dump format (bitcoin-seeder `dnsseed.dump`): one node per line with address,
good flag, lastSuccess timestamp, uptime over five windows (2h/8h/1d/7d/30d),
block height, service flags, protocol version and user agent.

Additionally, the Blockchair nodes API (`api.blockchair.com/bitcoin/nodes`)
is archived daily the same way (`blockchair-YYYY-MM-DD.json.gz`).

## Known limitations

- DNS responses depend on the resolver location of the GitHub Actions
  runner (US datacenters); anycast or GeoDNS behavior of individual seeds
  is not distinguishable from a single vantage point.
- The 6-hour sampling of DNS responses under-samples the seeder pools;
  counts of unique addresses per seed are lower bounds, not pool sizes.
- Crawler dumps are refreshed by their operators on their own schedules;
  a daily download may fetch an identical or a many-hours-old file. The
  manifest SHA-256 makes identical fetches detectable.
- Collection start: 2026-07-07. No backfill exists for earlier dates.

## Running manually

```
python3 collector/collect_dns.py    # requires dig
python3 collector/collect_dumps.py
```

Both scripts are Python stdlib only, idempotent per day, and append-only.
Source configuration (seed list, URLs) lives in `collector/seeds.py`.
