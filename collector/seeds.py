"""Source-of-truth configuration for all collected Bitcoin seeder data sources.

DNS seed list mirrors the mainnet ``vSeeds`` entries in Bitcoin Core's
``src/kernel/chainparams.cpp`` (checked 2026-07-07). The ``service_bits``
per seed follow the "only supports ..." comments in chainparams; for seeds
without such a comment we probe the common set. Unsupported subdomains
simply return NXDOMAIN, which is recorded and is itself a data point.
"""

# Common service-bit filter subdomains queried by Bitcoin Core:
#   x1  = NODE_NETWORK
#   x5  = NODE_NETWORK | NODE_BLOOM
#   x9  = NODE_NETWORK | NODE_WITNESS  (Bitcoin Core default)
#   xd  = NODE_NETWORK | NODE_BLOOM | NODE_WITNESS
COMMON_BITS = ["x1", "x5", "x9", "xd"]

ACHOW_BITS = [
    "x1", "x5", "x9", "x49", "x809", "x849", "xd",
    "x400", "x404", "x408", "x448", "xc08", "xc48", "x40c",
]

DNS_SEEDS = {
    "seed.bitcoin.sipa.be": {
        "operator": "Pieter Wuille (sipa)",
        "software": "sipa/bitcoin-seeder",
        "service_bits": COMMON_BITS,
    },
    "dnsseed.bluematt.me": {
        "operator": "Matt Corallo (TheBlueMatt)",
        "software": "TheBlueMatt/dnsseed",
        "service_bits": ["x9"],
    },
    "seed.bitcoin.jonasschnelli.ch": {
        "operator": "Jonas Schnelli",
        "software": "sipa/bitcoin-seeder (fork)",
        "service_bits": COMMON_BITS,
    },
    "seed.btc.petertodd.net": {
        "operator": "Peter Todd",
        "software": "sipa/bitcoin-seeder (fork)",
        "service_bits": COMMON_BITS,
    },
    "seed.bitcoin.sprovoost.nl": {
        "operator": "Sjors Provoost",
        "software": "sipa/bitcoin-seeder (fork)",
        "service_bits": COMMON_BITS,
    },
    "dnsseed.emzy.de": {
        "operator": "Stephan Oeste (Emzy)",
        "software": "sipa/bitcoin-seeder (fork)",
        "service_bits": COMMON_BITS,
    },
    "seed.bitcoin.wiz.biz": {
        "operator": "Jason Maurice (wiz)",
        "software": "wiz/dnsseed-rust",
        "service_bits": COMMON_BITS,
    },
    "seed.mainnet.achownodes.xyz": {
        "operator": "Ava Chow (achow101)",
        "software": "achow101/dnsseedrs",
        "service_bits": ACHOW_BITS,
    },
    # Community seeder, NOT in Bitcoin Core's vSeeds (operator unverified);
    # collected because it publishes a matching public crawler dump.
    "seed.bitcoin.fish.foo": {
        "operator": "fish.foo (community, non-Core)",
        "software": "sipa/bitcoin-seeder (dump format match)",
        "service_bits": COMMON_BITS,
    },
}

# Full crawler dumps published by seeder operators (bitcoin-seeder dump
# format: address, good, lastSuccess, uptime %(2h/8h/1d/7d/30d), blocks,
# services, version). These are the sources used by Bitcoin Core's
# contrib/seeds/makeseeds.py for fixed-seed generation.
CRAWLER_DUMPS = {
    "sipa": {
        "url": "https://bitcoin.sipa.be/seeds.txt.gz",
        "operator": "Pieter Wuille (sipa)",
        "kind": "seeds.txt.gz",
    },
    "achow101": {
        "url": "https://mainnet.achownodes.xyz/seeds.txt.gz",
        "operator": "Ava Chow (achow101)",
        "kind": "seeds.txt.gz",
    },
    "virtu": {
        "url": "https://21.ninja/seeds.txt.gz",
        "operator": "virtu",
        "kind": "seeds.txt.gz",
    },
    "fishfoo": {
        "url": "https://bitcoin.fish.foo/seeds.txt.gz",
        "operator": "fish.foo (community, non-Core)",
        "kind": "seeds.txt.gz",
    },
}

# Third-party crawler APIs (JSON responses, stored gzipped as delivered).
# Note: Blockchair's nodes endpoint only returns a limited "recently
# active" subset (~300 nodes), not a full crawl.
API_SOURCES = {
    "blockchair": {
        "url": "https://api.blockchair.com/bitcoin/nodes",
        "operator": "Blockchair",
        "kind": "json",
    },
    # Revival of the ayeowch/bitnodes crawler (brunneis fork) that ran
    # bitnodes.io until its demise; snapshots every ~24 min, we archive
    # one per day. Compact node format (no per-node ASN/geo).
    "btcnodes": {
        "url": "https://btcnodes.io/api/v1/snapshots/latest/",
        "operator": "Rodrigo Martinez (brunneis, btcnodes.io)",
        "kind": "json",
    },
    # Daily per-seed quality metrics (advertised/reachable/stale/pristine/
    # duplicate) back to Oct 2022. Each response carries the full history,
    # so a daily fetch self-heals gaps. Sibling endpoints (dns/latest,
    # hardcoded/history, decay/history) are documented in SOURCES.md.
    "octavio": {
        "url": "https://octavio.xyz/projects/dns-monitoring/api/dns/timeseries",
        "operator": "octavio.xyz DNS seed monitor",
        "kind": "json",
    },
}

# Sources publishing one dated file per day. The collector tries today's
# date first and falls back up to ``lookback_days`` if not yet published.
DATED_SOURCES = {
    "bitmex": {
        "url_template": "https://bitnod.es/csv/bitcoin_nodes_{date}.csv",
        "operator": "BitMEX Research (bitnod.es)",
        "kind": "csv",
        "lookback_days": 3,
    },
}

# Sources publishing dated files behind an HTML directory index whose
# exact filenames carry an unpredictable timestamp. The collector scrapes
# the index, picks the newest match, and archives it under its date.
# KIT's full history (daily dossiers back to 2015-07) stays available on
# the index, so only the newest file is fetched per run.
INDEXED_SOURCES = {
    "kit": {
        "index_url": "https://www.dsn.kastel.kit.edu/bitcoin/snapshots/",
        "file_pattern": r"(\d{8})_\d{6}_dossier\.json",
        "operator": "KIT DSN group (dsn.kastel.kit.edu)",
        "kind": "json",
    },
}
