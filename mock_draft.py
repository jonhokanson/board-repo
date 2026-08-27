#!/usr/bin/env python3
"""Simulate a mock draft across all 10 TBML teams, using the real player pool
(pool.json) + real overall ADP rankings for value, plus lightweight
roster-need logic (SLOT_TEMPLATE, matching the league's real QB/RB/RB/W-T/
W-T/W-R-T/K/DEF + bench roster -- see tbml-2026-league-rules.md) so teams
don't draft absurdly (e.g. 5 QBs before a single RB).

Writes mock_state.seed.json -- the version-controlled baseline the live app's
"/mock/reset" route restores mock_state.json from (see draft_app.py's
mock_reset()). This is a SIMULATION for demo purposes only: it never touches
the real state.json used for live draft-day tracking, and mock_state.json
itself (the live working copy on Web01) is untouched too -- only reset to
this seed when someone hits "Reset mock draft" on /mock/entry.

Rerun this any time pool.json changes (a rankings/ADP refresh -- see
RANKINGS.md) so the mock demo reflects current data instead of a stale
snapshot. All 10 teams' real Keep and Protect-pair data (from the league's
keeper spreadsheet, see tbml-2026-keeper-protect-data.md) IS modeled
correctly, including the protect-consolation mechanic for every team: as soon
as either player in a team's protect pair gets drafted live -- by a rival, or
by the owning team itself -- the other half is immediately pulled from the
pool and guaranteed to that team at Round 13. Whatever live pick triggered
it stays exactly where it happened; there's no separate "bonus round."

SIM_ROUNDS controls how many live rounds actually get simulated -- set it
below the league's full 12 to produce a partial "draft in progress" board
(useful for demos), or leave at 12 for a complete mock (the normal case for
regenerating the shipped seed).

Run with: python3 mock_draft.py    (from wherever this file + pool.json +
state.template.json live -- board-repo's v2-live-app checkout, normally).
"""
import copy
import json
import os
import random

import generate as g

# Paths are relative to this file's own location -- see the same pattern in
# generate.py, build_pool3.py, match_overall_ranks.py -- so this runs
# unmodified from the sandbox or a fresh board-repo checkout. Deliberately
# writes to mock_state.seed.json (not mock_state.json) -- the seed is the
# version-controlled "reset to this" baseline; mock_state.json is the live
# working copy on Web01 that /mock/reset copies the seed over, never
# something this script should overwrite directly.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POOL_PATH = os.path.join(BASE_DIR, "pool.json")
STATE_PATH = os.path.join(BASE_DIR, "state.template.json")
OUT_STATE = os.path.join(BASE_DIR, "mock_state.seed.json")

random.seed(30260)  # reproducible mock -- change/remove to get a different sim

SIM_ROUNDS = 12  # how many live rounds to actually simulate for this mock

# Live-round roster slots to fill per team (matches the league's roster:
# QB, RB, RB, W/T, W/T, W/R/T, K, DEF, BN x6 -- 2 of the 6 BN come from the
# reserved Keep/Protect rounds 13-14, so only 4 BN get filled live).
SLOT_TEMPLATE = [
    ("QB", {"QB"}),
    ("RB", {"RB"}),
    ("RB", {"RB"}),
    ("W/T", {"WR", "TE"}),
    ("W/T", {"WR", "TE"}),
    ("W/R/T", {"WR", "RB", "TE"}),
    ("K", {"K"}),
    ("DEF", {"DEF"}),
    ("BN", {"QB", "RB", "WR", "TE", "K", "DEF"}),
    ("BN", {"QB", "RB", "WR", "TE", "K", "DEF"}),
    ("BN", {"QB", "RB", "WR", "TE", "K", "DEF"}),
    ("BN", {"QB", "RB", "WR", "TE", "K", "DEF"}),
]
SPECIFICITY_ORDER = ["QB", "RB", "W/T", "W/R/T", "K", "DEF", "BN"]


# overall_pick / draft_order_for_round now live in generate.py so the real
# app, the mock simulator, and the rendered board's JS all agree on draft
# order -- used below as g.overall_pick / g.draft_order_for_round.


def value_key(p):
    if p.get("overallRank"):
        return p["overallRank"]
    return 300 + (p["rank"] or 999)


def pick_for_team(available, open_slots):
    needed_positions = set()
    for _, elig in open_slots:
        needed_positions |= elig
    candidates = [p for p in available if p["pos"] in needed_positions] or available
    only_flex_open = needed_positions <= {"QB", "RB", "WR", "TE"}

    def score(p):
        penalty = 40 if (p["pos"] in ("K", "DEF") and only_flex_open) else 0
        return value_key(p) + random.uniform(-6, 6) + penalty

    candidates.sort(key=score)
    return candidates[0]


def assign_slot(open_slots, pos):
    best_i = None
    for i, (label, elig) in enumerate(open_slots):
        if pos in elig:
            if best_i is None or SPECIFICITY_ORDER.index(label) < SPECIFICITY_ORDER.index(open_slots[best_i][0]):
                best_i = i
    open_slots.pop(best_i)


def main():
    real_pool = json.load(open(POOL_PATH))
    state = json.load(open(STATE_PATH))

    teams = state["teams"]
    n = len(teams)
    sim_rounds = min(SIM_ROUNDS, state["liveRounds"])

    pool = copy.deepcopy(real_pool)
    pool_by_name = {p["name"]: p for p in pool}

    # Every team's real Keep is off the board before a single pick happens --
    # pool.json's own "status" field doesn't reflect this (that's computed at
    # render time by generate.py), so it has to be applied here explicitly or
    # kept players would incorrectly be draftable in the simulation.
    kept_names = {
        info["keep"]["name"]
        for info in state.get("keepers", {}).values()
        if info.get("keep")
    }
    available = [
        p for p in pool
        if p["status"] == "available" and p["name"] not in kept_names
    ]

    # Every team's real protect pair (2 players each), tracked independently.
    # Whichever half of the pair gets drafted first -- by a rival, or by the
    # owning team itself, live -- the other half is simply guaranteed to that
    # team at Round 13. The live pick that triggered it (whoever made it,
    # whatever round) just stays where it happened; there's no separate
    # "bonus round" mechanic.
    protect_pairs = {
        team: list(info.get("protect", []))
        for team, info in state.get("keepers", {}).items()
    }
    protect_resolved = {team: False for team in protect_pairs}
    protect_results = {
        team: {"guaranteed": None}
        for team in protect_pairs
    }

    rosters = {t: [] for t in teams}
    open_slots = {t: [s for s in SLOT_TEMPLATE] for t in teams}
    picks = []
    protect_self_drafted = {}  # team -> True if the team drafted its own protect (for the recap text only)

    for r in range(1, sim_rounds + 1):
        for t_idx in g.draft_order_for_round(r, teams):
            team = teams[t_idx]

            slots = open_slots[team]
            if not slots:
                continue
            player = pick_for_team(available, slots)
            available.remove(player)
            assign_slot(slots, player["pos"])
            rosters[team].append(player)
            picks.append({
                "round": r, "team": team, "name": player["name"], "pos": player["pos"],
                "overallPick": g.overall_pick(r, t_idx, n),
            })

            # Check every team's still-unresolved protect pair against this pick.
            for pair_team, pair in protect_pairs.items():
                if protect_resolved.get(pair_team) or player["name"] not in pair:
                    continue
                other_name = [x for x in pair if x != player["name"]][0]
                other = pool_by_name.get(other_name)
                protect_results[pair_team] = {
                    "guaranteed": {"name": other_name, "pos": other["pos"] if other else None},
                }
                protect_self_drafted[pair_team] = (team == pair_team)
                protect_resolved[pair_team] = True
                if other in available:
                    available.remove(other)
                break

    mock_state = copy.deepcopy(state)
    mock_state["picks"] = [
        {"round": pk["round"], "team": pk["team"], "name": pk["name"], "pos": pk["pos"]}
        for pk in picks
    ]
    for team, result in protect_results.items():
        mock_state["protectResolution"][team] = result
    json.dump(mock_state, open(OUT_STATE, "w"), indent=2)

    resolved_count = sum(protect_resolved.values())
    print(f"Simulated {len(picks)} live picks across {sim_rounds} rounds "
          f"(of {state['liveRounds']} total live rounds -- rest left open for the demo).")
    print(f"{resolved_count} of {len(protect_pairs)} teams' protect pairs resolved so far:")
    for team, result in protect_results.items():
        if not protect_resolved[team]:
            continue
        if protect_self_drafted.get(team):
            print(f"  {team}: drafted one of their own protects live (pick stands as-is) -> "
                  f"{result['guaranteed']['name']} guaranteed free at Round 13.")
        else:
            print(f"  {team}: a rival drafted one of their protects -> "
                  f"{result['guaranteed']['name']} guaranteed free at Round 13.")
    print()

    for team in teams:
        print(team)
        for p in rosters[team]:
            ovr = f"Ovr {p['overallRank']}" if p.get("overallRank") else "Ovr --"
            print(f"   {p['pos']:<4} {p['name']:<26} {ovr}")
        keep = state.get("keepers", {}).get(team, {}).get("keep")
        if keep:
            print(f"   {keep['pos']:<4} {keep['name']:<26} (R14 free Keep)")
        print()


if __name__ == "__main__":
    main()
