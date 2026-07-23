# Data sources

One-stop overview of every Bitcoin node-data source this repo knows about:
what it is, where it comes from, and whether it is collected here. Two
groups: **DNS seeders** (what a bootstrapping node asks) and **crawlers /
node datasets** (the full network view an operator publishes).

Collection status: **daily** = fetched by the scheduled workflows,
**historic** = a one-time archive exists, **not collected** = known but
currently skipped (reason in the notes).

## DNS seeders

All eight seeds from Bitcoin Core's `src/kernel/chainparams.cpp` (mainnet
`vSeeds`, checked 2026-07-08) plus one community seeder. Each seeder runs a
crawler internally and answers DNS queries with a random sample (about 25
addresses) of the healthy nodes it knows.

| Seed | Operator | Software | Status |
|---|---|---|---|
| seed.bitcoin.sipa.be | Pieter Wuille (sipa) | [sipa/bitcoin-seeder](https://github.com/sipa/bitcoin-seeder) | daily (DNS) |
| dnsseed.bluematt.me | Matt Corallo | [TheBlueMatt/dnsseed](https://github.com/TheBlueMatt/dnsseed) | daily (DNS) |
| seed.bitcoin.jonasschnelli.ch | Jonas Schnelli | sipa fork | daily (DNS) |
| seed.btc.petertodd.net | Peter Todd | sipa fork | daily (DNS) |
| seed.bitcoin.sprovoost.nl | Sjors Provoost | sipa fork | daily (DNS) |
| dnsseed.emzy.de | Stephan Oeste (Emzy) | sipa fork | daily (DNS) |
| seed.bitcoin.wiz.biz | Jason Maurice (wiz) | [wiz/dnsseed-rust](https://github.com/wiz/dnsseed-rust) | daily (DNS); bare hostname is IPv4-only, but service-bit subdomains (x1, x9, ...) do return AAAA records; no dump |
| seed.mainnet.achownodes.xyz | Ava Chow (achow101) | [achow101/dnsseedrs](https://github.com/achow101/dnsseedrs) | daily (DNS) |
| seed.bitcoin.fish.foo | Will Clark (willcl-ark, Bitcoin Core contributor; **not in Core's vSeeds**) | [willcl-ark/dnsseedrs](https://github.com/willcl-ark/dnsseedrs) (achow101 fork) | daily (DNS) |

Two former Core seeds are still live and answering (both monitored by the
octavio seed monitor below), but we do not query them ourselves:

- `dnsseed.bitcoin.dashjr-list-of-p2p-nodes.us` (Luke Dashjr) - removed
  from Core's vSeeds in December 2025
  ([PR #33723](https://github.com/bitcoin/bitcoin/pull/33723)), still
  listed in Bitcoin Knots.
- `seed.bitcoinstats.com` (Christian Decker) - removed from Core's vSeeds
  in August 2024, still answering with a full record set.

## Crawlers / node datasets

| Source | Operator / origin | What it is | Status |
|---|---|---|---|
| [bitcoin.sipa.be/seeds.txt.gz](https://bitcoin.sipa.be/seeds.txt.gz) | Pieter Wuille (sipa) | Full `dnsseed.dump` of the sipa seeder crawler; one line per known node with uptime stats over 2h..30d. Used by Core's `makeseeds.py`. **Published dump is frozen since 2025-11-22** (the DNS seed itself stays fresh); still fetched in case it resumes. | daily (stale upstream) |
| [mainnet.achownodes.xyz/seeds.txt.gz](https://mainnet.achownodes.xyz/seeds.txt.gz) | Ava Chow (achow101) | Same dump format from the dnsseedrs crawler; widest service-bit coverage. Used by Core's `makeseeds.py`. | daily |
| [21.ninja/seeds.txt.gz](https://21.ninja/seeds.txt.gz) | virtu | Same dump format from the [virtu/p2p-crawler](https://github.com/virtu/p2p-crawler). Used by Core's `makeseeds.py`. **Frozen since 2026-05-22**; still fetched in case it resumes. | daily (stale upstream) |
| [bitcoin.fish.foo/seeds.txt.gz](https://bitcoin.fish.foo/seeds.txt.gz) | Will Clark (willcl-ark) | Same dump format from his dnsseedrs fork; fresh and the data source of his [dashboard](https://willcl-ark.github.io/dnsseedrs/). Not in Core's vSeeds, so an independent vantage point. | daily |
| [bitnod.es](https://bitnod.es) daily CSV | BitMEX Research | Cumulative "last seen" CSV per day (IP, port, country, ISP, services, UA, height) including many `.onion` rows. Clearnet charts in this repo use IPv4+IPv6 only. Weekly files before 2026-06-26, daily after. Backfilled to 2026-05-21 from manual downloads (flagged in the manifest). | daily + historic backfill |
| [btcnodes.io API](https://btcnodes.io/api/v1/snapshots/latest/) | Rodrigo Martinez (brunneis) | Revival of the original [ayeowch/bitnodes](https://github.com/brunneis/btcnodes) crawler behind bitnodes.io; snapshots roughly every 24 minutes incl. Tor/I2P/CJDNS, compact per-node format without ASN/geo. API history reaches back to 2026-05-10 (its restart). | daily + historic backfill (one noon snapshot per day since 2026-05-10) |
| [KIT DSN dossiers](https://www.dsn.kastel.kit.edu/bitcoin/snapshots/) | KIT DSN group (Karlsruhe Institute of Technology) | Daily research crawl dossier (about 6 MB JSON) with per-node whois/ASN annotations; public keys are hashed (no raw IPs). Every entry is connected to the monitor at dossier creation; full-dossier clearnet count matches the [live churn plot](https://www.dsn.kastel.kit.edu/bitcoin/) unique-IP scale (~9–10k). `lastConnect` is connection start time (connection-age buckets), not last-seen. Backfilled daily from 2026-05-10 (same start as btcnodes). | daily + historic backfill |
| [api.blockchair.com/bitcoin/nodes](https://api.blockchair.com/bitcoin/nodes) | Blockchair | Filtered "recently active" subset (about 300 nodes), not a full crawl; kept as a cheap cross-check. | daily |
| [octavio.xyz DNS seed monitor](https://octavio.xyz/projects/dns-monitoring/) | Octavio Lucca (Vinteum fellow, peer-observer contributor) | Daily per-seed quality metrics (advertised/reachable/stale/pristine/duplicate) covering 9 seeds incl. the two ex-Core seeds (dashjr, bitcoinstats). Two stitched datasets: his own measurements via the JSON API since 2026-05-17 (`api/dns/timeseries`, full API history in every response), plus virtu's historic series (2022-10-11 to 2025-11-04, originally at [21.ninja/dns-seeds](https://21.ninja/dns-seeds/)) hosted as static CSVs under `demo-data/`. Between the two datasets there is a measurement gap (Nov 2025 to May 2026). `api/dns/latest`, `api/hardcoded/history` and `api/decay/history` exist too. | daily (API) + historic (virtu CSVs archived once in `data/octavio-historic/`) |
| [bitcoin-data/getrawaddrman](https://github.com/bitcoin-data/getrawaddrman) | 0xb10c / peer.observer nodes | Daily `getrawaddrman` RPC exports (full `new`/`tried` tables incl. Tor/I2P) of the `hal` and `len` demo nodes. Git history covers 2026-02-02 onward (gap 2026-02-15 to 2026-03-03) and therefore brackets the April 2026 address flood. `analysis/addrman_history.py` reads every version directly from a sibling clone and computes timestamp-freshness, turnover and cohort-survival histories from the snapshots alone. Raw snapshots are not duplicated here. | analyzed from upstream git history |
| bitnodes.io | Addy Yeow (ayeowch) | The original crawler/website; **offline since around May 2026**. b10c's archived snapshots (2024-08 to 2026-04) live at [asmap/sample-data](https://github.com/asmap/sample-data/releases/tag/bitnodes). | historic only |
| [wiz.biz/bitcoin/seed](https://wiz.biz/bitcoin/seed) | Jason Maurice (wiz) | HTML status page of the wiz seeder; publishes no machine-readable dump. | not collected |

## Related monitoring (no raw node data, not collected)

Kept here so nothing gets re-evaluated from scratch:

- [willcl-ark.github.io/dnsseedrs](https://willcl-ark.github.io/dnsseedrs/) - Will Clark's dashboard over his own fish.foo seeder data: regenerated every 6 hours from the dump we already collect raw, maps good nodes through Core's `latest_asmap.dat`, shows Core/Knots split, per-network stats (IPv4/IPv6/Tor/I2P/CJDNS) and flags probable sybils (IPv4 /24 and IPv6 /48 prefixes and ASNs whose node count exceeds mean + 5 standard deviations).
- [census.yonson.dev](https://census.yonson.dev/) - listening-node feature-acceptance ratios; `census.jsonl` (about 90 KB) is aggregates-only and carries its full history in one file.
- [demo.peer.observer](https://demo.peer.observer/) - daily zst addrman snapshots of the same nodes as bitcoin-data/getrawaddrman (30-day retention); redundant with that repo's git archive.
- [dns-seed.github.io](https://dns-seed.github.io/) (Seed Coat) - current A/AAAA record counts per seeder only; our own DNS layer measures this better.
- [bitdis.org](https://bitdis.org/) - aggregate Core/Knots counters by the btcnodes.io operator; no node lists.
- [ViniciusCestarii/bitcoin-node-os-fingerprint](https://github.com/ViniciusCestarii/bitcoin-node-os-fingerprint) - monthly nmap OS fingerprints of reachable nodes (CSV in git, started 2026-07); OS metadata, not a node-list source.
- [BNOC data share](https://bitcoin-noc.github.io/datashare-website/) - ad-hoc Google-Drive datasets (pcaps, debug.logs); no stable URL, manual treasure trove only.
- [lopp.net node stats](https://www.lopp.net/bitcoin-information/statistics-metrics.html) / [Map of Bitcoin Monitoring](https://bitcoin-noc.github.io/map-of-bitcoin-monitoring/) - link collections, no data endpoints.
