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
}

# Third-party crawler APIs (JSON responses, stored gzipped as delivered).
API_SOURCES = {
    "blockchair": {
        "url": "https://api.blockchair.com/bitcoin/nodes",
        "operator": "Blockchair",
        "kind": "json",
    },
}
