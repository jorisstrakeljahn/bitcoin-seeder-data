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
`vSeeds`, checked 2026-07-07) plus one community seeder. Each seeder runs a
crawler internally and answers DNS queries with a random sample (~25
addresses) of the healthy nodes it knows.

| Seed | Operator | Software | Status |
|---|---|---|---|
| seed.bitcoin.sipa.be | Pieter Wuille (sipa) | [sipa/bitcoin-seeder](https://github.com/sipa/bitcoin-seeder) | daily (DNS) |
| dnsseed.bluematt.me | Matt Corallo | [TheBlueMatt/dnsseed](https://github.com/TheBlueMatt/dnsseed) | daily (DNS) |
| seed.bitcoin.jonasschnelli.ch | Jonas Schnelli | sipa fork | daily (DNS) |
| seed.btc.petertodd.net | Peter Todd | sipa fork | daily (DNS) |
| seed.bitcoin.sprovoost.nl | Sjors Provoost | sipa fork | daily (DNS) |
| dnsseed.emzy.de | Stephan Oeste (Emzy) | sipa fork | daily (DNS) |
| seed.bitcoin.wiz.biz | Jason Maurice (wiz) | [wiz/dnsseed-rust](https://github.com/wiz/dnsseed-rust) | daily (DNS); IPv4 only, no dump |
| seed.mainnet.achownodes.xyz | Ava Chow (achow101) | [achow101/dnsseedrs](https://github.com/achow101/dnsseedrs) | daily (DNS) |
| seed.bitcoin.fish.foo | fish.foo (community, **not in Core's vSeeds**, operator unverified) | sipa-compatible | daily (DNS) |

## Crawlers / node datasets

| Source | Operator / origin | What it is | Status |
|---|---|---|---|
| [bitcoin.sipa.be/seeds.txt.gz](https://bitcoin.sipa.be/seeds.txt.gz) | Pieter Wuille (sipa) | Full `dnsseed.dump` of the sipa seeder crawler; one line per known node with uptime stats over 2h..30d. Used by Core's `makeseeds.py`. | daily |
| [mainnet.achownodes.xyz/seeds.txt.gz](https://mainnet.achownodes.xyz/seeds.txt.gz) | Ava Chow (achow101) | Same dump format from the dnsseedrs crawler; widest service-bit coverage. Used by Core's `makeseeds.py`. | daily |
| [21.ninja/seeds.txt.gz](https://21.ninja/seeds.txt.gz) | virtu | Same dump format from the [virtu/p2p-crawler](https://github.com/virtu/p2p-crawler). Used by Core's `makeseeds.py`. | daily |
| [bitcoin.fish.foo/seeds.txt.gz](https://bitcoin.fish.foo/seeds.txt.gz) | fish.foo (community, unverified) | Same dump format from a non-Core community seeder; independent vantage point. | daily |
| [bitnod.es](https://bitnod.es) daily CSV | BitMEX Research | Cumulative "last seen" CSV per day (IP, port, country, ISP, services, UA, height); the bitnodes.io-style continuation after its demise. Weekly files before ~2026-06-26, daily after. | daily |
| [btcnodes.io API](https://btcnodes.io/api/v1/snapshots/latest/) | Rodrigo Martinez (brunneis) | Revival of the original [ayeowch/bitnodes](https://github.com/brunneis/btcnodes) crawler behind bitnodes.io; ~24-min snapshots incl. Tor/I2P/CJDNS, compact per-node format without ASN/geo. API history reaches back to 2026-05-10 (its restart). | daily + historic backfill (one noon snapshot per day since 2026-05-10) |
| [KIT DSN dossiers](https://www.dsn.kastel.kit.edu/bitcoin/snapshots/) | KIT DSN group (Karlsruhe Institute of Technology) | Daily research crawl dossier (~6 MB JSON) with per-node whois/ASN annotations; public directory index reaches back to 2015-07, so gaps can be backfilled any time. | daily (newest dossier per run) |
| [api.blockchair.com/bitcoin/nodes](https://api.blockchair.com/bitcoin/nodes) | Blockchair | Filtered "recently active" subset (~300 nodes), not a full crawl; kept as a cheap cross-check. | daily |
| [octavio.xyz DNS seed monitor](https://octavio.xyz/projects/dns-monitoring/) | octavio | Daily per-seed quality metrics (advertised/reachable/stale/pristine/duplicate) back to Oct 2022 - the only third-party seeder-quality time series. We archive `api/dns/timeseries` (~74 KB, full history in every response); `api/dns/latest`, `api/hardcoded/history` and `api/decay/history` exist too. | daily |
| [bitcoin-data/getrawaddrman](https://github.com/bitcoin-data/getrawaddrman) | 0xb10c / peer.observer nodes | Daily `getrawaddrman` RPC exports (full addrman incl. Tor/I2P) of two instrumented nodes; a complementary addrman-view rather than a crawler-view. Full history already archived in that repo's git log. | not collected (archived upstream) |
| bitnodes.io | Addy Yeow (ayeowch) | The original crawler/website; **dead since ~June 2026**. b10c's archived snapshots (2024-08..2026-04) live at [asmap/sample-data](https://github.com/asmap/sample-data/releases/tag/bitnodes). | historic only |
| [wiz.biz/bitcoin/seed](https://wiz.biz/bitcoin/seed) | Jason Maurice (wiz) | HTML status page of the wiz seeder; publishes no machine-readable dump. | not collected |

## Related monitoring (no raw node data, not collected)

Kept here so nothing gets re-evaluated from scratch:

- [willcl-ark.github.io/dnsseedrs](https://willcl-ark.github.io/dnsseedrs/) - DNS-seeder health dashboard; its `data.json` aggregates are derived from the fish.foo dump we already collect raw.
- [census.yonson.dev](https://census.yonson.dev/) - listening-node feature-acceptance ratios; `census.jsonl` (~90 KB) is aggregates-only and carries its full history in one file.
- [demo.peer.observer](https://demo.peer.observer/) - daily zst addrman snapshots of the same nodes as bitcoin-data/getrawaddrman (30-day retention); redundant with that repo's git archive.
- [dns-seed.github.io](https://dns-seed.github.io/) (Seed Coat) - current A/AAAA record counts per seeder only; our own DNS layer measures this better.
- [bitdis.org](https://bitdis.org/) - aggregate Core/Knots counters by the btcnodes.io operator; no node lists.
- [BNOC data share](https://bitcoin-noc.github.io/datashare-website/) - ad-hoc Google-Drive datasets (pcaps, debug.logs); no stable URL, manual treasure trove only.
- [lopp.net node stats](https://www.lopp.net/bitcoin-information/statistics-metrics.html) / [Map of Bitcoin Monitoring](https://bitcoin-noc.github.io/map-of-bitcoin-monitoring/) - link collections, no data endpoints.
