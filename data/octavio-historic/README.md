# Historic DNS-seed quality series (virtu, via octavio.xyz)

One-time archive (fetched 2026-07-08) of the static CSVs served at
`https://octavio.xyz/projects/dns-monitoring/demo-data/`.

Provenance, as credited on the octavio.xyz summary page: collected by
[virtu](https://github.com/virtu) via
[p2p-crawler](https://github.com/virtu/p2p-crawler) from 2022-10-11 to
2025-11-04, originally published at
[21.ninja/dns-seeds](https://21.ninja/dns-seeds/). Octavio Lucca's own
measurements (via the JSON API, collected daily by this repo) resume on
2026-05-17; the months in between are a measurement gap nobody covered.

Files: `dns_seed_summary.csv` (network-wide totals per category) plus one
`dns_seed_<metric>.csv` per metric (advertised/pristine/reachable/
unreachable/duplicate/stale, as node counts and shares), one column per
seed (sipa, bluematt, dashjr, bitcoinstats, schnelli, todd, provoost,
emzy, wiz).
