#!/usr/bin/env python3
"""Generate draft_board.html and available_players.html from state.json + pool.json.
Re-run this after editing state.json (adding a pick, resolving a protect, etc.)
to regenerate both pages in sync."""
import json
import os
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
APP_VERSION = "0.2.1.1"

POOL_PATH = os.path.join(BASE_DIR, "pool.json")
STATE_PATH = os.path.join(BASE_DIR, "state.json")
BOARD_OUT = os.path.join(BASE_DIR, "draft-board.html")
LIST_OUT = os.path.join(BASE_DIR, "draft-players.html")
KP_OUT = os.path.join(BASE_DIR, "keep-protect.html")

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
        protects = []
        for pname in info.get("protect", []):
            p = pool_by_name.get(pname)
            status = "pending"
            detail = None
            pos = p["pos"] if p else None
            if p:
                if p.get("status") == "protected":
                    status = "guaranteed"
                elif p.get("status") == "picked":
                    status = "picked"
                    detail = p.get("pickInfo")
            protects.append({"name": pname, "pos": pos, "status": status, "detail": detail})
        rows.append({"team": team, "keep": keep, "protects": protects})
    resolved = sum(1 for r in rows if any(pp["status"] == "guaranteed" for pp in r["protects"]))
    return {"rows": rows, "resolvedCount": resolved, "totalTeams": len(rows)}


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
  td.pick {{ padding:8px 10px; vertical-align:top; min-width:118px; }}
  .pick-num {{ font-size:10px; color:var(--text-dim); font-weight:600; }}
  .pos-filled .pick-num {{ color:rgba(11,15,20,.6); }}
  .pick-player {{ font-size:13px; margin-top:3px; color:var(--empty); }}
  .pick-player.filled {{ color:#0b0f14; font-weight:700; }}
  .pick-player.pending {{ font-style:italic; }}
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

function hexIsSet(pos) {{ return STATE.posColors[pos]; }}

function overallPick(round, teamIndex, n) {{
  const posInRound = (round % 2 === 1) ? (teamIndex + 1) : (n - teamIndex);
  return (round - 1) * n + posInRound;
}}

function cellInner(label, entry) {{
  const filled = entry && entry.name;
  return `<div class="pick-num">${{label}}</div><div class="pick-player${{filled ? ' filled' : ' pending'}}">${{filled ? entry.name : (label.startsWith('#') ? '&mdash;' : 'Pending')}}</div>`;
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
  .refresh-toggle {{ margin-left:auto; font-size:12px; color:var(--text-dim); display:flex; align-items:center; gap:6px; cursor:pointer; user-select:none; }}
  .refresh-toggle input {{ cursor:pointer; }}
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
  </div>

  <div class="tabs">
    <button class="tab-btn active" id="tabBtnByPos">By Position</button>
    <button class="tab-btn" id="tabBtnOverall">Overall Ranking</button>
    <label class="refresh-toggle"><input type="checkbox" id="autoRefreshToggle" checked> Auto-refresh</label>
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
      <span class="modal-team-detail">${{p.pos}}${{team.abbr ? ' &middot; ' + team.abbr : ''}}</span>
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
      row.innerHTML = `
        <div class="player-name${{p.status !== 'available' ? ' strike' : ''}}"><span class="player-rank">${{rankLabel}}</span><a class="player-link" href="#" data-name="${{escAttr(p.name)}}">${{p.name}}</a><span class="row-injury-chip" data-name="${{escAttr(p.name)}}"></span></div>
        <div class="player-meta">${{ovrLabel ? `<span class="overall-rank">${{ovrLabel}}</span>` : ''}}<span>${{p.nflTeam}}</span>${{statusBadges(p)}}</div>
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
    tr.innerHTML = `
      <td class="overall-num">${{p.overallRank ? '#' + p.overallRank : '&mdash;'}}</td>
      <td><a class="player-link${{p.status !== 'available' ? ' strike' : ''}}" href="#" data-name="${{escAttr(p.name)}}">${{p.name}}</a><span class="row-injury-chip" data-name="${{escAttr(p.name)}}"></span></td>
      <td><span class="pos-badge" style="background:${{DATA.posColors[p.pos]}}">${{p.pos}}</span></td>
      <td>${{p.nflTeam}}</td>
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

// Real-time updates via the same SSE push as the other board pages (see
// draft_app.py's /entry/events), gated by the same checkbox as before --
// unticking it just ignores the next push/poll, no page state is lost
// either way since tab/hide are restored from the URL hash above. The slow
// safety-net poll only kicks in if SSE never manages to connect at all.
const SAFETY_POLL_SECONDS = 30;
let autoRefreshEnabled = true;
let sseConnected = false;
document.getElementById('autoRefreshToggle').addEventListener('change', e => {{
  autoRefreshEnabled = e.target.checked;
}});
try {{
  const es = new EventSource('/entry/events');
  es.onopen = () => {{ sseConnected = true; }};
  es.onmessage = () => {{ if (autoRefreshEnabled) location.reload(); }};
  es.onerror = () => {{ if (es.readyState === EventSource.CLOSED) sseConnected = false; }};
}} catch (e) {{ /* EventSource unsupported -- safety poll below covers it */ }}
setInterval(() => {{ if (autoRefreshEnabled && !sseConnected) location.reload(); }}, SAFETY_POLL_SECONDS * 1000);
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
      ? `<div class="kp-row keep"><span class="kp-label">Keep</span><span class="kp-name">${{row.keep.name}}</span></div>`
      : '';
    const protectRows = row.protects.map(pp =>
      `<div class="kp-row ${{pp.status}}"><span class="kp-label">Protect</span><span class="kp-name">${{pp.name}}</span><span class="kp-badge">${{badgeFor(pp)}}</span></div>`
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


def main():
    pool = json.load(open(POOL_PATH))
    state = json.load(open(STATE_PATH))
    derived = build_derived_state(state, pool)

    board_html = render_draft_board(derived, state)
    list_html = render_available_players(pool, derived)
    kp_data = build_keep_protect_data(state, pool)
    kp_html = render_keep_protect(kp_data, state)

    open(BOARD_OUT, "w").write(board_html)
    open(LIST_OUT, "w").write(list_html)
    open(KP_OUT, "w").write(kp_html)
    print("Wrote", BOARD_OUT)
    print("Wrote", LIST_OUT)
    print("Wrote", KP_OUT)


if __name__ == "__main__":
    main()
