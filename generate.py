#!/usr/bin/env python3
"""Generate draft_board.html and available_players.html from state.json + pool.json.
Re-run this after editing state.json (adding a pick, resolving a protect, etc.)
to regenerate both pages in sync."""
import json
import math
import os
import random
import re
import urllib.error
import urllib.request
from yahoo_ids import YAHOO_IDS

# Paths are relative to this file's own location, not hardcoded, so this
# module works unmodified wherever it's deployed (Claude's sandbox, Web01's
# /opt/tbml-draft-app, etc.) -- draft_app.py imports these functions
# directly and never calls main(), so these constants only matter when
# generate.py is run standalone (e.g. `python3 generate.py` for a manual
# regen).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Shown in a small footer on every generated page so it's obvious at a glance
# (including on Web01 itself, or in a screenshot) whether a deploy actually
# landed. Scheme: v0.MAJOR.MINOR.PATCH -- bump PATCH (last digit) on routine
# commits, bump MINOR (third digit, reset PATCH to 0) on a notable feature or
# milestone. Bump this by hand alongside any change worth shipping.
APP_VERSION = "0.2.5.1"

POOL_PATH = os.path.join(BASE_DIR, "pool.json")
STATE_PATH = os.path.join(BASE_DIR, "state.json")
BOARD_OUT = os.path.join(BASE_DIR, "draft-board.html")
LIST_OUT = os.path.join(BASE_DIR, "draft-players.html")
KP_OUT = os.path.join(BASE_DIR, "keep-protect.html")
GRADES_DIR = os.path.join(BASE_DIR, "grades")

POS_ORDER = ["QB", "RB", "WR", "TE", "K", "DEF"]
POS_COLORS = {
    "QB": "#c7cdd3",
    "RB": "#e2564f",
    "WR": "#a9d3ff",
    "TE": "#a8f0c0",
    "K": "#d8c4f5",
    "DEF": "#ffe14d",
}


def build_derived_state(state, pool):
    teams = state["teams"]
    my_index = teams.index(state["myTeam"])
    n = len(teams)
    live_rounds = state["liveRounds"]

    picks_grid = [[None] * n for _ in range(live_rounds)]
    pool_by_name = {p["name"]: p for p in pool}

    # Reset pool status derived fields (pool.json's own "kept" flags for
    # keepers still apply; live picks layered on top each regen).
    for p in pool:
        p.setdefault("protectedBy", None)

    for team, info in state.get("keepers", {}).items():
        keep = info.get("keep")
        if keep and keep["name"] in pool_by_name:
            pool_by_name[keep["name"]]["status"] = "kept"
            pool_by_name[keep["name"]]["pickInfo"] = {"round": 14, "team": team, "label": "Keep"}
        for pname in info.get("protect", []):
            if pname in pool_by_name and pool_by_name[pname]["status"] == "available":
                pool_by_name[pname]["protectedBy"] = team

    keep_row = [None] * n
    protect_row = [None] * n

    for team, info in state.get("keepers", {}).items():
        idx = teams.index(team)
        if info.get("keep"):
            keep_row[idx] = info["keep"]

    # A protect pair resolves the moment either player in it gets drafted --
    # by a rival, or by the owning team itself, live -- at which point the
    # other half is guaranteed to that team at Round 13. Either way, whatever
    # live pick actually happened (by anyone, in whatever round) just stays
    # where it was made; there's no separate "bonus round" mechanic.
    for team, res in state.get("protectResolution", {}).items():
        idx = teams.index(team)
        guaranteed = res.get("guaranteed")
        if guaranteed:
            protect_row[idx] = guaranteed
            # Once a protect player is guaranteed to a team (the other half of
            # the pair got drafted), they're no longer actually up for grabs --
            # reflect that in status so the available-players page stops
            # listing them as "available" (dims them, hides them under the
            # hide-unavailable toggle, excludes them from available counts).
            if guaranteed["name"] in pool_by_name:
                pool_by_name[guaranteed["name"]]["status"] = "protected"
                pool_by_name[guaranteed["name"]]["pickInfo"] = {
                    "round": 13, "team": team, "label": "Protect (R13)",
                }

    for pk in state.get("picks", []):
        idx = teams.index(pk["team"])
        r = pk["round"]
        entry = {"name": pk["name"], "pos": pk["pos"]}
        if r <= live_rounds:
            picks_grid[r - 1][idx] = entry
        if pk["name"] in pool_by_name:
            pool_by_name[pk["name"]]["status"] = "picked"
            pool_by_name[pk["name"]]["pickInfo"] = {"round": r, "team": team_at(teams, idx), "label": f"R{r}"}

    # Tag every filled cell with its player's NFL team so the draft board can
    # show a bye-week badge without needing the whole pool shipped to that
    # page -- covers live picks, keepers, and guaranteed protects alike.
    for row in [*picks_grid, keep_row, protect_row]:
        for entry in row:
            if entry and entry.get("name") and entry["name"] in pool_by_name:
                entry["nflTeam"] = pool_by_name[entry["name"]].get("nflTeam")

    return {
        "teams": teams,
        "myIndex": my_index,
        "liveRounds": live_rounds,
        "picksGrid": picks_grid,
        "keepRow": keep_row,
        "protectRow": protect_row,
        "leagueName": state.get("leagueName", ""),
        "draftDate": state.get("draftDate", ""),
    }


def team_at(teams, idx):
    return teams[idx]


def draft_order_for_round(round_, teams):
    """Snake draft order: odds go 0..n-1, evens go n-1..0."""
    idxs = list(range(len(teams)))
    return idxs if round_ % 2 == 1 else list(reversed(idxs))


def overall_pick(round_, team_index, n):
    """Overall pick number (1-based) for a given round + team index in a
    snake draft of n teams."""
    pos_in_round = (team_index + 1) if (round_ % 2 == 1) else (n - team_index)
    return (round_ - 1) * n + pos_in_round


def next_pick_slot(state):
    """Whichever (round, team) slot is next up, based purely on how many live
    picks have been recorded so far -- i.e. round-robin position len(picks)+1
    through the snake order. Used by the live entry app to default the form
    to 'who's on the clock' without requiring manual round/team selection."""
    teams = state["teams"]
    n = len(teams)
    live_rounds = state["liveRounds"]
    count = len(state.get("picks", []))
    if count >= n * live_rounds:
        return None  # all live rounds full
    round_ = (count // n) + 1
    pos_in_round = count % n
    order = draft_order_for_round(round_, teams)
    team_idx = order[pos_in_round]
    return {"round": round_, "team": teams[team_idx], "teamIndex": team_idx}


def compute_protect_resolution(state, pool):
    """Recomputed from scratch every time from state['picks'] (in the order
    they were entered) rather than incrementally mutated -- this is the same
    logic mock_draft.py simulates, made authoritative here so both the mock
    simulator and the live entry app share one implementation. As soon as
    either player in a team's protect pair gets drafted -- by a rival, or by
    the owning team itself -- the other half is guaranteed to that team at
    Round 13; whatever live pick triggered it just stays where it happened."""
    pool_by_name = {p["name"]: p for p in pool}
    protect_pairs = {
        team: list(info.get("protect", []))
        for team, info in state.get("keepers", {}).items()
    }
    resolved = {team: False for team in protect_pairs}
    result = {team: {"guaranteed": None} for team in protect_pairs}

    for pk in state.get("picks", []):
        name = pk["name"]
        for pair_team, pair in protect_pairs.items():
            if resolved.get(pair_team) or name not in pair:
                continue
            other_name = [x for x in pair if x != name][0]
            other = pool_by_name.get(other_name)
            result[pair_team] = {
                "guaranteed": {"name": other_name, "pos": other["pos"] if other else None},
            }
            resolved[pair_team] = True
    return result


def build_keep_protect_data(state, pool):
    """Per-team Keep/Protect summary for the dedicated tracker page. Reads
    status off `pool` -- which build_derived_state has already annotated with
    'picked' / 'protected' / 'available' -- so this must be called after
    build_derived_state(state, pool) has run against the same pool list."""
    pool_by_name = {p["name"]: p for p in pool}
    rows = []
    for team in state["teams"]:
        info = state.get("keepers", {}).get(team, {})
        keep = info.get("keep")
        if keep and keep.get("name") in pool_by_name:
            # Copy rather than mutate -- keep dicts come straight from
            # state.json and get reused across teams/regenerations.
            keep = {**keep, "nflTeam": pool_by_name[keep["name"]].get("nflTeam")}
        protects = []
        for pname in info.get("protect", []):
            p = pool_by_name.get(pname)
            status = "pending"
            detail = None
            pos = p["pos"] if p else None
            nfl_team = p.get("nflTeam") if p else None
            if p:
                if p.get("status") == "protected":
                    status = "guaranteed"
                elif p.get("status") == "picked":
                    status = "picked"
                    detail = p.get("pickInfo")
            protects.append({"name": pname, "pos": pos, "nflTeam": nfl_team, "status": status, "detail": detail})
        rows.append({"team": team, "keep": keep, "protects": protects})
    resolved = sum(1 for r in rows if any(pp["status"] == "guaranteed" for pp in r["protects"]))
    return {"rows": rows, "resolvedCount": resolved, "totalTeams": len(rows)}


# ---------------------------------------------------------------------------
# Draft grades
#
# Value model: for every LIVE pick (state["picks"] only -- keepers and
# guaranteed protects are pre-set roster slots, not draft-day decisions, so
# they're excluded from scoring and just displayed as reference rows), compare
# the round it was actually taken against the round its overall ADP rank
# (pool.json's `overallRank`, cross-position, n teams/round) implies it
# "should" have gone in: expectedRound = ceil(overallRank / n). A player who
# falls past that round is a value pick (positive score = rounds of value);
# one taken before it is a reach (negative). Averaging that across a team's
# picks -- overall and per position -- gives an honest, fully-automatic grade
# with no subjective input. Players with no ADP match (deep bench, mostly
# K/DEF) are shown but excluded from scoring since there's nothing to compare
# against.
# ---------------------------------------------------------------------------

GRADE_POSITIONS = ["QB", "RB", "WR", "TE"]

# (minimum average value score, letter) checked top-down. Tuned so a
# perfectly-at-ADP team (avg 0) lands a solid B, and grades move roughly a
# third of a letter per quarter-round of average value -- adjust freely once
# real draft results give a feel for the actual spread.
GRADE_BANDS = [
    (1.75, "A+"), (1.15, "A"), (0.65, "A-"),
    (0.30, "B+"), (-0.05, "B"), (-0.35, "B-"),
    (-0.70, "C+"), (-1.15, "C"), (-1.75, "C-"),
]

STEAL_THRESHOLD = 2.0   # rounds of value to earn a "STEAL" tag
REACH_THRESHOLD = -2.0  # rounds of value to earn a "REACH" tag


def letter_grade(avg_value):
    if avg_value is None:
        return "—"
    for threshold, grade in GRADE_BANDS:
        if avg_value >= threshold:
            return grade
    return "D"


def team_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def compute_team_grades(state, pool):
    """Returns {team_name: grade_data} for every team, built purely from
    state["picks"] + pool.json's overallRank -- safe to call at any point
    during the draft (including pre-draft, when picks is empty)."""
    teams = state["teams"]
    n = len(teams)
    live_rounds = state["liveRounds"]
    pool_by_name = {p["name"]: p for p in pool}

    picks_by_team = {t: [] for t in teams}
    for pk in state.get("picks", []):
        picks_by_team.setdefault(pk["team"], []).append(pk)

    grades = {}
    for idx, team in enumerate(teams):
        team_picks = sorted(picks_by_team.get(team, []), key=lambda p: p["round"])
        rows = []
        for pk in team_picks:
            info = pool_by_name.get(pk["name"], {})
            overall_rank = info.get("overallRank")
            value = None
            tag = None
            # K/DEF are excluded from value scoring entirely (not just the
            # positional bars) -- they're forced picks with no meaningful
            # ADP-implied "expected round" in a 1-per-team league, so scoring
            # them just drags every team's grade down by the same amount and
            # tells you nothing about who actually drafted well.
            if overall_rank and pk["pos"] in GRADE_POSITIONS:
                expected_round = math.ceil(overall_rank / n)
                value = pk["round"] - expected_round
                if value >= STEAL_THRESHOLD:
                    tag = "STEAL"
                elif value <= REACH_THRESHOLD:
                    tag = "REACH"
            rows.append({
                "round": pk["round"], "name": pk["name"], "pos": pk["pos"],
                "nflTeam": info.get("nflTeam"), "value": value, "tag": tag,
            })

        # Keeper / guaranteed-protect rows: reference-only, never scored.
        keep = state.get("keepers", {}).get(team, {}).get("keep")
        if keep:
            keep_info = pool_by_name.get(keep["name"], {})
            rows.append({
                "round": 14, "name": keep["name"], "pos": keep["pos"],
                "nflTeam": keep_info.get("nflTeam"), "value": None, "tag": "KEPT",
            })
        guaranteed = state.get("protectResolution", {}).get(team, {}).get("guaranteed")
        # Defensive: a guaranteed protect player should never also show up as
        # one of this team's own live picks (the moment the pair resolves,
        # build_derived_state removes them from the available pool) -- but
        # don't let a data-entry slip during the live draft render a
        # confusing duplicate row if it ever happens anyway.
        if guaranteed and guaranteed["name"] in {r["name"] for r in rows}:
            guaranteed = None
        if guaranteed:
            g_info = pool_by_name.get(guaranteed["name"], {})
            rows.append({
                "round": 13, "name": guaranteed["name"], "pos": guaranteed["pos"],
                "nflTeam": g_info.get("nflTeam"), "value": None, "tag": "PROTECTED",
            })
        rows.sort(key=lambda r: r["round"])

        valued = [r for r in rows if r["value"] is not None]
        avg_value = sum(r["value"] for r in valued) / len(valued) if valued else None

        pos_grades = {}
        for pos in GRADE_POSITIONS:
            pos_valued = [r for r in valued if r["pos"] == pos]
            if pos_valued:
                pos_avg = sum(r["value"] for r in pos_valued) / len(pos_valued)
                # Center a dead-on-ADP team (avg 0) at 50% fill; each round of
                # value/reach moves the bar ~22%, clamped to a readable range.
                pct = max(8, min(100, round(50 + pos_avg * 22)))
                pos_grades[pos] = {"grade": letter_grade(pos_avg), "avg": pos_avg, "pct": pct}
            else:
                pos_grades[pos] = None

        best_value = max(valued, key=lambda r: r["value"], default=None)
        biggest_reach = min(valued, key=lambda r: r["value"], default=None)
        graded_pos = {p: g for p, g in pos_grades.items() if g}
        weakest_pos = min(graded_pos.items(), key=lambda kv: kv[1]["avg"], default=(None, None))

        grades[team] = {
            "team": team,
            "slot": idx + 1,
            "rows": rows,
            "avgValue": avg_value,
            "grade": letter_grade(avg_value),
            "posGrades": pos_grades,
            "bestValue": best_value,
            "biggestReach": biggest_reach,
            "weakestPos": weakest_pos[0],
            "roundsPicked": len(team_picks),
            "liveRounds": live_rounds,
        }
    return grades


# ---------------------------------------------------------------------------
# Post-draft roast commentary -- lighthearted trash talk generated purely
# from each team's own grade data. No external calls (no API key, no
# network dependency, nothing that can fail on draft day) -- just a bank of
# template lines picked with a seed derived from the team's actual picks, so
# the same final roster always gets the same roast instead of it reshuffling
# on every page refresh. Only rendered once a team's draft is fully final
# (see is_final in render_grade_page) so this reads like a recap, not
# commentary on a roster that's still half-built.
# ---------------------------------------------------------------------------

ROAST_OPENERS = {
    "A+": [
        "Somebody actually did their homework — {team} dismantled the ADP chart so thoroughly it should probably be under investigation.",
        "{team} didn't draft a fantasy team, they drafted a war crime. Every bye week in this league owes them an apology.",
    ],
    "A": [
        "{team} drafted like they had insider information nobody else got, and honestly, rude.",
        "Somewhere a scouting department is quietly updating their resume because {team} just made their whole job look unnecessary.",
    ],
    "A-": [
        "{team} played this draft like a chess grandmaster who also reads the waiver wire at 3am. Genuinely annoying to watch.",
    ],
    "B+": [
        "{team} had a good draft. Not a legendary one, not a disaster — just solid, responsible, slightly boring excellence.",
    ],
    "B": [
        "{team} drafted a perfectly fine team that will finish 7-6 and haunt absolutely no one.",
    ],
    "B-": [
        "{team} is living proof you can draft entirely by vibes and still land north of mediocre.",
    ],
    "C+": [
        "{team} took some genuinely questionable swings but somehow it didn't fully implode. Bold strategy.",
    ],
    "C": [
        "{team} drafted like they were filling out a scantron sheet and just started bubbling in C for every question.",
    ],
    "C-": [
        "{team} reached so often this draft should come with a warning label about overexertion.",
    ],
    "D": [
        "{team} didn't draft a fantasy team so much as assemble a cautionary tale for next year's rookies.",
        "Somewhere, an ADP chart is filing a restraining order against {team}.",
    ],
}
ROAST_DEFAULT_OPENERS = ROAST_OPENERS["C"]

ROAST_STEAL_LINES = [
    "Grabbing {name} in Round {round} was either genius or the rest of the league fell asleep at the wheel — either way, {name}'s a walking receipt now.",
    "{name} in Round {round} is the one pick this team will bring up unprompted at every league gathering until 2031.",
    "Somehow {name} fell to Round {round} and this team just quietly pocketed the free value like nothing happened.",
]

ROAST_REACH_LINES = [
    "Taking {name} in Round {round} wasn't a reach, it was a full-extension diving catch for a ball that was never thrown.",
    "{name} in Round {round}? The rest of the league collectively muted their mics so nobody would laugh out loud.",
    "History will remember Round {round}'s {name} pick the way it remembers other great unforced errors.",
]

ROAST_WEAK_POS_LINES = [
    "The {pos} room graded out at a {grade}, which is a nice way of saying it needs a moment of silence.",
    "Somebody's {pos} corps graded {grade} and needs to be handled with the same urgency as a grease fire.",
    "{pos} came in at a {grade} — bold of this team to punt an entire position group and just live with it.",
]

ROAST_CLOSERS = [
    "See everyone at the podium on draft day, where none of this can be quietly edited after the fact.",
    "Print this page. Laminate it. Bring it to the league group chat the second things go sideways.",
    "This has been an entirely fact-based recap and any resemblance to actual draft strategy is purely coincidental.",
    "The algorithm doesn't care about your feelings. Neither will the rest of the league.",
]


def generate_roast(g):
    """Deterministic-per-roster roast paragraph for a team's grade page, or
    None if there's nothing gradeable to work with yet (e.g. every pick was
    K/DEF, which can't happen in practice given the roster slots, but don't
    crash if it somehow does)."""
    if g["avgValue"] is None:
        return None

    seed_key = g["team"] + "|" + "|".join(r["name"] for r in g["rows"])
    rng = random.Random(seed_key)

    opener = rng.choice(ROAST_OPENERS.get(g["grade"], ROAST_DEFAULT_OPENERS)).format(team=g["team"])
    lines = [opener]

    supporting = []
    bv = g["bestValue"]
    if bv and bv["value"] is not None and bv["value"] > 0:
        supporting.append(rng.choice(ROAST_STEAL_LINES).format(name=bv["name"], round=bv["round"]))
    br = g["biggestReach"]
    if br and br["value"] is not None and br["value"] < 0:
        supporting.append(rng.choice(ROAST_REACH_LINES).format(name=br["name"], round=br["round"]))
    if g["weakestPos"]:
        wp = g["weakestPos"]
        wp_grade = g["posGrades"][wp]["grade"]
        supporting.append(rng.choice(ROAST_WEAK_POS_LINES).format(pos=wp, grade=wp_grade))

    if supporting:
        lines.extend(rng.sample(supporting, k=min(2, len(supporting))))

    lines.append(rng.choice(ROAST_CLOSERS))
    return " ".join(lines)

# ---------------------------------------------------------------------------
# AI-generated roast -- an optional upgrade over generate_roast() above. Only
# ever called from an explicit "Generate" action on the /entry page (never
# automatically on a pick/undo), and only ever with the caller already
# holding a real API key -- see draft_app.py's read_anthropic_key(). Results
# are meant to be cached by the caller (state["roasts"][team]) so this never
# runs more than once per team unless someone deliberately re-rolls it.
#
# Deliberately uses stdlib urllib instead of the `anthropic` package -- one
# fewer dependency to install on Web01, and the Messages API is a plain JSON
# POST. generate_ai_roast() must never raise: any failure (missing/bad key,
# network error, timeout, malformed response) returns None so the caller
# falls back to generate_roast(), and a flaky API call can never leave a
# grade page broken or blank.
# ---------------------------------------------------------------------------

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
# Haiku tier -- fast and cheap, plenty for a few sentences of trash talk.
# Override via env var if Anthropic retires/renames this model id later.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
ANTHROPIC_MAX_TOKENS = 220
ANTHROPIC_TIMEOUT_SECONDS = 15

ROAST_SYSTEM_PROMPT = (
    "You write short, funny commentary for a friend group's fantasy football "
    "keeper league (the Ted Brown Memorial League). You'll be given one team's "
    "final draft results: their letter grade, full roster with each pick's "
    "round and value versus ADP consensus, best value pick, biggest reach, and "
    "weakest position group. Write 3-5 sentences of sharp, funny full-roast-"
    "style trash talk about how this team drafted -- brutal one-liners are "
    "encouraged for bad grades. Keep it entirely about fantasy football "
    "performance (reaches, steals, positional weaknesses), never personal, "
    "and never punch at anything outside the draft itself. Output only the "
    "roast paragraph -- no preamble, no sign-off, no quotation marks around it."
)


def _ai_roast_prompt(g):
    """Same underlying facts generate_roast() uses (letter grade, full
    roster with round/value/tag, best value, biggest reach, weakest
    position), formatted as plain text for the model instead of picked from
    a template."""
    lines = [f"Team: {g['team']} (draft slot #{g['slot']})", f"Overall grade: {g['grade']}", "", "Full roster:"]
    for row in g["rows"]:
        if row["value"] is not None:
            val = f"{row['value']:+d} rd vs ADP"
        else:
            val = "not scored"
        tag = f" [{row['tag']}]" if row["tag"] else ""
        lines.append(f"  Round {row['round']}: {row['name']} ({row['pos']}) -- {val}{tag}")
    if g["bestValue"]:
        bv = g["bestValue"]
        lines.append(f"\nBest value pick: {bv['name']}, Round {bv['round']} ({bv['value']:+d} rounds vs ADP)")
    if g["biggestReach"] and g["biggestReach"]["value"] is not None and g["biggestReach"]["value"] < 0:
        br = g["biggestReach"]
        lines.append(f"Biggest reach: {br['name']}, Round {br['round']} ({br['value']:+d} rounds vs ADP)")
    if g["weakestPos"]:
        wp = g["weakestPos"]
        lines.append(f"Weakest position group: {wp} (grade {g['posGrades'][wp]['grade']})")
    return "\n".join(lines)


def generate_ai_roast(g, api_key):
    """Returns a roast paragraph from the Anthropic API, or None on any
    failure. See module note above for why this never raises."""
    if not api_key:
        return None
    try:
        body = json.dumps({
            "model": ANTHROPIC_MODEL,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "system": ROAST_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": _ai_roast_prompt(g)}],
        }).encode("utf-8")
        req = urllib.request.Request(
            ANTHROPIC_API_URL,
            data=body,
            method="POST",
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
                "content-type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=ANTHROPIC_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = "".join(
            block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text"
        ).strip()
        return text or None
    except Exception:  # noqa: BLE001 -- deliberately broad, see module note above
        return None


def render_draft_board(derived, state):
    payload = json.dumps({
        "teams": derived["teams"],
        "myIndex": derived["myIndex"],
        "liveRounds": derived["liveRounds"],
        "picksGrid": derived["picksGrid"],
        "keepRow": derived["keepRow"],
        "protectRow": derived["protectRow"],
        "posColors": POS_COLORS,
        "leagueName": derived["leagueName"],
        "draftDate": derived["draftDate"],
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TBML 2026 Draft Board</title>
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<style>
  :root {{
    --bg: #0f1720; --panel: #16212c; --panel-2: #1c2a37; --border: #2a3a48;
    --text: #e8edf2; --text-dim: #93a4b3; --accent: #3ba7ff; --accent-bg: rgba(59,167,255,0.12);
    --keep: #33c17a; --keep-bg: rgba(51,193,122,0.12); --protect: #f5a623; --protect-bg: rgba(245,166,35,0.12);
    --empty: #4a5b6b;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--text); padding:24px; }}
  .wrap {{ max-width:1400px; margin:0 auto; }}
  header {{ margin-bottom:20px; }}
  h1 {{ font-size:22px; margin:0; font-weight:700; letter-spacing:-0.01em; }}
  .home-link {{ color:inherit; text-decoration:none; }}
  .home-link:hover {{ color:var(--accent); text-decoration:underline; }}
  .header-top {{ display:flex; align-items:baseline; justify-content:space-between; gap:16px; flex-wrap:wrap; }}
  .updated {{ color:var(--text-dim); font-size:12px; white-space:nowrap; }}
  .nav-links {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }}
  .nav-link {{ display:inline-block; font-size:12px; color:var(--accent); text-decoration:none; border:1px solid var(--accent); padding:4px 10px; border-radius:6px; }}
  .board-scroll {{ overflow-x:auto; border:1px solid var(--border); border-radius:12px; background:var(--panel); }}
  table {{ border-collapse:collapse; width:100%; min-width:1200px; }}
  th,td {{ border-bottom:1px solid var(--border); border-right:1px solid var(--border); padding:0; text-align:left; }}
  th:last-child, td:last-child {{ border-right:none; }}
  thead th {{ background:var(--panel-2); padding:10px 12px; font-size:12px; font-weight:700; position:sticky; top:0; z-index:2; }}
  thead th.round-col {{ width:64px; text-align:center; color:var(--text-dim); }}
  tbody th.round-col {{ background:var(--panel-2); color:var(--text-dim); font-size:11px; text-align:center; padding:8px 4px; position:sticky; left:0; line-height:1.3; }}
  tbody tr.reserved.keep-row th.round-col {{ color:var(--keep); font-weight:700; }}
  tbody tr.reserved.protect-row th.round-col {{ color:var(--protect); font-weight:700; }}
  td.pick {{ padding:8px 10px; vertical-align:top; min-width:118px; position:relative; }}
  .pick-num {{ font-size:10px; color:var(--text-dim); font-weight:600; }}
  .pos-filled .pick-num {{ color:rgba(11,15,20,.6); }}
  .pick-player {{ font-size:13px; margin-top:3px; color:var(--empty); }}
  .pick-player.filled {{ color:#0b0f14; font-weight:700; }}
  .pick-player.pending {{ font-style:italic; }}
  .pick-bye {{ position:absolute; top:6px; right:8px; font-size:9.5px; font-weight:700; color:var(--text-dim); }}
  .pos-filled .pick-bye {{ color:rgba(11,15,20,.55); }}
  .legend {{ display:flex; flex-wrap:wrap; gap:14px; margin-top:14px; }}
  .legend-item {{ display:inline-flex; align-items:center; gap:6px; font-size:12px; color:var(--text-dim); }}
  .legend .dot {{ width:9px; height:9px; border-radius:50%; display:inline-block; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="header-top">
      <h1><a class="home-link" href="/" title="Back to TBML draft home">TBML</a> 2026 Draft Board</h1>
      <div class="updated" id="updated"></div>
    </div>
    <div class="nav-links">
      <a class="nav-link" href="draft-players.html">View available players &rarr;</a>
      <a class="nav-link" href="keep-protect.html">Keep/Protect tracker &rarr;</a>
      <a class="nav-link" href="grades/grades.html">Draft Grades &rarr;</a>
    </div>
  </header>

  <div class="board-scroll">
    <table id="board">
      <thead><tr id="board-head"><th class="round-col">Rnd</th></tr></thead>
      <tbody id="board-body"></tbody>
    </table>
  </div>

  <div class="legend" id="legend"></div>
</div>

<script>
const STATE = {payload};

// 2026 NFL bye weeks per team (per NFL.com's 2026 schedule release) -- kept
// in sync by hand with the copy in draft-players.html's player-card modal.
const TEAM_BYE = {{
  "Arizona Cardinals": 14, "Atlanta Falcons": 11, "Baltimore Ravens": 13, "Buffalo Bills": 7,
  "Carolina Panthers": 5, "Chicago Bears": 10, "Cincinnati Bengals": 6, "Cleveland Browns": 11,
  "Dallas Cowboys": 14, "Denver Broncos": 10, "Detroit Lions": 6, "Green Bay Packers": 11,
  "Houston Texans": 8, "Indianapolis Colts": 13, "Jacksonville Jaguars": 7, "Kansas City Chiefs": 5,
  "Las Vegas Raiders": 13, "Los Angeles Chargers": 7, "Los Angeles Rams": 11, "Miami Dolphins": 6,
  "Minnesota Vikings": 6, "New England Patriots": 11, "New Orleans Saints": 8, "New York Giants": 8,
  "New York Jets": 13, "Philadelphia Eagles": 10, "Pittsburgh Steelers": 9, "San Francisco 49ers": 8,
  "Seattle Seahawks": 11, "Tampa Bay Buccaneers": 10, "Tennessee Titans": 9, "Washington Commanders": 7,
}};

function hexIsSet(pos) {{ return STATE.posColors[pos]; }}

function overallPick(round, teamIndex, n) {{
  const posInRound = (round % 2 === 1) ? (teamIndex + 1) : (n - teamIndex);
  return (round - 1) * n + posInRound;
}}

function cellInner(label, entry) {{
  const filled = entry && entry.name;
  const bye = filled && entry.nflTeam ? TEAM_BYE[entry.nflTeam] : null;
  const byeBadge = bye ? `<div class="pick-bye">Bye ${{bye}}</div>` : '';
  return `${{byeBadge}}<div class="pick-num">${{label}}</div><div class="pick-player${{filled ? ' filled' : ' pending'}}">${{filled ? entry.name : (label.startsWith('#') ? '&mdash;' : 'Pending')}}</div>`;
}}

function applyPosStyle(td, entry) {{
  if (entry && entry.name && hexIsSet(entry.pos)) {{
    td.style.background = STATE.posColors[entry.pos];
    td.classList.add('pos-filled');
  }} else {{
    td.classList.add('pos-empty');
  }}
}}

function renderHead() {{
  const tr = document.getElementById('board-head');
  STATE.teams.forEach((t, i) => {{
    const th = document.createElement('th');
    th.className = 'team-col';
    th.textContent = t;
    tr.appendChild(th);
  }});
}}

function renderLegend() {{
  const el = document.getElementById('legend');
  el.innerHTML = Object.entries(STATE.posColors)
    .map(([pos, color]) => `<span class="legend-item"><span class="dot" style="background:${{color}}"></span>${{pos}}</span>`).join('');
}}

function renderBoard() {{
  const tbody = document.getElementById('board-body');
  tbody.innerHTML = '';
  for (let r = 1; r <= STATE.liveRounds; r++) {{
    const tr = document.createElement('tr');
    const th = document.createElement('th');
    th.className = 'round-col';
    th.textContent = r;
    tr.appendChild(th);
    STATE.teams.forEach((team, t) => {{
      const td = document.createElement('td');
      td.className = 'pick';
      const entry = STATE.picksGrid[r-1][t];
      applyPosStyle(td, entry);
      td.innerHTML = cellInner('#' + overallPick(r, t, STATE.teams.length), entry);
      tr.appendChild(td);
    }});
    tbody.appendChild(tr);
  }}
  const reserved = [
    {{ round: 13, cls: 'protect-row', label: 'Protect', data: STATE.protectRow }},
    {{ round: 14, cls: 'keep-row', label: 'Keep', data: STATE.keepRow }},
  ];
  reserved.forEach(rr => {{
    const tr = document.createElement('tr');
    tr.className = 'reserved ' + rr.cls;
    const th = document.createElement('th');
    th.className = 'round-col';
    th.innerHTML = rr.round + '<br>' + rr.label;
    tr.appendChild(th);
    STATE.teams.forEach((team, t) => {{
      const td = document.createElement('td');
      td.className = 'pick';
      applyPosStyle(td, rr.data[t]);
      td.innerHTML = cellInner(rr.label, rr.data[t]);
      tr.appendChild(td);
    }});
    tbody.appendChild(tr);
  }});
}}

// Real-time updates: the live app pushes a notice over Server-Sent Events
// (see draft_app.py's /entry/events) the instant a pick lands, so this page
// reloads in well under a second instead of waiting on a timer. Browsers
// reconnect a dropped EventSource on their own; the slow safety-net poll
// below only matters if SSE can't connect at all (app not deployed yet, or
// briefly down), so the page never goes silently stale either way.
const SAFETY_POLL_SECONDS = 30;
let sseConnected = false;
try {{
  const es = new EventSource('/entry/events');
  es.onopen = () => {{ sseConnected = true; }};
  es.onmessage = () => location.reload();
  es.onerror = () => {{ if (es.readyState === EventSource.CLOSED) sseConnected = false; }};
}} catch (e) {{ /* EventSource unsupported -- safety poll below covers it */ }}
setInterval(() => {{ if (!sseConnected) location.reload(); }}, SAFETY_POLL_SECONDS * 1000);

document.getElementById('updated').textContent = 'Last updated: ' + (STATE.picksGrid.flat().filter(Boolean).length ? (STATE.picksGrid.flat().filter(Boolean).length + ' live picks made') : 'pre-draft, no live picks yet') + ' · live-updating';
renderHead();
renderLegend();
renderBoard();
</script>
<div style="text-align:center; font-size:11px; color:#93a4b3; opacity:0.5; padding:22px 0 6px;">TBML Draft Tool &middot; v{APP_VERSION}</div>
</body>
</html>
"""


def render_available_players(pool, derived):
    payload = json.dumps({
        "pool": pool,
        "posOrder": POS_ORDER,
        "posColors": POS_COLORS,
        "yahooIds": YAHOO_IDS,
    })
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TBML 2026 Available Players</title>
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<style>
  :root {{
    --bg:#0f1720; --panel:#16212c; --panel-2:#1c2a37; --border:#2a3a48;
    --text:#e8edf2; --text-dim:#93a4b3; --accent:#3ba7ff;
    --keep:#33c17a; --protect:#f5a623; --picked:#4a5b6b;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--text); padding:24px; }}
  .wrap {{ max-width:1200px; margin:0 auto; }}
  h1 {{ font-size:22px; margin:0 0 4px 0; font-weight:700; }}
  .home-link {{ color:inherit; text-decoration:none; }}
  .home-link:hover {{ color:var(--accent); text-decoration:underline; }}
  .sub {{ color:var(--text-dim); font-size:13px; margin-bottom:6px; }}
  .nav-links {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; margin-bottom:18px; }}
  .nav-link {{ display:inline-block; font-size:12px; color:var(--accent); text-decoration:none; border:1px solid var(--accent); padding:4px 10px; border-radius:6px; }}
  .search-wrap {{ position:relative; width:100%; max-width:360px; margin-bottom:20px; }}
  #search {{ width:100%; padding:9px 32px 9px 12px; border-radius:8px; border:1px solid var(--border); background:var(--panel); color:var(--text); font-size:14px; box-sizing:border-box; }}
  #search::placeholder {{ color:var(--text-dim); }}
  #searchClear {{ display:none; position:absolute; right:6px; top:50%; transform:translateY(-50%); width:22px; height:22px; border:none; border-radius:50%; background:transparent; color:var(--text-dim); font-size:16px; line-height:1; cursor:pointer; align-items:center; justify-content:center; }}
  #searchClear:hover {{ background:var(--panel-2); color:var(--text); }}
  #searchClear.visible {{ display:flex; }}
  .pos-section {{ margin-bottom:14px; border:1px solid var(--border); border-radius:10px; background:var(--panel); overflow:hidden; }}
  .pos-head {{ display:flex; align-items:center; gap:10px; padding:12px 14px; cursor:pointer; user-select:none; }}
  .pos-head:hover {{ background:var(--panel-2); }}
  .chevron {{ font-size:11px; color:var(--text-dim); transition:transform 0.15s ease; margin-left:auto; }}
  .pos-section.collapsed .chevron {{ transform:rotate(-90deg); }}
  .pos-badge {{ font-size:12px; font-weight:800; padding:3px 10px; border-radius:6px; color:#0b0f14; }}
  .pos-count {{ font-size:12px; color:var(--text-dim); }}
  .player-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(230px,1fr)); gap:8px; padding:0 14px 14px; }}
  .pos-section.collapsed .player-grid {{ display:none; }}
  .player-row {{ background:var(--panel-2); border:1px solid var(--border); border-radius:8px; padding:8px 10px; display:flex; flex-direction:column; gap:2px; }}
  .player-row.unavailable {{ opacity:0.42; }}
  .player-name {{ font-size:13.5px; font-weight:600; display:flex; align-items:baseline; gap:6px; }}
  .player-rank {{ font-size:10.5px; color:var(--text-dim); font-weight:700; }}
  .player-link {{ color:var(--text); text-decoration:none; }}
  .player-link:hover {{ color:var(--accent); text-decoration:underline; }}
  .player-meta {{ font-size:11px; color:var(--text-dim); display:flex; gap:6px; flex-wrap:wrap; align-items:center; }}
  .badge {{ font-size:9.5px; text-transform:uppercase; letter-spacing:.03em; font-weight:800; padding:1px 6px; border-radius:4px; }}
  .badge.kept {{ background:rgba(51,193,122,0.15); color:var(--keep); }}
  .badge.picked {{ background:rgba(74,91,107,0.3); color:var(--text-dim); }}
  .badge.protected {{ background:rgba(245,166,35,0.15); color:var(--protect); }}
  .strike {{ text-decoration:line-through; }}
  .toggle-all {{ font-size:12px; color:var(--accent); background:none; border:1px solid var(--accent); border-radius:6px; padding:4px 10px; cursor:pointer; margin-left:10px; }}
  .hide-toggle {{ font-size:12px; color:var(--text-dim); background:none; border:1px solid var(--border); border-radius:6px; padding:4px 10px; cursor:pointer; margin-bottom:14px; }}
  .hide-toggle.active {{ color:var(--protect); border-color:var(--protect); background:rgba(245,166,35,0.1); }}
  .tabs {{ display:flex; align-items:center; gap:8px; margin:14px 0 18px; }}
  .tab-btn {{ font-size:13px; font-weight:600; color:var(--text-dim); background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:8px 16px; cursor:pointer; }}
  .tab-btn.active {{ color:var(--accent); border-color:var(--accent); background:var(--accent-bg,rgba(59,167,255,0.1)); }}
  .tab-panel {{ display:none; }}
  .tab-panel.active {{ display:block; }}
  .overall-rank {{ font-size:10.5px; color:var(--accent); font-weight:700; }}
  .overall-table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--border); border-radius:10px; overflow:hidden; }}
  .overall-table th {{ text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:var(--text-dim); background:var(--panel-2); padding:10px 12px; position:sticky; top:0; }}
  .overall-table td {{ padding:9px 12px; border-top:1px solid var(--border); font-size:13.5px; vertical-align:middle; }}
  .overall-table tr.unavailable td {{ opacity:0.42; }}
  .overall-num {{ font-weight:800; color:var(--accent); width:44px; }}
  .overall-table .pos-badge {{ font-size:10.5px; padding:2px 7px; }}
  .modal-overlay {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,0.55); align-items:center; justify-content:center; z-index:1000; padding:20px; }}
  .modal-overlay.open {{ display:flex; }}
  .modal-panel {{ background:var(--panel); border:1px solid var(--border); border-radius:16px; max-width:420px; width:100%; position:relative; box-shadow:0 12px 40px rgba(0,0,0,0.5); overflow:hidden; }}
  .modal-close {{ position:absolute; top:12px; right:12px; width:30px; height:30px; border-radius:50%; border:none; background:rgba(0,0,0,0.35); backdrop-filter:blur(4px); color:#fff; font-size:18px; cursor:pointer; line-height:1; z-index:2; }}
  .modal-close:hover {{ background:rgba(0,0,0,0.55); }}
  .modal-header {{ position:relative; padding:20px 52px 18px 20px; display:flex; align-items:center; gap:14px; color:#fff; overflow:hidden; }}
  .modal-header-logo {{ position:absolute; top:50%; right:-10px; transform:translateY(-50%); width:130px; height:130px; object-fit:contain; opacity:0.55; pointer-events:none; filter:drop-shadow(0 0 10px rgba(0,0,0,0.35)); }}
  .modal-header > *:not(.modal-header-logo) {{ position:relative; z-index:1; }}
  .modal-avatar {{ flex-shrink:0; width:64px; height:64px; border-radius:50%; background:rgba(255,255,255,0.16); border:2px solid rgba(255,255,255,0.35); display:flex; align-items:center; justify-content:center; font-size:21px; font-weight:800; letter-spacing:.02em; overflow:hidden; }}
  .modal-avatar img {{ width:100%; height:100%; object-fit:cover; border-radius:50%; }}
  .modal-chip-row {{ display:flex; align-items:center; gap:6px; flex-wrap:wrap; }}
  .modal-chip {{ display:inline-block; font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; padding:2px 8px; border-radius:5px; background:rgba(0,0,0,0.3); margin-bottom:6px; }}
  .injury-chip {{ display:inline-block; font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; padding:2px 8px; border-radius:5px; margin-bottom:6px; }}
  .injury-questionable {{ background:#f5c423; color:#241a00; }}
  .injury-probable {{ background:#4cbb79; color:#0c2016; }}
  .injury-doubtful {{ background:#e07b1a; color:#fff; }}
  .injury-out, .injury-suspended {{ background:#d13b3b; color:#fff; }}
  .injury-ir, .injury-pup {{ background:#7a1f1f; color:#fff; }}
  .row-injury-chip {{ display:none; font-size:9px; font-weight:800; text-transform:uppercase; letter-spacing:.04em; padding:1px 6px; border-radius:4px; margin-left:6px; vertical-align:middle; }}
  .modal-header-name {{ font-size:19px; font-weight:800; line-height:1.15; }}
  .modal-teambar {{ background:var(--panel-2); padding:9px 20px; display:flex; align-items:baseline; justify-content:space-between; gap:10px; border-bottom:1px solid var(--border); }}
  .modal-team-name {{ font-weight:700; font-size:13px; letter-spacing:.01em; }}
  .modal-team-detail {{ font-size:11.5px; color:var(--text-dim); }}
  .modal-body-content {{ padding:16px 20px 20px; }}
  .stat-pills {{ display:flex; gap:8px; margin-bottom:14px; }}
  .stat-pill {{ flex:1; background:var(--panel-2); border:1px solid var(--border); border-radius:10px; padding:9px 6px; text-align:center; }}
  .stat-pill .label {{ font-size:9px; text-transform:uppercase; letter-spacing:.05em; color:var(--text-dim); margin-bottom:4px; }}
  .stat-pill .value {{ font-size:14.5px; font-weight:800; }}
  .bio-pills .stat-pill .value {{ font-size:13px; }}
  .modal-college {{ font-size:11.5px; color:var(--text-dim); text-align:center; margin:-4px 0 12px; }}
  .modal-status-detail {{ font-size:12.5px; color:var(--text-dim); text-align:center; margin-bottom:14px; }}
  .modal-link {{ display:block; text-align:center; font-size:13px; color:var(--accent); text-decoration:none; border:1px solid var(--accent); padding:9px 14px; border-radius:8px; }}
  .modal-link:hover {{ background:rgba(59,167,255,0.1); }}
</style>
</head>
<body>
<div class="wrap">
  <h1><a class="home-link" href="/" title="Back to TBML draft home">TBML</a> 2026 Available Players</h1>
  <div class="nav-links">
    <a class="nav-link" href="draft-board.html">&larr; Back to draft board</a>
    <a class="nav-link" href="keep-protect.html">Keep/Protect tracker &rarr;</a>
    <a class="nav-link" href="grades/grades.html">Draft Grades &rarr;</a>
  </div>

  <div class="tabs">
    <button class="tab-btn active" id="tabBtnByPos">By Position</button>
    <button class="tab-btn" id="tabBtnOverall">Overall Ranking</button>
  </div>

  <button class="toggle-all" id="toggleAll">Collapse all</button>
  <br>
  <div class="search-wrap">
    <input id="search" type="text" placeholder="Filter by player or team...">
    <button id="searchClear" type="button" aria-label="Clear search">&times;</button>
  </div>

  <div class="tab-panel active" id="panelByPos">
    <br>
    <button class="hide-toggle" id="hideToggleByPos">Hide unavailable</button>
    <div id="sections"></div>
  </div>
  <div class="tab-panel" id="panelOverall">
    <br>
    <button class="hide-toggle" id="hideToggleOverall">Hide unavailable</button>
    <table class="overall-table">
      <thead><tr><th>Ovr</th><th>Player</th><th>Pos</th><th>Team</th><th>Status</th></tr></thead>
      <tbody id="overallBody"></tbody>
    </table>
  </div>

  <div class="modal-overlay" id="modalOverlay">
    <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="modalName">
      <button class="modal-close" id="modalClose" aria-label="Close">&times;</button>
      <div id="modalBody"></div>
    </div>
  </div>
</div>

<script>
const DATA = {payload};

// Collapse state persists across re-renders (e.g. while typing in search).
const collapsedState = {{}};

function statusBadges(p) {{
  let html = '';
  if (p.status === 'kept') html += `<span class="badge kept">Kept &middot; ${{p.pickInfo.team}}</span>`;
  if (p.status === 'picked') html += `<span class="badge picked">${{p.pickInfo.label}} &middot; ${{p.pickInfo.team}}</span>`;
  if (p.status === 'protected') html += `<span class="badge protected">${{p.pickInfo.label}} &middot; ${{p.pickInfo.team}}</span>`;
  else if (p.protectedBy) html += `<span class="badge protected">Protect &middot; ${{p.protectedBy}}</span>`;
  return html;
}}

function yahooSearchUrl(name) {{
  return `https://sports.yahoo.com/search?p=${{encodeURIComponent(name + ' NFL')}}`;
}}

function yahooPlayerUrl(p) {{
  const id = DATA.yahooIds[p.name];
  return id ? `https://sports.yahoo.com/nfl/players/${{id}}/` : yahooSearchUrl(p.name);
}}

// Used only for the data-name attribute on player links, so a name with a
// quote or ampersand in it (there aren't any right now, but don't assume)
// can't break the surrounding HTML.
function escAttr(s) {{
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}}

function statusLine(p) {{
  if (p.status === 'kept') return `Kept by ${{p.pickInfo.team}}`;
  if (p.status === 'picked') return `Picked ${{p.pickInfo.label}} by ${{p.pickInfo.team}}`;
  if (p.status === 'protected') return `Guaranteed ${{p.pickInfo.label}} to ${{p.pickInfo.team}}`;
  if (p.protectedBy) return `Available &mdash; protected by ${{p.protectedBy}}`;
  return 'Available';
}}

function statusChip(p) {{
  if (p.status === 'kept') return 'Kept';
  if (p.status === 'picked') return 'Picked';
  if (p.status === 'protected') return 'Guaranteed R13';
  return 'Available';
}}

// Colors + logo URLs sourced from nflverse's public teams_colors_logos
// dataset (github.com/nflverse/nfldata), which mirrors ESPN's team brand
// colors and hosts logo images at ESPN's public CDN -- not an API key or
// auth of any kind, just static image URLs. Every NFL team is covered so
// there's always a real gradient + logo; TEAM_STYLE_FALLBACK only kicks in
// if a pool entry's nflTeam string somehow doesn't match one of these.
const TEAM_STYLE = {{
  "Arizona Cardinals": {{primary:"#97233F", secondary:"#000000", abbr:"ARI", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/ari.png"}},
  "Atlanta Falcons": {{primary:"#A71930", secondary:"#000000", abbr:"ATL", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/atl.png"}},
  "Baltimore Ravens": {{primary:"#241773", secondary:"#9E7C0C", abbr:"BAL", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/bal.png"}},
  "Buffalo Bills": {{primary:"#00338D", secondary:"#C60C30", abbr:"BUF", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/buf.png"}},
  "Carolina Panthers": {{primary:"#0085CA", secondary:"#000000", abbr:"CAR", logo:"https://a.espncdn.com/i/teamlogos/nfl/500-dark/car.png"}},
  "Chicago Bears": {{primary:"#0B162A", secondary:"#E64100", abbr:"CHI", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/chi.png"}},
  "Cincinnati Bengals": {{primary:"#FB4F14", secondary:"#000000", abbr:"CIN", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/cin.png"}},
  "Cleveland Browns": {{primary:"#FF3C00", secondary:"#311D00", abbr:"CLE", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/cle.png"}},
  "Dallas Cowboys": {{primary:"#002244", secondary:"#B0B7BC", abbr:"DAL", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/dal.png"}},
  "Denver Broncos": {{primary:"#002244", secondary:"#FB4F14", abbr:"DEN", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/den.png"}},
  "Detroit Lions": {{primary:"#0076B6", secondary:"#B0B7BC", abbr:"DET", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/det.png"}},
  "Green Bay Packers": {{primary:"#203731", secondary:"#FFB612", abbr:"GB", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/gb.png"}},
  "Houston Texans": {{primary:"#03202F", secondary:"#A71930", abbr:"HOU", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/hou.png"}},
  "Indianapolis Colts": {{primary:"#002C5F", secondary:"#a5acaf", abbr:"IND", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/ind.png"}},
  "Jacksonville Jaguars": {{primary:"#006778", secondary:"#000000", abbr:"JAX", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/jax.png"}},
  "Kansas City Chiefs": {{primary:"#E31837", secondary:"#FFB612", abbr:"KC", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/kc.png"}},
  "Las Vegas Raiders": {{primary:"#000000", secondary:"#A5ACAF", abbr:"LV", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/lv.png"}},
  "Los Angeles Chargers": {{primary:"#007BC7", secondary:"#ffc20e", abbr:"LAC", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/lac.png"}},
  "Los Angeles Rams": {{primary:"#003594", secondary:"#FFD100", abbr:"LAR", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/lar.png"}},
  "Miami Dolphins": {{primary:"#008E97", secondary:"#F58220", abbr:"MIA", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/mia.png"}},
  "Minnesota Vikings": {{primary:"#4F2683", secondary:"#FFC62F", abbr:"MIN", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/min.png"}},
  "New England Patriots": {{primary:"#002244", secondary:"#C60C30", abbr:"NE", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/ne.png"}},
  "New Orleans Saints": {{primary:"#D3BC8D", secondary:"#000000", abbr:"NO", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/no.png"}},
  "New York Giants": {{primary:"#0B2265", secondary:"#A71930", abbr:"NYG", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png"}},
  "New York Jets": {{primary:"#003F2D", secondary:"#000000", abbr:"NYJ", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png"}},
  "Philadelphia Eagles": {{primary:"#004C54", secondary:"#A5ACAF", abbr:"PHI", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/phi.png"}},
  "Pittsburgh Steelers": {{primary:"#000000", secondary:"#FFB612", abbr:"PIT", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/pit.png"}},
  "San Francisco 49ers": {{primary:"#AA0000", secondary:"#B3995D", abbr:"SF", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/sf.png"}},
  "Seattle Seahawks": {{primary:"#002244", secondary:"#69be28", abbr:"SEA", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/sea.png"}},
  "Tampa Bay Buccaneers": {{primary:"#A71930", secondary:"#322F2B", abbr:"TB", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/tb.png"}},
  "Tennessee Titans": {{primary:"#4495D2", secondary:"#D50A0A", abbr:"TEN", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/ten.png"}},
  "Washington Commanders": {{primary:"#5A1414", secondary:"#FFB612", abbr:"WSH", logo:"https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png"}},
}};
const TEAM_STYLE_FALLBACK = {{primary:"#2a3a48", secondary:"#16212c", abbr:"", logo:null}};

// 2026 NFL bye weeks per team (per NFL.com's 2026 schedule release). Byes run
// Week 5-14, skipping Week 12 (Thanksgiving, full slate). Team-level, so
// applies the same to a DEF pool entry as to any of that team's players.
const TEAM_BYE = {{
  "Arizona Cardinals": 14, "Atlanta Falcons": 11, "Baltimore Ravens": 13, "Buffalo Bills": 7,
  "Carolina Panthers": 5, "Chicago Bears": 10, "Cincinnati Bengals": 6, "Cleveland Browns": 11,
  "Dallas Cowboys": 14, "Denver Broncos": 10, "Detroit Lions": 6, "Green Bay Packers": 11,
  "Houston Texans": 8, "Indianapolis Colts": 13, "Jacksonville Jaguars": 7, "Kansas City Chiefs": 5,
  "Las Vegas Raiders": 13, "Los Angeles Chargers": 7, "Los Angeles Rams": 11, "Miami Dolphins": 6,
  "Minnesota Vikings": 6, "New England Patriots": 11, "New Orleans Saints": 8, "New York Giants": 8,
  "New York Jets": 13, "Philadelphia Eagles": 10, "Pittsburgh Steelers": 9, "San Francisco 49ers": 8,
  "Seattle Seahawks": 11, "Tampa Bay Buccaneers": 10, "Tennessee Titans": 9, "Washington Commanders": 7,
}};

function initials(name) {{
  const parts = name.split(' ').filter(Boolean);
  const first = parts[0] ? parts[0][0] : '';
  const last = parts.length > 1 ? parts[parts.length - 1][0] : '';
  return (first + last).toUpperCase();
}}

// --- Sleeper bio/photo lookup ---------------------------------------------
// Sleeper's player API (api.sleeper.app) is public/no-auth but only offers a
// single "give me every NFL player" endpoint -- ~5MB, no per-player lookup.
// Their own docs say not to call it more than once/day, so this fetches it
// at most that often, trims it down to just what the modal needs, and caches
// the trimmed result in localStorage (this is a real deployed site, not a
// Claude.ai artifact, so localStorage is fine to use here). Everything here
// is wrapped so a failure -- offline, CORS, a name that doesn't match, no
// cached data yet -- just means the modal keeps showing today's initials
// avatar and skips the bio row. Nothing about the existing modal depends on
// this succeeding.
const SLEEPER_CACHE_KEY = 'tbmlSleeperPlayers_v2'; // bump this whenever the trimmed payload's fields change, so a code update invalidates old cached data immediately instead of silently missing new fields for up to SLEEPER_MAX_AGE_MS
const SLEEPER_MAX_AGE_MS = 20 * 60 * 60 * 1000; // under Sleeper's "once/day" guidance
let sleeperDataPromise = null;

function normalizeName(name) {{
  return String(name).toLowerCase().replace(/[^a-z0-9]/g, '');
}}

async function fetchSleeperPlayers() {{
  const res = await fetch('https://api.sleeper.app/v1/players/nfl');
  if (!res.ok) throw new Error('Sleeper fetch failed: ' + res.status);
  const raw = await res.json();
  const trimmed = {{}};
  for (const id in raw) {{
    const pl = raw[id];
    if (!pl || !pl.search_full_name) continue;
    trimmed[pl.search_full_name] = {{
      id: pl.player_id,
      age: pl.age || null,
      height: pl.height || null,
      weight: pl.weight || null,
      exp: (pl.years_exp === undefined || pl.years_exp === null) ? null : pl.years_exp,
      injuryStatus: pl.injury_status || null,
      college: pl.college || null,
    }};
  }}
  return trimmed;
}}

// Loads once per page (in-memory), refreshed from network at most once/day
// (localStorage). Returns {{}} rather than throwing if anything goes wrong,
// so callers never need their own try/catch.
function getSleeperData() {{
  if (sleeperDataPromise) return sleeperDataPromise;
  sleeperDataPromise = (async () => {{
    let cached = null;
    try {{ cached = JSON.parse(localStorage.getItem(SLEEPER_CACHE_KEY)); }} catch (e) {{ /* corrupt/missing cache -- refetch */ }}
    if (cached && cached.fetchedAt && (Date.now() - cached.fetchedAt) < SLEEPER_MAX_AGE_MS && cached.players) {{
      return cached.players;
    }}
    try {{
      const players = await fetchSleeperPlayers();
      try {{ localStorage.setItem(SLEEPER_CACHE_KEY, JSON.stringify({{fetchedAt: Date.now(), players}})); }} catch (e) {{ /* storage full/unavailable -- still usable this page load */ }}
      return players;
    }} catch (e) {{
      return (cached && cached.players) || {{}}; // network/CORS failure -- fall back to stale cache if we have one
    }}
  }})();
  return sleeperDataPromise;
}}

function formatHeight(totalInches) {{
  const n = parseInt(totalInches, 10);
  if (!n) return null;
  return `${{Math.floor(n / 12)}}'${{n % 12}}"`;
}}

function formatExp(years) {{
  if (years === null || years === undefined) return null;
  return years === 0 ? 'Rookie' : `${{years}} yr${{years === 1 ? '' : 's'}}`;
}}

// Rough severity ordering for color: Probable (mildest) -> IR/PUP (most
// severe). An unrecognized future status Sleeper adds falls back to the
// "Questionable" (yellow, least alarming-but-still-flagged) styling rather
// than being hidden or defaulting to something scarier than warranted.
function injuryBadgeClass(status) {{
  const map = {{
    Probable: 'injury-probable',
    Questionable: 'injury-questionable',
    Doubtful: 'injury-doubtful',
    Out: 'injury-out',
    Suspended: 'injury-suspended',
    IR: 'injury-ir',
    PUP: 'injury-pup',
  }};
  return map[status] || 'injury-questionable';
}}

// Populated once the page-load Sleeper fetch resolves (see the bottom of
// this script); stays null until then, so applyInjuryBadges() is a safe
// no-op if it's called before the data arrives -- the .then() callback that
// sets this also re-runs it once, so nothing is stuck permanently blank.
let sleeperDataCache = null;

function applyInjuryBadges() {{
  if (!sleeperDataCache) return;
  document.querySelectorAll('.row-injury-chip').forEach(el => {{
    const info = sleeperDataCache[normalizeName(el.dataset.name)];
    if (info && info.injuryStatus) {{
      el.textContent = info.injuryStatus;
      el.className = 'row-injury-chip ' + injuryBadgeClass(info.injuryStatus);
      el.style.display = 'inline-block';
    }}
  }});
}}

let currentModalPlayer = null;

function openPlayerModal(name) {{
  const p = DATA.pool.find(x => x.name === name);
  if (!p) return;
  currentModalPlayer = name;
  const team = TEAM_STYLE[p.nflTeam] || TEAM_STYLE_FALLBACK;
  const bye = TEAM_BYE[p.nflTeam] || null;
  const rankLabel = p.rank ? `${{p.pos}}${{p.rank}}` : '&mdash;';
  const ovrLabel = p.overallRank ? `#${{p.overallRank}}` : '&mdash;';
  document.getElementById('modalBody').innerHTML = `
    <div class="modal-header" style="background:linear-gradient(rgba(15,23,32,0.55), rgba(15,23,32,0.55)), linear-gradient(135deg, ${{team.primary}}, ${{team.secondary}})">
      ${{team.logo ? `<img class="modal-header-logo" src="${{team.logo}}" alt="" onerror="this.remove()">` : ''}}
      <div class="modal-avatar" id="modalAvatar">${{initials(p.name)}}</div>
      <div>
        <div class="modal-chip-row">
          <div class="modal-chip">${{statusChip(p)}}</div>
          <span class="injury-chip" id="modalInjuryChip" style="display:none;"></span>
        </div>
        <div class="modal-header-name" id="modalName">${{p.name}}</div>
      </div>
    </div>
    <div class="modal-teambar">
      <span class="modal-team-name">${{p.nflTeam}}</span>
      <span class="modal-team-detail">${{p.pos}}${{team.abbr ? ' &middot; ' + team.abbr : ''}}${{bye ? ' &middot; Bye ' + bye : ''}}</span>
    </div>
    <div class="modal-body-content">
      <div class="stat-pills">
        <div class="stat-pill"><div class="label">Pos rank</div><div class="value">${{rankLabel}}</div></div>
        <div class="stat-pill"><div class="label">Overall</div><div class="value">${{ovrLabel}}</div></div>
      </div>
      <div class="stat-pills bio-pills" id="bioPills" style="display:none;"></div>
      <div class="modal-college" id="modalCollege" style="display:none;"></div>
      <div class="modal-status-detail">${{statusLine(p)}}</div>
      <a class="modal-link" href="${{yahooPlayerUrl(p)}}" target="_blank" rel="noopener">View full profile on Yahoo &#8599;</a>
      <a class="modal-link" id="modalSleeperLink" href="#" target="_blank" rel="noopener" style="display:none; margin-top:8px;">View on Sleeper &#8599;</a>
    </div>
  `;
  document.getElementById('modalOverlay').classList.add('open');

  // Team defenses don't have a meaningful bio -- skip the lookup entirely.
  if (p.pos === 'DEF') return;

  getSleeperData().then(players => {{
    if (currentModalPlayer !== name) return; // modal moved on to someone else (or closed) while this was loading
    const info = players[normalizeName(p.name)];
    if (!info) return; // no match -- initials avatar + no bio row stays as-is, silently

    if (info.id) {{
      const avatarEl = document.getElementById('modalAvatar');
      if (avatarEl) {{
        // data-fallback (not an inline JSON literal) so the initials string
        // can't collide with the onerror attribute's own quoting -- a name
        // producing a stray `"` there would otherwise break the markup.
        avatarEl.innerHTML = `<img src="https://sleepercdn.com/content/nfl/players/${{info.id}}.jpg" alt="" data-fallback="${{escAttr(initials(p.name))}}" onerror="this.parentElement.textContent=this.dataset.fallback">`;
      }}
      const sleeperLinkEl = document.getElementById('modalSleeperLink');
      if (sleeperLinkEl) {{
        sleeperLinkEl.href = `https://sleeper.com/nfl/players/${{info.id}}`;
        sleeperLinkEl.style.display = '';
      }}
    }}

    const bioStats = [
      ['Age', info.age || null],
      ['Height', formatHeight(info.height)],
      ['Weight', info.weight ? `${{info.weight}} lbs` : null],
      ['Exp', formatExp(info.exp)],
    ].filter(([, v]) => v);
    if (bioStats.length) {{
      const bioEl = document.getElementById('bioPills');
      if (bioEl) {{
        bioEl.innerHTML = bioStats.map(([label, value]) =>
          `<div class="stat-pill"><div class="label">${{label}}</div><div class="value">${{value}}</div></div>`
        ).join('');
        bioEl.style.display = '';
      }}
    }}

    if (info.injuryStatus) {{
      const injuryEl = document.getElementById('modalInjuryChip');
      if (injuryEl) {{
        injuryEl.textContent = info.injuryStatus;
        injuryEl.className = 'injury-chip ' + injuryBadgeClass(info.injuryStatus);
        injuryEl.style.display = '';
      }}
    }}

    if (info.college) {{
      const collegeEl = document.getElementById('modalCollege');
      if (collegeEl) {{
        collegeEl.textContent = info.college;
        collegeEl.style.display = '';
      }}
    }}
  }}); // deliberately no .catch() -- getSleeperData() never rejects, it resolves to {{}} on any failure
}}

function closePlayerModal() {{
  currentModalPlayer = null;
  document.getElementById('modalOverlay').classList.remove('open');
}}

document.getElementById('modalClose').addEventListener('click', closePlayerModal);
document.getElementById('modalOverlay').addEventListener('click', (e) => {{
  if (e.target.id === 'modalOverlay') closePlayerModal();
}});
document.addEventListener('keydown', (e) => {{
  if (e.key === 'Escape') closePlayerModal();
}});
// Delegated so it keeps working across every re-render (search, collapse,
// tab switch) without needing to re-attach a listener per row.
document.addEventListener('click', (e) => {{
  const link = e.target.closest('.player-link');
  if (!link) return;
  e.preventDefault();
  openPlayerModal(link.dataset.name);
}});

function render(filterText) {{
  const el = document.getElementById('sections');
  el.innerHTML = '';
  const f = (filterText || '').trim().toLowerCase();

  DATA.posOrder.forEach(pos => {{
    const matchingSearch = DATA.pool
      .filter(p => p.pos === pos)
      .filter(p => !f || p.name.toLowerCase().includes(f) || p.nflTeam.toLowerCase().includes(f));
    const players = matchingSearch.filter(p => !hideUnavailable || p.status === 'available');
    if (!matchingSearch.length) return;

    const available = matchingSearch.filter(p => p.status === 'available').length;
    const isCollapsed = !!collapsedState[pos];

    const section = document.createElement('div');
    section.className = 'pos-section' + (isCollapsed ? ' collapsed' : '');
    const head = document.createElement('div');
    head.className = 'pos-head';
    head.innerHTML = `
      <span class="pos-badge" style="background:${{DATA.posColors[pos]}}">${{pos}}</span>
      <span class="pos-count">${{available}} available / ${{matchingSearch.length}} total</span>
      <span class="chevron">&#9660;</span>
    `;
    head.addEventListener('click', () => {{
      collapsedState[pos] = !collapsedState[pos];
      render(document.getElementById('search').value);
    }});
    section.appendChild(head);

    const grid = document.createElement('div');
    grid.className = 'player-grid';
    players.forEach(p => {{
      const row = document.createElement('div');
      row.className = 'player-row' + (p.status !== 'available' ? ' unavailable' : '');
      const rankLabel = p.rank ? `${{p.pos}}${{p.rank}}` : '&mdash;';
      const ovrLabel = p.overallRank ? `Ovr ${{p.overallRank}}` : '';
      const rowBye = TEAM_BYE[p.nflTeam] || null;
      row.innerHTML = `
        <div class="player-name${{p.status !== 'available' ? ' strike' : ''}}"><span class="player-rank">${{rankLabel}}</span><a class="player-link" href="#" data-name="${{escAttr(p.name)}}">${{p.name}}</a><span class="row-injury-chip" data-name="${{escAttr(p.name)}}"></span></div>
        <div class="player-meta">${{ovrLabel ? `<span class="overall-rank">${{ovrLabel}}</span>` : ''}}<span>${{p.nflTeam}}${{rowBye ? ' &middot; Bye ' + rowBye : ''}}</span>${{statusBadges(p)}}</div>
      `;
      grid.appendChild(row);
    }});
    section.appendChild(grid);
    el.appendChild(section);
  }});
  applyInjuryBadges();
}}

function renderOverall(filterText) {{
  const tbody = document.getElementById('overallBody');
  tbody.innerHTML = '';
  const f = (filterText || '').trim().toLowerCase();

  const ranked = DATA.pool
    .filter(p => !f || p.name.toLowerCase().includes(f) || p.nflTeam.toLowerCase().includes(f))
    .filter(p => !hideUnavailable || p.status === 'available')
    .slice()
    .sort((a, b) => {{
      const ar = a.overallRank == null ? Infinity : a.overallRank;
      const br = b.overallRank == null ? Infinity : b.overallRank;
      if (ar !== br) return ar - br;
      // Unranked players (no ADP match): fall back to position rank so the
      // list still ends in a sensible order instead of arbitrary JSON order.
      return (a.rank || 9999) - (b.rank || 9999);
    }});

  ranked.forEach(p => {{
    const tr = document.createElement('tr');
    tr.className = p.status !== 'available' ? 'unavailable' : '';
    const rowBye = TEAM_BYE[p.nflTeam] || null;
    tr.innerHTML = `
      <td class="overall-num">${{p.overallRank ? '#' + p.overallRank : '&mdash;'}}</td>
      <td><a class="player-link${{p.status !== 'available' ? ' strike' : ''}}" href="#" data-name="${{escAttr(p.name)}}">${{p.name}}</a><span class="row-injury-chip" data-name="${{escAttr(p.name)}}"></span></td>
      <td><span class="pos-badge" style="background:${{DATA.posColors[p.pos]}}">${{p.pos}}</span></td>
      <td>${{p.nflTeam}}${{rowBye ? ' &middot; Bye ' + rowBye : ''}}</td>
      <td>${{statusBadges(p)}}</td>
    `;
    tbody.appendChild(tr);
  }});
  applyInjuryBadges();
}}

function renderActiveTab() {{
  const q = document.getElementById('search').value;
  document.getElementById('searchClear').classList.toggle('visible', q.length > 0);
  if (activeTab === 'overall') renderOverall(q); else render(q);
}}

// Auto-refresh reloads the whole page, which would normally reset which tab
// you're on and whether "hide unavailable" is active. To survive that, both
// get stashed in the URL hash (not localStorage -- keeps this a plain static
// file with no storage APIs) and restored on load instead of defaulting.
const hashParams = new URLSearchParams(location.hash.slice(1));
let activeTab = hashParams.get('tab') === 'overall' ? 'overall' : 'byPos';
let hideUnavailable = hashParams.get('hide') === '1';

function syncHash() {{
  history.replaceState(null, '', '#tab=' + activeTab + '&hide=' + (hideUnavailable ? '1' : '0'));
}}

document.getElementById('search').addEventListener('input', renderActiveTab);

document.getElementById('searchClear').addEventListener('click', () => {{
  const input = document.getElementById('search');
  input.value = '';
  input.focus();
  renderActiveTab();
}});

document.getElementById('toggleAll').addEventListener('click', () => {{
  const anyExpanded = DATA.posOrder.some(pos => !collapsedState[pos]);
  DATA.posOrder.forEach(pos => {{ collapsedState[pos] = anyExpanded; }});
  document.getElementById('toggleAll').textContent = anyExpanded ? 'Expand all' : 'Collapse all';
  render(document.getElementById('search').value);
}});

function setHideUnavailable(val) {{
  hideUnavailable = val;
  [document.getElementById('hideToggleByPos'), document.getElementById('hideToggleOverall')].forEach(btn => {{
    btn.classList.toggle('active', hideUnavailable);
    btn.textContent = hideUnavailable ? 'Show unavailable' : 'Hide unavailable';
  }});
  syncHash();
  renderActiveTab();
}}
document.getElementById('hideToggleByPos').addEventListener('click', () => setHideUnavailable(!hideUnavailable));
document.getElementById('hideToggleOverall').addEventListener('click', () => setHideUnavailable(!hideUnavailable));

function setTab(tab) {{
  activeTab = tab;
  document.getElementById('tabBtnByPos').classList.toggle('active', tab === 'byPos');
  document.getElementById('tabBtnOverall').classList.toggle('active', tab === 'overall');
  document.getElementById('panelByPos').classList.toggle('active', tab === 'byPos');
  document.getElementById('panelOverall').classList.toggle('active', tab === 'overall');
  document.getElementById('toggleAll').style.display = tab === 'byPos' ? '' : 'none';
  syncHash();
  renderActiveTab();
}}
document.getElementById('tabBtnByPos').addEventListener('click', () => setTab('byPos'));
document.getElementById('tabBtnOverall').addEventListener('click', () => setTab('overall'));

// Apply whatever tab/hide state was restored from the hash (or the defaults)
// before the first render, so a reload lands back where you left off.
setHideUnavailable(hideUnavailable);
setTab(activeTab);

// Kick off the Sleeper fetch as soon as the page loads (rather than waiting
// for someone to open a player's modal) so injury badges next to names in
// the list can populate without needing any interaction. applyInjuryBadges()
// re-runs here once data's ready; it also runs at the end of every
// render()/renderOverall() call above, covering the case where the data was
// already cached (instant) and a re-render (search, collapse, hide toggle)
// just needs to reapply it to the freshly rebuilt rows.
getSleeperData().then(players => {{
  sleeperDataCache = players;
  applyInjuryBadges();
}});

// Real-time updates via the same SSE push as the other board pages -- see
// draft_app.py's /entry/events. Tab/hide state is restored from the URL
// hash above, so a reload never loses your place. The slow safety-net poll
// only kicks in if SSE never manages to connect at all.
const SAFETY_POLL_SECONDS = 30;
let sseConnected = false;
try {{
  const es = new EventSource('/entry/events');
  es.onopen = () => {{ sseConnected = true; }};
  es.onmessage = () => location.reload();
  es.onerror = () => {{ if (es.readyState === EventSource.CLOSED) sseConnected = false; }};
}} catch (e) {{ /* EventSource unsupported -- safety poll below covers it */ }}
setInterval(() => {{ if (!sseConnected) location.reload(); }}, SAFETY_POLL_SECONDS * 1000);
</script>
<div style="text-align:center; font-size:11px; color:#93a4b3; opacity:0.5; padding:22px 0 6px;">TBML Draft Tool &middot; v{APP_VERSION}</div>
</body>
</html>
"""


def render_keep_protect(kp_data, state):
    payload = json.dumps(kp_data)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TBML 2026 Keep/Protect Tracker</title>
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<style>
  :root {{
    --bg: #0f1720; --panel: #16212c; --panel-2: #1c2a37; --border: #2a3a48;
    --text: #e8edf2; --text-dim: #93a4b3; --accent: #3ba7ff; --accent-bg: rgba(59,167,255,0.12);
    --keep: #33c17a; --keep-bg: rgba(51,193,122,0.12); --protect: #f5a623; --protect-bg: rgba(245,166,35,0.12);
    --picked: #4a5b6b; --picked-bg: rgba(74,91,107,0.18);
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--text); padding:24px; }}
  .wrap {{ max-width:1200px; margin:0 auto; }}
  header {{ margin-bottom:20px; }}
  h1 {{ font-size:22px; margin:0; font-weight:700; letter-spacing:-0.01em; }}
  .home-link {{ color:inherit; text-decoration:none; }}
  .home-link:hover {{ color:var(--accent); text-decoration:underline; }}
  .header-top {{ display:flex; align-items:baseline; justify-content:space-between; gap:16px; flex-wrap:wrap; }}
  .updated {{ color:var(--text-dim); font-size:12px; white-space:nowrap; }}
  .nav-links {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }}
  .nav-link {{ display:inline-block; font-size:12px; color:var(--accent); text-decoration:none; border:1px solid var(--accent); padding:4px 10px; border-radius:6px; }}
  .summary {{ display:flex; align-items:center; gap:10px; margin:16px 0 20px; padding:12px 16px; background:var(--panel); border:1px solid var(--border); border-radius:10px; font-size:13px; color:var(--text-dim); }}
  .summary strong {{ color:var(--text); font-size:15px; }}
  .kp-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:12px; }}
  .kp-card {{ background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:14px 16px; }}
  .kp-team {{ font-weight:700; font-size:14px; margin-bottom:10px; }}
  .kp-row {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 8px; padding:6px 0; border-top:1px solid var(--border); }}
  .kp-row:first-of-type {{ border-top:none; }}
  .kp-label {{ font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; color:var(--text-dim); flex-shrink:0; width:44px; }}
  .kp-name {{ font-size:13px; font-weight:600; flex:1 1 auto; min-width:0; }}
  .kp-bye {{ font-size:10.5px; font-weight:400; color:var(--text-dim); flex-shrink:0; }}
  .kp-badge {{ font-size:10px; font-weight:700; padding:3px 7px; border-radius:6px; white-space:nowrap; margin-left:auto; }}
  .kp-row.keep .kp-label {{ color:var(--keep); }}
  .kp-row.pending .kp-label {{ color:var(--text-dim); }}
  .kp-row.pending .kp-badge {{ background:var(--panel-2); color:var(--text-dim); }}
  .kp-row.guaranteed .kp-label {{ color:var(--protect); }}
  .kp-row.guaranteed .kp-name {{ color:var(--protect); }}
  .kp-row.guaranteed .kp-badge {{ background:var(--protect-bg); color:var(--protect); }}
  .kp-row.picked .kp-name {{ color:var(--text-dim); text-decoration:line-through; text-decoration-color:var(--picked); }}
  .kp-row.picked .kp-badge {{ background:var(--picked-bg); color:var(--text-dim); }}
  .legend {{ display:flex; flex-wrap:wrap; gap:16px; margin-top:18px; font-size:12px; color:var(--text-dim); }}
  .legend-item {{ display:inline-flex; align-items:center; gap:6px; }}
  .legend .dot {{ width:9px; height:9px; border-radius:50%; display:inline-block; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="header-top">
      <h1><a class="home-link" href="/" title="Back to TBML draft home">TBML</a> 2026 Keep/Protect Tracker</h1>
      <div class="updated" id="updated"></div>
    </div>
    <div class="nav-links">
      <a class="nav-link" href="draft-board.html">&larr; Back to draft board</a>
      <a class="nav-link" href="draft-players.html">View available players &rarr;</a>
      <a class="nav-link" href="grades/grades.html">Draft Grades &rarr;</a>
    </div>
  </header>

  <div class="summary" id="summary"></div>

  <div class="kp-grid" id="kpGrid"></div>

  <div class="legend">
    <span class="legend-item"><span class="dot" style="background:var(--keep)"></span>Keep &mdash; locked in, Round 14</span>
    <span class="legend-item"><span class="dot" style="background:var(--text-dim)"></span>In play &mdash; both protects still live</span>
    <span class="legend-item"><span class="dot" style="background:var(--protect)"></span>Guaranteed &mdash; the other half got drafted, this one locks in at Round 13</span>
    <span class="legend-item"><span class="dot" style="background:var(--picked)"></span>Picked &mdash; drafted live, no longer protected</span>
  </div>
</div>

<script>
const DATA = {payload};

// 2026 NFL bye weeks per team (per NFL.com's 2026 schedule release) -- kept
// in sync by hand with the copies on the draft board and player-card modal.
const TEAM_BYE = {{
  "Arizona Cardinals": 14, "Atlanta Falcons": 11, "Baltimore Ravens": 13, "Buffalo Bills": 7,
  "Carolina Panthers": 5, "Chicago Bears": 10, "Cincinnati Bengals": 6, "Cleveland Browns": 11,
  "Dallas Cowboys": 14, "Denver Broncos": 10, "Detroit Lions": 6, "Green Bay Packers": 11,
  "Houston Texans": 8, "Indianapolis Colts": 13, "Jacksonville Jaguars": 7, "Kansas City Chiefs": 5,
  "Las Vegas Raiders": 13, "Los Angeles Chargers": 7, "Los Angeles Rams": 11, "Miami Dolphins": 6,
  "Minnesota Vikings": 6, "New England Patriots": 11, "New Orleans Saints": 8, "New York Giants": 8,
  "New York Jets": 13, "Philadelphia Eagles": 10, "Pittsburgh Steelers": 9, "San Francisco 49ers": 8,
  "Seattle Seahawks": 11, "Tampa Bay Buccaneers": 10, "Tennessee Titans": 9, "Washington Commanders": 7,
}};

function byeBadge(entry) {{
  const bye = entry && entry.nflTeam ? TEAM_BYE[entry.nflTeam] : null;
  return bye ? `<span class="kp-bye">Bye ${{bye}}</span>` : '';
}}

function badgeFor(pp) {{
  if (pp.status === 'guaranteed') return 'Guaranteed &middot; R13';
  if (pp.status === 'picked') return `Picked &middot; R${{pp.detail.round}} &middot; ${{pp.detail.team}}`;
  return 'In play';
}}

function renderSummary() {{
  document.getElementById('summary').innerHTML =
    `<strong>${{DATA.resolvedCount}} / ${{DATA.totalTeams}}</strong> protect pairs resolved &mdash; the rest still have both players live in the pool.`;
}}

function renderGrid() {{
  const el = document.getElementById('kpGrid');
  el.innerHTML = DATA.rows.map(row => {{
    const keepRow = row.keep
      ? `<div class="kp-row keep"><span class="kp-label">Keep</span><span class="kp-name">${{row.keep.name}}</span>${{byeBadge(row.keep)}}</div>`
      : '';
    const protectRows = row.protects.map(pp =>
      `<div class="kp-row ${{pp.status}}"><span class="kp-label">Protect</span><span class="kp-name">${{pp.name}}</span>${{byeBadge(pp)}}<span class="kp-badge">${{badgeFor(pp)}}</span></div>`
    ).join('');
    return `<div class="kp-card"><div class="kp-team">${{row.team}}</div>${{keepRow}}${{protectRows}}</div>`;
  }}).join('');
}}

// Real-time updates via the same SSE push as the other board pages -- see
// draft_app.py's /entry/events -- so the commissioner can leave this open
// and watch protects resolve the instant a pick lands. Safety-net poll
// covers the case where SSE never connects at all.
const SAFETY_POLL_SECONDS = 30;
let sseConnected = false;
try {{
  const es = new EventSource('/entry/events');
  es.onopen = () => {{ sseConnected = true; }};
  es.onmessage = () => location.reload();
  es.onerror = () => {{ if (es.readyState === EventSource.CLOSED) sseConnected = false; }};
}} catch (e) {{ /* EventSource unsupported -- safety poll below covers it */ }}
setInterval(() => {{ if (!sseConnected) location.reload(); }}, SAFETY_POLL_SECONDS * 1000);

document.getElementById('updated').textContent = 'Last updated: ' + DATA.resolvedCount + ' of ' + DATA.totalTeams + ' resolved · live-updating';
renderSummary();
renderGrid();
</script>
<div style="text-align:center; font-size:11px; color:#93a4b3; opacity:0.5; padding:22px 0 6px;">TBML Draft Tool &middot; v{APP_VERSION}</div>
</body>
</html>
"""


def _pos_badge(pos):
    color = POS_COLORS.get(pos, "#93a4b3")
    return f'<span style="font-size:9.5px;font-weight:800;padding:2px 6px;border-radius:4px;color:#0b0f14;background:{color};">{pos}</span>'


def _grade_tag(tag):
    if tag == "STEAL":
        return '<span style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.03em;padding:2px 6px;border-radius:4px;background:rgba(51,193,122,0.15);color:var(--keep);">Steal</span>'
    if tag == "REACH":
        return '<span style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.03em;padding:2px 6px;border-radius:4px;background:rgba(226,86,79,0.15);color:#e2564f;">Reach</span>'
    if tag == "KEPT":
        return '<span style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.03em;padding:2px 6px;border-radius:4px;background:rgba(51,193,122,0.15);color:var(--keep);">Kept</span>'
    if tag == "PROTECTED":
        return '<span style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.03em;padding:2px 6px;border-radius:4px;background:rgba(245,166,35,0.15);color:var(--protect);">Protected</span>'
    return ''


def _value_label(row):
    if row["value"] is None:
        return ''
    sign = "+" if row["value"] > 0 else ""
    return f'<span style="font-size:10px;color:var(--text-dim);">{sign}{row["value"]} rd</span>'


def render_grade_page(g, state):
    team = g["team"]
    league = state.get("leagueName", "Ted Brown Memorial League")
    live_rounds = g["liveRounds"]
    rounds_picked = g["roundsPicked"]

    started = rounds_picked > 0
    is_final = started and rounds_picked >= live_rounds
    grade_display = g["grade"] if started else "—"
    if started and rounds_picked < live_rounds:
        status_line = f"Live grade &middot; {rounds_picked} of {live_rounds} rounds picked &middot; updates as picks land"
    elif started:
        status_line = f"Final grade &middot; all {live_rounds} live rounds picked"
    else:
        status_line = "Grade pending &mdash; check back once the draft gets underway"

    # Roast commentary only shows once the draft is actually final for this
    # team -- see generate_roast for why (reads like a recap, not live
    # narration on a roster that's still half-built). A cached AI roast
    # (generated on demand from the /entry page, see draft_app.py) always
    # wins if one exists; otherwise fall back to the free, always-available
    # template roast so every team shows *something* the moment it's final.
    ai_roast = state.get("roasts", {}).get(team) if is_final else None
    roast_text = ai_roast or (generate_roast(g) if is_final else None)
    roast_source_badge = (
        '<span style="font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;padding:2px 6px;border-radius:4px;background:rgba(59,167,255,0.15);color:var(--accent);margin-left:8px;">AI</span>'
        if ai_roast else ''
    )
    if roast_text:
        roast_html = f'''<div style="background:linear-gradient(135deg, rgba(226,86,79,0.10), rgba(59,167,255,0.06));border:1px solid var(--border);border-radius:12px;padding:18px 20px;margin-bottom:22px;">
      <div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:#e2564f;margin-bottom:10px;">&#128293; Post-Draft Roast{roast_source_badge}</div>
      <div style="font-size:14px;line-height:1.55;color:var(--text);">{roast_text}</div>
    </div>'''
    else:
        roast_html = ''

    def stat_tile(label, color, value_html, sub_html):
        return f'''<div style="background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px;text-align:center;">
        <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:{color};margin-bottom:8px;">{label}</div>
        <div style="font-size:15px;font-weight:700;">{value_html}</div>
        <div style="font-size:12px;color:var(--text-dim);">{sub_html}</div>
      </div>'''

    if g["bestValue"]:
        bv = g["bestValue"]
        best_value_tile = stat_tile("Best Value", "var(--keep)", bv["name"], f'Round {bv["round"]} &middot; +{bv["value"]} rd vs ADP')
    else:
        best_value_tile = stat_tile("Best Value", "var(--keep)", "—", "No graded picks yet")

    if g["biggestReach"] and g["biggestReach"]["value"] is not None and g["biggestReach"]["value"] < 0:
        br = g["biggestReach"]
        reach_tile = stat_tile("Biggest Reach", "#e2564f", br["name"], f'Round {br["round"]} &middot; {br["value"]} rd vs ADP')
    else:
        reach_tile = stat_tile("Biggest Reach", "#e2564f", "—", "No reaches yet")

    if g["avgValue"] is not None:
        sign = "+" if g["avgValue"] > 0 else ""
        value_score_tile = stat_tile("Value Score", "var(--accent)", f'{sign}{g["avgValue"]:.1f} rd avg', "Rounds of value per pick")
    else:
        value_score_tile = stat_tile("Value Score", "var(--accent)", "—", "Not enough picks yet")

    if g["weakestPos"]:
        wp = g["weakestPos"]
        wp_grade = g["posGrades"][wp]["grade"]
        weakest_tile = stat_tile("Weakest Position", "var(--protect)", f'{wp} ({wp_grade})', "Lowest positional grade")
    else:
        weakest_tile = stat_tile("Weakest Position", "var(--protect)", "—", "Not enough picks yet")

    pos_bars = []
    for pos in GRADE_POSITIONS:
        pg = g["posGrades"].get(pos)
        if pg:
            pct, grade_letter, fill = pg["pct"], pg["grade"], POS_COLORS.get(pos, "#93a4b3")
        else:
            pct, grade_letter, fill = 0, "—", "#2a3a48"
        pos_bars.append(f'''<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
        <div style="width:28px;font-size:11px;font-weight:800;color:var(--text-dim);">{pos}</div>
        <div style="flex:1;height:8px;border-radius:5px;background:var(--panel-2);overflow:hidden;"><div style="width:{pct}%;height:100%;background:{fill};"></div></div>
        <div style="width:26px;font-size:12px;font-weight:700;text-align:right;">{grade_letter}</div>
      </div>''')
    pos_bars_html = ''.join(pos_bars)

    pick_rows = []
    for row in g["rows"]:
        pick_rows.append(f'''<div style="display:flex;align-items:center;gap:6px;background:var(--panel-2);border:1px solid var(--border);border-radius:8px;padding:7px 10px;">
        <span style="font-size:11px;color:var(--text-dim);width:22px;flex-shrink:0;">R{row["round"]}</span>
        <span style="font-size:12.5px;font-weight:600;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{row["name"]}</span>
        {_pos_badge(row["pos"])}
        {_grade_tag(row["tag"])}
      </div>''')
    pick_rows_html = ''.join(pick_rows) if pick_rows else '<div style="font-size:12.5px;color:var(--text-dim);grid-column:1 / -1;text-align:center;padding:12px;">No picks yet.</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{team} &middot; TBML 2026 Draft Grade</title>
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<style>
  :root {{
    --bg: #0f1720; --panel: #16212c; --panel-2: #1c2a37; --border: #2a3a48;
    --text: #e8edf2; --text-dim: #93a4b3; --accent: #3ba7ff; --accent-bg: rgba(59,167,255,0.12);
    --keep: #33c17a; --protect: #f5a623;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--text); }}
  a {{ color: var(--accent); }}
  a:hover {{ color: #6cc0ff; }}
  .home-link {{ color:inherit; text-decoration:none; }}
  .home-link:hover {{ color:var(--accent); text-decoration:underline; }}
  .nav-link {{ display:inline-block; font-size:12px; color:var(--accent); text-decoration:none; border:1px solid var(--accent); padding:4px 10px; border-radius:6px; }}
  /* Two-column roster grid gets cramped on phone widths -- long names plus
     a STEAL/REACH tag start truncating. Single column below 520px gives
     each row the full content width instead. */
  @media (max-width: 520px) {{
    .roster-grid {{ grid-template-columns: 1fr !important; }}
  }}
</style>
</head>
<body>
<div style="min-height:100%; background: radial-gradient(circle at 20% 0%, rgba(59,167,255,0.12), transparent 50%), var(--bg); padding:0 0 36px;">

  <div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px 0;flex-wrap:wrap;gap:8px;">
    <a class="nav-link" href="grades.html">&larr; All Grades</a>
    <a class="nav-link home-link" href="../draft-board.html">Draft Board</a>
  </div>

  <div style="text-align:center;padding:22px 24px 26px;">
    <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-bottom:10px;">{league} &middot; 2026 Draft Recap</div>
    <div style="width:104px;height:104px;border-radius:50%;background:var(--accent-bg);border:2px solid var(--accent);display:flex;align-items:center;justify-content:center;font-size:2.8rem;font-weight:800;color:var(--accent);margin:0 auto 14px;">{grade_display}</div>
    <h1 style="font-size:1.9rem;font-weight:800;margin:0 0 4px;letter-spacing:-0.01em;"><a class="home-link" href="/" title="Back to TBML draft home">{team}</a></h1>
    <div style="color:var(--text-dim);font-size:13px;">Draft Slot #{g["slot"]} &middot; {status_line}</div>
  </div>

  <div style="padding:0 24px;max-width:760px;margin:0 auto;">
    <div style="display:grid;grid-template-columns:repeat(2, minmax(0,1fr));gap:12px;margin-bottom:22px;">
      {best_value_tile}
      {reach_tile}
      {value_score_tile}
      {weakest_tile}
    </div>

    {roast_html}

    <div style="background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px 18px;margin-bottom:22px;">
      <div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:var(--text-dim);margin-bottom:12px;">Positional Grades</div>
      {pos_bars_html}
    </div>

    <div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:var(--text-dim);margin-bottom:10px;">Full Roster</div>
    <div class="roster-grid" style="display:grid;grid-template-columns:repeat(2, minmax(0,1fr));gap:8px;margin-bottom:18px;">
      {pick_rows_html}
    </div>

    <div style="font-size:11px;color:var(--text-dim);opacity:0.6;text-align:center;">Value score compares each pick's round to its ADP-implied round (fantasyfootballcalculator.com consensus). Keepers and guaranteed protects aren't scored.</div>
  </div>
</div>
<script>
const SAFETY_POLL_SECONDS = 30;
let sseConnected = false;
try {{
  const es = new EventSource('/entry/events');
  es.onopen = () => {{ sseConnected = true; }};
  es.onmessage = () => location.reload();
  es.onerror = () => {{ if (es.readyState === EventSource.CLOSED) sseConnected = false; }};
}} catch (e) {{ /* EventSource unsupported -- safety poll below covers it */ }}
setInterval(() => {{ if (!sseConnected) location.reload(); }}, SAFETY_POLL_SECONDS * 1000);
</script>
<div style="text-align:center; font-size:11px; color:#93a4b3; opacity:0.5; padding:6px 0 22px;">TBML Draft Tool &middot; v{APP_VERSION}</div>
</body>
</html>
"""


def render_grades_hub(grades, state):
    league = state.get("leagueName", "Ted Brown Memorial League")
    cards = []
    for team in state["teams"]:
        g = grades[team]
        started = g["roundsPicked"] > 0
        grade_display = g["grade"] if started else "—"
        sub = f'{g["roundsPicked"]} of {g["liveRounds"]} rounds' if started else "Not started"
        slug = team_slug(team)
        cards.append(f'''<a href="grade-{slug}.html" style="display:flex;align-items:center;gap:14px;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px 16px;text-decoration:none;color:inherit;">
      <div style="flex-shrink:0;width:52px;height:52px;border-radius:12px;background:var(--accent-bg);border:1px solid var(--accent);display:flex;align-items:center;justify-content:center;font-size:1.3rem;font-weight:800;color:var(--accent);">{grade_display}</div>
      <div style="flex:1;min-width:0;">
        <div style="font-size:14.5px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{team}</div>
        <div style="font-size:12px;color:var(--text-dim);">Slot #{g["slot"]} &middot; {sub}</div>
      </div>
      <div style="color:var(--accent);font-size:14px;">&rarr;</div>
    </a>''')
    cards_html = ''.join(cards)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TBML 2026 Draft Grades</title>
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<style>
  :root {{
    --bg: #0f1720; --panel: #16212c; --panel-2: #1c2a37; --border: #2a3a48;
    --text: #e8edf2; --text-dim: #93a4b3; --accent: #3ba7ff; --accent-bg: rgba(59,167,255,0.12);
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--text); padding:24px; }}
  .wrap {{ max-width:640px; margin:0 auto; }}
  h1 {{ font-size:22px; margin:0 0 4px; font-weight:700; letter-spacing:-0.01em; }}
  .home-link {{ color:inherit; text-decoration:none; }}
  .home-link:hover {{ color:var(--accent); text-decoration:underline; }}
  .nav-link {{ display:inline-block; font-size:12px; color:var(--accent); text-decoration:none; border:1px solid var(--accent); padding:4px 10px; border-radius:6px; margin-top:10px; margin-bottom:20px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1><a class="home-link" href="/" title="Back to TBML draft home">TBML</a> 2026 Draft Grades</h1>
  <div style="color:var(--text-dim);font-size:13px;">{league}</div>
  <a class="nav-link" href="../draft-board.html">&larr; Back to draft board</a>
  <div style="display:flex;flex-direction:column;gap:10px;">
    {cards_html}
  </div>
</div>
<script>
const SAFETY_POLL_SECONDS = 30;
let sseConnected = false;
try {{
  const es = new EventSource('/entry/events');
  es.onopen = () => {{ sseConnected = true; }};
  es.onmessage = () => location.reload();
  es.onerror = () => {{ if (es.readyState === EventSource.CLOSED) sseConnected = false; }};
}} catch (e) {{ /* EventSource unsupported -- safety poll below covers it */ }}
setInterval(() => {{ if (!sseConnected) location.reload(); }}, SAFETY_POLL_SECONDS * 1000);
</script>
<div style="text-align:center; font-size:11px; color:#93a4b3; opacity:0.5; padding:22px 0 6px;">TBML Draft Tool &middot; v{APP_VERSION}</div>
</body>
</html>
"""


def main():
    pool = json.load(open(POOL_PATH))
    state = json.load(open(STATE_PATH))
    derived = build_derived_state(state, pool)

    board_html = render_draft_board(derived, state)
    list_html = render_available_players(pool, derived)
    kp_data = build_keep_protect_data(state, pool)
    kp_html = render_keep_protect(kp_data, state)
    grades = compute_team_grades(state, pool)

    open(BOARD_OUT, "w").write(board_html)
    open(LIST_OUT, "w").write(list_html)
    open(KP_OUT, "w").write(kp_html)
    print("Wrote", BOARD_OUT)
    print("Wrote", LIST_OUT)
    print("Wrote", KP_OUT)

    os.makedirs(GRADES_DIR, exist_ok=True)
    for team in state["teams"]:
        page_path = os.path.join(GRADES_DIR, f"grade-{team_slug(team)}.html")
        open(page_path, "w").write(render_grade_page(grades[team], state))
    hub_path = os.path.join(GRADES_DIR, "grades.html")
    open(hub_path, "w").write(render_grades_hub(grades, state))
    print("Wrote", GRADES_DIR, f"({len(state['teams'])} team pages + hub)")


if __name__ == "__main__":
    main()
