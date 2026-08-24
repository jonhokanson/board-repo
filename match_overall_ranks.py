#!/usr/bin/env python3
"""Match overall_adp.py's cross-position ADP list onto pool.json entries,
writing an `overallRank` field (int or None) onto each player. Run after any
pool.json rebuild, before generate.py."""
import json
import os
import re
import unicodedata
from overall_adp import OVERALL_ADP

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POOL_PATH = os.path.join(BASE_DIR, "pool.json")

# Full team name (as used for DEF entries in pool.json) keyed by ADP's team abbr.
TEAM_ABBR_TO_FULL = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
    "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}


def norm(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.lower()
    name = re.sub(r"\b(jr|sr|ii|iii|iv)\.?\b", "", name)
    name = re.sub(r"[^a-z0-9]", "", name)
    return name


def main():
    pool = json.load(open(POOL_PATH))

    # Build lookup: normalized name -> list of pool entries (positions can collide
    # rarely, e.g. two "AJ Barner"-type near-duplicates, so keep a list).
    by_norm = {}
    for p in pool:
        by_norm.setdefault(norm(p["name"]), []).append(p)
        p["overallRank"] = None  # reset each run

    matched = 0
    unmatched = []
    for rank, adp_name, team, pos in OVERALL_ADP:
        if pos == "DEF":
            full_name = TEAM_ABBR_TO_FULL.get(team)
            candidates = [p for p in pool if p["pos"] == "DEF" and p["name"] == full_name]
        else:
            candidates = by_norm.get(norm(adp_name), [])
            if len(candidates) > 1:
                # Prefer the one matching position, if ambiguous.
                pos_matches = [c for c in candidates if c["pos"] == pos]
                if pos_matches:
                    candidates = pos_matches
        if candidates:
            candidates[0]["overallRank"] = rank
            matched += 1
        else:
            unmatched.append((rank, adp_name, team, pos))

    json.dump(pool, open(POOL_PATH, "w"), indent=2)
    print(f"Matched {matched}/{len(OVERALL_ADP)} overall-ADP rows into pool.json")
    if unmatched:
        print("Unmatched ADP rows (left with no pool.json counterpart):")
        for rank, name, team, pos in unmatched:
            print(f"  #{rank} {name} ({team} {pos})")


if __name__ == "__main__":
    main()
