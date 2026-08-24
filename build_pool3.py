#!/usr/bin/env python3
"""Build pool.json from real 2026 positional fantasy rankings (standard
scoring), including each player's rank within their position.

Run this after refreshing raw_rankings.py, then run match_overall_ranks.py
to layer overall_adp.py's cross-position ADP onto the result. See
RANKINGS.md for the full refresh workflow.

Every player here starts "available" -- this script has NO knowledge of
picks, keepers, or protects. That's intentional: state.json is the single
source of truth for live draft state, and generate.py's
build_derived_state() layers it onto this pool fresh, in memory, on every
page render. Baking any keeper/protect status into pool.json itself would
be redundant at best and stale at worst (an earlier version of this script
hardcoded just one team's keep/protect here, which silently went stale the
moment other teams' keepers were added to state.json -- don't repeat that)."""
import json
import os
from raw_rankings import (
    QB_RANKS, RB_RANKS, WR_RANKS, TE_RANKS, K_RANKS, DEF_RANKS,
    TEAM_ABBR2, ALL_32_DEFENSES2,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POOL_PATH = os.path.join(BASE_DIR, "pool.json")


def parse_ranked_block(block):
    out = []
    for line in block.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        name, team = [p.strip() for p in line.rsplit(" - ", 1)]
        out.append((name, team))
    return out


def main():
    pool = []

    for pos, block in [("QB", QB_RANKS), ("RB", RB_RANKS), ("WR", WR_RANKS),
                        ("TE", TE_RANKS), ("K", K_RANKS)]:
        for i, (name, team) in enumerate(parse_ranked_block(block), start=1):
            pool.append({
                "name": name,
                "pos": pos,
                "nflTeam": TEAM_ABBR2.get(team, team),
                "rank": i,
                "status": "available",
                "pickInfo": None,
                "protectedBy": None,
            })

    ranked_defs = [l.strip() for l in DEF_RANKS.strip().splitlines() if l.strip()]
    ranked_def_set = set(ranked_defs)
    for i, team in enumerate(ranked_defs, start=1):
        pool.append({
            "name": team, "pos": "DEF", "nflTeam": team, "rank": i,
            "status": "available", "pickInfo": None, "protectedBy": None,
        })
    for team in ALL_32_DEFENSES2:
        if team not in ranked_def_set:
            pool.append({
                "name": team, "pos": "DEF", "nflTeam": team, "rank": None,
                "status": "available", "pickInfo": None, "protectedBy": None,
            })

    # Sort within each position by rank (unranked entries go to the end).
    pool.sort(key=lambda p: (p["pos"], p["rank"] if p["rank"] is not None else 9999))

    json.dump(pool, open(POOL_PATH, "w"), indent=2)
    from collections import Counter
    print(f"Wrote {len(pool)} players to {POOL_PATH}")
    print(Counter(p["pos"] for p in pool))


if __name__ == "__main__":
    main()
