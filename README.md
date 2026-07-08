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

Seeds collected: the eight mainnet seeds from chainparams.cpp plus the
community seeder `seed.bitcoin.fish.foo` (not in Core's vSeeds). Full
table with operators and software: [SOURCES.md](SOURCES.md).

### Layer B — Full crawler dumps (`data/dumps/`)

The complete crawler view published by seeder/crawler operators —
including the three sources Bitcoin Core's `contrib/seeds/makeseeds.py`
uses for fixed-seed generation. Downloaded once per day (cron `43 5 * * *`).

The dumps are large (~40 MB/day total), so they are **not committed to
git**. The workflow uploads them unmodified as assets to a monthly GitHub
release (`dumps-YYYY-MM`, asset name `<source>-YYYY-MM-DD.txt.gz`). Only
`data/dumps/manifest.jsonl` is tracked in git; it records URL, size,
SHA-256 and HTTP status for every download (including failures), so each
release asset can be verified against the manifest. Manual runs keep the
files locally under `data/dumps/<source>/` (gitignored).

Sources (full table with descriptions: [SOURCES.md](SOURCES.md)):

- **seeds.txt.gz dumps** from sipa, achow101, virtu (21.ninja) and the
  community seeder fish.foo. Dump format (bitcoin-seeder `dnsseed.dump`):
  one node per line with address, good flag, lastSuccess timestamp,
  uptime over five windows (2h/8h/1d/7d/30d), block height, service
  flags, protocol version and user agent.
- **BitMEX Research crawler** (`bitnod.es`): the daily node CSV
  (`https://bitnod.es/csv/bitcoin_nodes_YYYY-MM-DD.csv`, stored as
  `bitmex-YYYY-MM-DD.csv.gz`). One row per known node with export_date,
  IP, port, country, ISP, services, protocol version, user agent and
  block height. The collector tries today's date and falls back up to
  3 days; files are stored under the date in the URL.
- **btcnodes.io** (brunneis' revival of the ayeowch/bitnodes crawler):
  the latest full snapshot from `api/v1/snapshots/latest/` (~750 KB
  gzipped, includes Tor/I2P/CJDNS nodes). One snapshot per day; a
  one-time backfill archived one noon snapshot per day back to
  2026-05-10 (the crawler's restart).
- **KIT DSN dossier** (`dsn.kastel.kit.edu/bitcoin/snapshots/`): the
  newest daily research-crawl dossier (~520 KB gzipped, per-node
  whois/ASN annotations), resolved by scraping the directory index.
  KIT keeps its full history (back to 2015-07) online, so missed days
  can be backfilled at any time.
- **Blockchair nodes API** (`api.blockchair.com/bitcoin/nodes`, stored as
  `blockchair-YYYY-MM-DD.json.gz`). Note: this endpoint only returns a
  limited "recently active" subset (~300 nodes), not a full crawl.

## Known limitations

- DNS responses depend on the resolver location of the GitHub Actions
  runner (US datacenters); anycast or GeoDNS behavior of individual seeds
  is not distinguishable from a single vantage point.
- The 6-hour sampling of DNS responses under-samples the seeder pools;
  counts of unique addresses per seed are lower bounds, not pool sizes.
- Crawler dumps are refreshed by their operators on their own schedules;
  a daily download may fetch an identical or a many-hours-old file. The
  manifest SHA-256 makes identical fetches detectable.
- `seed.bitcoin.wiz.biz` publishes no crawler dump (DNS responses only);
  `wiz.biz/bitcoin/seed` is an HTML status page.
- bitnodes.io (ayeowch/bitnodes) has been unreachable since ~June 2026
  and is not collected. Historic archives exist at
  https://github.com/asmap/sample-data/releases/tag/bitnodes; its
  crawler lives on as btcnodes.io (collected, see above).
- `seed.bitcoin.fish.foo` / `bitcoin.fish.foo` is a community source
  whose operator is unverified; treat it as an independent-but-unvetted
  vantage point, not as ground truth.
- The KIT resolver only fetches the newest dossier per run; a skipped
  day is not retried automatically (KIT's index keeps the full history,
  so manual backfill is always possible).
- Collection start: 2026-07-07 (btcnodes backfilled to 2026-05-10).
  No other backfill exists for earlier dates.

## Running manually

```
python3 collector/collect_dns.py    # requires dig
python3 collector/collect_dumps.py
```

Both scripts are Python stdlib only, idempotent per day, and append-only.
Source configuration (seed list, URLs) lives in `collector/seeds.py`.
