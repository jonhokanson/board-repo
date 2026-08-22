#!/usr/bin/env python3
"""Live pick-entry app for the TBML 2026 draft. Runs on Web01 itself (not the
Claude cloud sandbox) so picks can be entered directly at the table, with no
round-trip through chat. Reuses generate.py's rendering/derivation logic
directly -- no reimplementation -- so the live app can never drift from how
the static pages are built.

state.json here IS the live source of truth once this app is deployed and in
use. Every successful pick/undo: (1) writes state.json, (2) regenerates
draft-board.html / draft-players.html / keep-protect.html straight to the
paths nginx serves, so viewers see the update immediately with no dependency
on git at all, then (3) commits + pushes to GitHub as an offsite backup /
history, best-effort (a git failure does not fail the request -- the local
write already succeeded and is already being served).

Run with a single worker only (see run_app.sh / the systemd unit) -- state.json
read-modify-write is guarded with a file lock, but that only protects against
corruption, not against two workers racing to serve stale "next pick" info to
two people at once.
"""
import fcntl
import html
import json
import os
import queue
import subprocess
import threading

from flask import Flask, request, redirect, url_for, session, make_response, Response

import generate as g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POOL_PATH = os.environ.get("POOL_PATH", os.path.join(BASE_DIR, "pool.json"))
STATE_PATH = os.environ.get("STATE_PATH", os.path.join(BASE_DIR, "state.json"))
PIN_PATH = os.environ.get("PIN_PATH", os.path.join(BASE_DIR, "pin.txt"))
# Anthropic API key for the AI-generated draft-grade roast (optional -- the
# feature works fine without it, just using the free built-in template roast
# instead). Same git-ignored-file pattern as PIN_PATH/secret_key.txt: never
# committed, created once by hand on Web01. No systemd Environment= line
# needed since the default path is already inside BASE_DIR.
ANTHROPIC_KEY_PATH = os.environ.get("ANTHROPIC_KEY_PATH", os.path.join(BASE_DIR, "anthropic_key.txt"))
LOCK_PATH = STATE_PATH + ".lock"

# Where the regenerated pages get written -- on Web01 this should be the same
# paths nginx serves (e.g. /var/www/html/board/*.html). Defaults here match
# the sandbox layout for local testing.
BOARD_OUT = os.environ.get("BOARD_OUT", os.path.join(BASE_DIR, "draft-board.html"))
LIST_OUT = os.environ.get("LIST_OUT", os.path.join(BASE_DIR, "draft-players.html"))
KP_OUT = os.environ.get("KP_OUT", os.path.join(BASE_DIR, "keep-protect.html"))
GRADES_OUT_DIR = os.environ.get("GRADES_OUT_DIR", os.path.join(BASE_DIR, "grades"))

# --- Mock draft sandbox (added 2026-08-22) --------------------------------
# A second, fully independent copy of everything above -- its own state
# file, lock, and output paths -- so Jon can submit picks, undo, and
# generate/clear AI roasts against fake data without any risk of touching
# the real draft. Never backed up to git (see mock_reset()/mock routes
# below) since it's throwaway play data, not something worth a history for.
# On Web01 these point at /var/www/html/mock/board/*.html, same static-file
# serving as the real board -- no nginx changes needed, just new systemd
# Environment= lines (see DEPLOY.md).
MOCK_STATE_PATH = os.environ.get("MOCK_STATE_PATH", os.path.join(BASE_DIR, "mock_state.json"))
MOCK_SEED_PATH = os.environ.get("MOCK_SEED_PATH", os.path.join(BASE_DIR, "mock_state.seed.json"))
MOCK_LOCK_PATH = MOCK_STATE_PATH + ".lock"
MOCK_BOARD_OUT = os.environ.get("MOCK_BOARD_OUT", os.path.join(BASE_DIR, "mock-draft-board.html"))
MOCK_LIST_OUT = os.environ.get("MOCK_LIST_OUT", os.path.join(BASE_DIR, "mock-draft-players.html"))
MOCK_KP_OUT = os.environ.get("MOCK_KP_OUT", os.path.join(BASE_DIR, "mock-keep-protect.html"))
MOCK_GRADES_OUT_DIR = os.environ.get("MOCK_GRADES_OUT_DIR", os.path.join(BASE_DIR, "mock-grades"))

# Local git working copy to push backups from -- separate from the paths
# above so a slow/failed git push can never block or corrupt what's served.
GIT_REPO_DIR = os.environ.get("GIT_REPO_DIR")  # e.g. /var/www/html on Web01
GIT_REMOTE = os.environ.get("GIT_REMOTE", "github")
GIT_BRANCH = os.environ.get("GIT_BRANCH", "main")
# Full pick-by-pick history as raw JSON, committed alongside the rendered
# pages -- this is the precise, replayable audit trail; the HTML commits are
# more of a "what did it look like at the time" snapshot.
STATE_BACKUP_PATH = os.environ.get(
    "STATE_BACKUP_PATH", os.path.join(GIT_REPO_DIR, "board", "state-backup.json") if GIT_REPO_DIR else None
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "DRAFT_APP_SECRET",
    open(os.path.join(BASE_DIR, "secret_key.txt")).read().strip()
    if os.path.exists(os.path.join(BASE_DIR, "secret_key.txt"))
    else os.urandom(24).hex(),
)


def read_pin():
    if os.path.exists(PIN_PATH):
        return open(PIN_PATH).read().strip()
    return "0000"  # obvious placeholder -- deployment doc tells Jon to set a real one


def read_anthropic_key():
    if os.path.exists(ANTHROPIC_KEY_PATH):
        key = open(ANTHROPIC_KEY_PATH).read().strip()
        return key or None
    return None


def load_pool():
    return json.load(open(POOL_PATH))


def load_state(path=None):
    return json.load(open(path or STATE_PATH))


def save_state(state, path=None):
    """Read-modify-write callers should hold the lock for the whole critical
    section; this just does the write+atomic-rename part."""
    path = path or STATE_PATH
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_path, path)


class StateLock:
    """File lock around the read-modify-write cycle for a state file, so two
    near-simultaneous submits (double click, two tabs) can't interleave and
    corrupt it. Not needed for correctness if the app only ever runs with a
    single worker/thread, but cheap insurance if that ever changes. Defaults
    to the real draft's lock; the mock routes pass MOCK_LOCK_PATH so the two
    state files can never block or interleave with each other."""

    def __init__(self, lock_path=None):
        self.lock_path = lock_path or LOCK_PATH

    def __enter__(self):
        self.fh = open(self.lock_path, "w")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()


def regenerate_pages(state, pool, board_out=None, list_out=None, kp_out=None, grades_dir=None):
    board_out = board_out or BOARD_OUT
    list_out = list_out or LIST_OUT
    kp_out = kp_out or KP_OUT
    grades_dir = grades_dir or GRADES_OUT_DIR

    derived = g.build_derived_state(state, pool)
    board_html = g.render_draft_board(derived, state)
    list_html = g.render_available_players(pool, derived)
    kp_data = g.build_keep_protect_data(state, pool)
    kp_html = g.render_keep_protect(kp_data, state)
    grades = g.compute_team_grades(state, pool)
    open(board_out, "w").write(board_html)
    open(list_out, "w").write(list_html)
    open(kp_out, "w").write(kp_html)

    os.makedirs(grades_dir, exist_ok=True)
    for team in state["teams"]:
        page_path = os.path.join(grades_dir, f"grade-{g.team_slug(team)}.html")
        open(page_path, "w").write(g.render_grade_page(grades[team], state))
    open(os.path.join(grades_dir, "grades.html"), "w").write(g.render_grades_hub(grades, state))


MOCK_BANNER_HTML = (
    '<div style="background:#f5a623;color:#1a1200;text-align:center;'
    'font-weight:800;font-size:12px;letter-spacing:.04em;text-transform:uppercase;'
    'padding:6px 10px;">&#129514; Mock Draft &mdash; not the real draft, none of this counts</div>'
)


def _inject_mock_banner(path):
    html_str = open(path).read().replace("<body>", "<body>" + MOCK_BANNER_HTML, 1)
    open(path, "w").write(html_str)


def regenerate_mock_pages(state, pool):
    """Same rendering as regenerate_pages(), written to the separate mock/
    output paths, with a bright banner spliced into every page so there's
    never any chance of mistaking this for the real draft."""
    # Unlike the real board/list/kp paths (whose parent dir -- /var/www/html/board --
    # already exists from the original static-site setup), the mock output paths
    # point at a brand-new /var/www/html/mock/board that nothing else creates.
    # regenerate_pages() itself only os.makedirs()'s the grades subdirectory, so
    # create the board/list/kp parent dirs here defensively rather than relying
    # on a one-time manual mkdir on Web01.
    for out_path in (MOCK_BOARD_OUT, MOCK_LIST_OUT, MOCK_KP_OUT):
        parent = os.path.dirname(out_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    regenerate_pages(
        state, pool,
        board_out=MOCK_BOARD_OUT, list_out=MOCK_LIST_OUT, kp_out=MOCK_KP_OUT, grades_dir=MOCK_GRADES_OUT_DIR,
    )
    for path in (MOCK_BOARD_OUT, MOCK_LIST_OUT, MOCK_KP_OUT):
        _inject_mock_banner(path)
    for fname in os.listdir(MOCK_GRADES_OUT_DIR):
        _inject_mock_banner(os.path.join(MOCK_GRADES_OUT_DIR, fname))


def ensure_mock_state():
    """Bootstraps mock_state.json from the seed file the first time ANY mock
    route is hit, so a fresh deploy that skipped the manual one-time
    `cp mock_state.seed.json mock_state.json` step (or one where that file
    got cleaned up somehow) self-heals instead of every mock route 500ing on
    a missing file forever. Idempotent and cheap (an os.path.exists check)
    -- called at the top of every mock route below, same spirit as the
    template-roast fallback: the feature should never be stuck broken just
    because a one-time setup step was missed."""
    if os.path.exists(MOCK_STATE_PATH):
        return
    if not os.path.exists(MOCK_SEED_PATH):
        return  # nothing to bootstrap from -- the route's own load_state() call will raise a clear error
    with StateLock(MOCK_LOCK_PATH):
        if os.path.exists(MOCK_STATE_PATH):  # re-check inside the lock -- another request may have won the race
            return
        seed = json.load(open(MOCK_SEED_PATH))
        save_state(seed, MOCK_STATE_PATH)
        regenerate_mock_pages(seed, load_pool())


def push_backup(message, state):
    """Best-effort git commit + push of the regenerated pages + a full copy
    of state.json to GitHub as an offsite backup/history. Never raises -- a
    network hiccup should never fail the request or block the board from
    updating locally. Only stages the specific files this app owns (not
    `git add -A`), so a stray unrelated file sitting in GIT_REPO_DIR never
    gets swept into a commit by accident."""
    if not GIT_REPO_DIR:
        return "skipped (GIT_REPO_DIR not set)"
    try:
        if STATE_BACKUP_PATH:
            with open(STATE_BACKUP_PATH, "w") as f:
                json.dump(state, f, indent=2)
        tracked = [p for p in (BOARD_OUT, LIST_OUT, KP_OUT, GRADES_OUT_DIR, STATE_BACKUP_PATH) if p]
        subprocess.run(["git", "-C", GIT_REPO_DIR, "add", "--"] + tracked, check=True, capture_output=True, timeout=10)
        diff = subprocess.run(
            ["git", "-C", GIT_REPO_DIR, "diff", "--cached", "--quiet"], capture_output=True, timeout=10
        )
        if diff.returncode == 0:
            return "no changes"
        subprocess.run(
            ["git", "-C", GIT_REPO_DIR, "commit", "-m", message, "-q"], check=True, capture_output=True, timeout=10
        )
        subprocess.run(
            ["git", "-C", GIT_REPO_DIR, "push", GIT_REMOTE, GIT_BRANCH],
            check=True, capture_output=True, timeout=20,
        )
        return "pushed"
    except Exception as e:  # noqa: BLE001 -- deliberately broad, this must never break the request
        return f"failed ({e})"


def require_auth():
    return session.get("authed") is True


# --- Real-time push (Server-Sent Events) ---------------------------------
# Every viewer with a board page open (draft-board.html / draft-players.html
# / keep-protect.html) holds a long-lived connection to /entry/events. The
# instant a pick or undo lands, broadcast_update() wakes every connected
# client's queue, and each one's stream() generator turns that into an SSE
# message telling the browser to reload. This is deliberately NOT gated by
# require_auth() -- the board pages themselves are public static files with
# no PIN, and the push carries no data of its own (just "something changed"),
# so there's nothing here that isn't already visible to anyone with the URL.
_sse_clients = set()
_sse_lock = threading.Lock()


def broadcast_update():
    with _sse_lock:
        clients = list(_sse_clients)
    for q in clients:
        q.put_nowait("update")


@app.route("/entry/events")
def events():
    q = queue.Queue()
    with _sse_lock:
        _sse_clients.add(q)

    def stream():
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    msg = q.get(timeout=20)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"  # comment line -- keeps the connection open through proxies/timeouts
        finally:
            with _sse_lock:
                _sse_clients.discard(q)

    resp = Response(stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"  # belt-and-suspenders vs. nginx proxy buffering
    return resp


PAGE_STYLE = """
:root {
  --bg: #0f1720; --panel: #16212c; --panel-2: #1c2a37; --border: #2a3a48;
  --text: #e8edf2; --text-dim: #93a4b3; --accent: #3ba7ff; --accent-bg: rgba(59,167,255,0.12);
  --keep: #33c17a; --protect: #f5a623; --danger: #e2564f; --danger-bg: rgba(226,86,79,0.12);
}
* { box-sizing: border-box; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--text); padding:24px; }
.wrap { max-width:640px; margin:0 auto; }
h1 { font-size:20px; margin:0 0 4px; font-weight:700; }
.sub { color:var(--text-dim); font-size:13px; margin-bottom:20px; }
.card { background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:18px 20px; margin-bottom:16px; }
.on-clock { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.on-clock .who { font-size:17px; font-weight:700; }
.on-clock .round { color:var(--text-dim); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
label { display:block; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; color:var(--text-dim); margin:14px 0 6px; }
input[type=text], input[type=password], select {
  width:100%; padding:10px 12px; border-radius:8px; border:1px solid var(--border);
  background:var(--panel-2); color:var(--text); font-size:15px;
}
input:focus, select:focus { outline:none; border-color:var(--accent); }
button {
  font-size:14px; font-weight:700; padding:10px 18px; border-radius:8px; border:none;
  cursor:pointer; margin-top:14px;
}
button.primary { background:var(--accent); color:#04101c; }
button.danger { background:var(--danger-bg); color:var(--danger); border:1px solid var(--danger); }
button.ghost { background:transparent; color:var(--text-dim); border:1px solid var(--border); }
.msg { padding:10px 14px; border-radius:8px; font-size:13px; margin-bottom:16px; }
.msg.ok { background:rgba(51,193,122,0.12); color:var(--keep); border:1px solid var(--keep); }
.msg.err { background:var(--danger-bg); color:var(--danger); border:1px solid var(--danger); }
.suggestions { border:1px solid var(--border); border-radius:8px; margin-top:4px; max-height:220px; overflow-y:auto; display:none; background:var(--panel-2); }
.suggestions.open { display:block; }
.suggestion { padding:8px 12px; font-size:14px; cursor:pointer; border-bottom:1px solid var(--border); }
.suggestion:last-child { border-bottom:none; }
.suggestion:hover, .suggestion.active { background:var(--accent-bg); }
.suggestion .pos { color:var(--text-dim); font-size:11px; margin-left:6px; }
.recent { font-size:13px; color:var(--text-dim); }
.recent .row { display:flex; justify-content:space-between; padding:4px 0; border-top:1px solid var(--border); }
.recent .row:first-child { border-top:none; }
.recent .row .name { color:var(--text); font-weight:600; }
.toggle-link { font-size:12px; color:var(--accent); cursor:pointer; text-decoration:underline; }
.override-row { display:none; gap:10px; margin-top:14px; }
.override-row.open { display:flex; }
.override-row > div { flex:1; }
.home-link { color:inherit; text-decoration:none; }
.home-link:hover { color:var(--accent); text-decoration:underline; }
"""


def page(title, body, msg=None, msg_kind="ok"):
    msg_html = f'<div class="msg {msg_kind}">{msg}</div>' if msg else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{PAGE_STYLE}</style>
</head>
<body>
<div class="wrap">
  <h1><a class="home-link" href="/" title="Back to TBML draft home">TBML</a> {title}</h1>
  {msg_html}
  {body}
</div>
</body>
</html>
"""


@app.route("/entry/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("pin", "") == read_pin():
            session["authed"] = True
            return redirect(url_for("entry"))
        error = "Wrong PIN."
    body = f"""
  <div class="card">
    <form method="post">
      <label for="pin">Enter PIN</label>
      <input type="password" id="pin" name="pin" autofocus>
      <button class="primary" type="submit">Unlock</button>
    </form>
  </div>
  """
    return page("Draft Entry &mdash; Login", body, msg=error, msg_kind="err")


@app.route("/entry/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/entry", methods=["GET"])
def entry():
    if not require_auth():
        return redirect(url_for("login"))

    state = load_state()
    pool = load_pool()
    derived = g.build_derived_state(state, pool)

    slot = g.next_pick_slot(state)
    if slot:
        on_clock_html = f"""
      <div class="on-clock">
        <div>
          <div class="round">Round {slot['round']} &middot; Pick {len(state['picks']) + 1}</div>
          <div class="who">{slot['team']} is on the clock</div>
        </div>
        <span class="toggle-link" onclick="document.getElementById('override').classList.toggle('open')">Wrong? Override &rarr;</span>
      </div>
      <div id="override" class="override-row">
        <div>
          <label for="ovTeam">Team</label>
          <select id="ovTeam" name="override_team">
            <option value="">(use on-the-clock team)</option>
            {''.join(f'<option value="{t}">{t}</option>' for t in state['teams'])}
          </select>
        </div>
        <div>
          <label for="ovRound">Round</label>
          <select id="ovRound" name="override_round">
            <option value="">(use next round)</option>
            {''.join(f'<option value="{r}">{r}</option>' for r in range(1, state['liveRounds'] + 1))}
          </select>
        </div>
      </div>
      """
    else:
        on_clock_html = '<div class="on-clock"><div class="who">All 12 live rounds are full.</div></div>'

    available_players = sorted(
        [p for p in pool if p["status"] == "available"],
        key=lambda p: (p["pos"], p.get("rank") or 999),
    )
    player_payload = json.dumps(
        [{"name": p["name"], "pos": p["pos"], "team": p.get("nflTeam", "")} for p in available_players]
    )

    recent = list(reversed(state["picks"][-8:]))
    recent_html = (
        "".join(
            f'<div class="row"><span class="name">{pk["name"]}</span><span>R{pk["round"]} &middot; {pk["team"]}</span></div>'
            for pk in recent
        )
        if recent
        else '<div class="row"><span>No picks recorded yet.</span></div>'
    )

    # Draft grade roasts (AI) -- see /entry/generate-grades. Purely a manual,
    # on-demand action; never triggered automatically by a pick/undo.
    has_ai_key = read_anthropic_key() is not None
    grades = g.compute_team_grades(state, pool)
    final_teams = [
        t for t in state["teams"]
        if grades[t]["roundsPicked"] > 0 and grades[t]["roundsPicked"] >= grades[t]["liveRounds"]
    ]
    roasted_teams = [t for t in final_teams if t in state.get("roasts", {})]

    if not has_ai_key:
        roast_card = """
  <div class="card">
    <div class="sub" style="margin-bottom:8px;">Draft grade roasts (AI)</div>
    <div style="font-size:12.5px;color:var(--text-dim);">No Anthropic API key configured yet on this server -- grade pages are using the free built-in roast. See anthropic_key.txt.</div>
  </div>
  """
    elif not final_teams:
        roast_card = """
  <div class="card">
    <div class="sub" style="margin-bottom:8px;">Draft grade roasts (AI)</div>
    <div style="font-size:12.5px;color:var(--text-dim);">No teams have finished their draft yet -- nothing to generate.</div>
  </div>
  """
    else:
        n_final = len(final_teams)
        status_line = (
            f"{len(roasted_teams)} of {n_final} finished team{'s' if n_final != 1 else ''} "
            f"{'have' if n_final != 1 else 'has'} an AI roast; the rest use the built-in one."
        )
        roast_card = f"""
  <div class="card">
    <div class="sub" style="margin-bottom:8px;">Draft grade roasts (AI)</div>
    <div style="font-size:12.5px;color:var(--text-dim);margin-bottom:10px;">{status_line}</div>
    <form method="post" action="/entry/generate-grades">
      <button class="primary" type="submit">Generate missing AI roasts</button>
    </form>
    <div style="margin-top:10px;">
      <span class="toggle-link" onclick="document.getElementById('regen').classList.toggle('open')">Regenerate one team &rarr;</span>
    </div>
    <div id="regen" class="override-row">
      <form method="post" action="/entry/generate-grades" style="display:flex;gap:10px;width:100%;align-items:flex-end;">
        <div style="flex:1;">
          <label for="regenTeam">Team</label>
          <select id="regenTeam" name="team">
            {''.join(f'<option value="{t}">{t}</option>' for t in final_teams)}
          </select>
        </div>
        <button class="ghost" type="submit" formaction="/entry/generate-grades">Regenerate</button>
        <button class="danger" type="submit" formaction="/entry/clear-grade" onclick="return confirm('Clear the AI roast for this team? It will fall back to the built-in roast.');">Clear</button>
      </form>
    </div>
  </div>
  """

    body = f"""
  <div class="card">
    <form method="post" action="/entry/pick" id="pickForm">
      {on_clock_html}
      <label for="playerSearch">Player</label>
      <input type="text" id="playerSearch" autocomplete="off" placeholder="Start typing a name...">
      <div id="suggestions" class="suggestions"></div>
      <input type="hidden" id="playerName" name="player_name">
      <button class="primary" type="submit" id="submitBtn" disabled>Record pick</button>
    </form>
  </div>

  <div class="card">
    <form method="post" action="/entry/undo" onsubmit="return confirm('Undo the most recent pick?');">
      <button class="danger" type="submit">Undo last pick</button>
    </form>
  </div>

  <div class="card">
    <div class="sub" style="margin-bottom:8px;">Recent picks</div>
    <div class="recent">{recent_html}</div>
  </div>
  {roast_card}
  <div class="sub"><a class="home-link" href="/entry/logout" style="text-decoration:underline;">Log out</a></div>

  <script>
    const PLAYERS = {player_payload};
    const searchEl = document.getElementById('playerSearch');
    const suggEl = document.getElementById('suggestions');
    const hiddenEl = document.getElementById('playerName');
    const submitBtn = document.getElementById('submitBtn');

    function renderSuggestions(matches) {{
      if (!matches.length) {{ suggEl.classList.remove('open'); suggEl.innerHTML = ''; return; }}
      suggEl.innerHTML = matches.slice(0, 12).map(p =>
        `<div class="suggestion" data-name="${{p.name}}">${{p.name}}<span class="pos">${{p.pos}}${{p.team ? ' &middot; ' + p.team : ''}}</span></div>`
      ).join('');
      suggEl.classList.add('open');
    }}

    searchEl.addEventListener('input', () => {{
      hiddenEl.value = '';
      submitBtn.disabled = true;
      const q = searchEl.value.trim().toLowerCase();
      if (!q) {{ renderSuggestions([]); return; }}
      const matches = PLAYERS.filter(p => p.name.toLowerCase().includes(q));
      renderSuggestions(matches);
    }});

    suggEl.addEventListener('click', (e) => {{
      const row = e.target.closest('.suggestion');
      if (!row) return;
      searchEl.value = row.dataset.name;
      hiddenEl.value = row.dataset.name;
      submitBtn.disabled = false;
      renderSuggestions([]);
    }});

    document.addEventListener('click', (e) => {{
      if (!e.target.closest('#suggestions') && e.target !== searchEl) renderSuggestions([]);
    }});
  </script>
  """
    return page("Draft Entry", body)


@app.route("/entry/pick", methods=["POST"])
def submit_pick():
    if not require_auth():
        return redirect(url_for("login"))

    # Raw (unescaped) values are only ever used as dict-key lookups or written
    # to state.json -- never interpolated into HTML directly. The `_safe`
    # copies are HTML-escaped and used only in messages shown back to the
    # browser, since these are attacker-controllable form fields (a forged
    # request could set player_name to anything, not just what the JS
    # autocomplete offers).
    player_name = request.form.get("player_name", "").strip()
    override_team = request.form.get("override_team", "").strip()
    override_round = request.form.get("override_round", "").strip()
    player_name_safe = html.escape(player_name)
    override_team_safe = html.escape(override_team)

    if not player_name:
        return redirect(url_for("entry_with_msg", msg="Pick a player from the suggestions list first.", kind="err"))

    with StateLock():
        state = load_state()
        pool = load_pool()
        pool_by_name = {p["name"]: p for p in pool}

        player = pool_by_name.get(player_name)
        if not player:
            return redirect(url_for("entry_with_msg", msg=f'"{player_name_safe}" not found in the player pool.', kind="err"))

        derived = g.build_derived_state(state, pool)
        status = pool_by_name[player_name].get("status")
        if status != "available":
            return redirect(
                url_for("entry_with_msg", msg=f"{player_name} is already {status} &mdash; not available.", kind="err")
            )

        if override_team or override_round:
            if not (override_team and override_round):
                return redirect(url_for("entry_with_msg", msg="Set both team and round to override, or leave both blank.", kind="err"))
            if override_team not in state["teams"]:
                return redirect(url_for("entry_with_msg", msg=f"Unknown team: {override_team_safe}", kind="err"))
            try:
                round_ = int(override_round)
            except ValueError:
                return redirect(url_for("entry_with_msg", msg=f"Invalid round: {html.escape(override_round)}", kind="err"))
            if not (1 <= round_ <= state["liveRounds"]):
                return redirect(url_for("entry_with_msg", msg=f"Round must be between 1 and {state['liveRounds']}.", kind="err"))
            team = override_team
            if any(pk["team"] == team and pk["round"] == round_ for pk in state["picks"]):
                return redirect(url_for("entry_with_msg", msg=f"{team} already has a Round {round_} pick recorded.", kind="err"))
        else:
            slot = g.next_pick_slot(state)
            if not slot:
                return redirect(url_for("entry_with_msg", msg="All 12 live rounds are already full.", kind="err"))
            round_, team = slot["round"], slot["team"]

        state["picks"].append({"round": round_, "team": team, "name": player_name, "pos": player["pos"]})
        state["protectResolution"] = g.compute_protect_resolution(state, pool)
        save_state(state)
        regenerate_pages(state, pool)
        broadcast_update()
        git_result = push_backup(f"Live pick: {player_name} -> {team} (R{round_})", state)

    return redirect(
        url_for("entry_with_msg", msg=f"Recorded: {player_name} &rarr; {team} (Round {round_}). Backup: {git_result}.", kind="ok")
    )


@app.route("/entry/undo", methods=["POST"])
def undo_pick():
    if not require_auth():
        return redirect(url_for("login"))

    with StateLock():
        state = load_state()
        pool = load_pool()
        if not state["picks"]:
            return redirect(url_for("entry_with_msg", msg="No picks to undo.", kind="err"))
        removed = state["picks"].pop()
        state["protectResolution"] = g.compute_protect_resolution(state, pool)
        save_state(state)
        regenerate_pages(state, pool)
        broadcast_update()
        git_result = push_backup(f"Undo pick: {removed['name']} ({removed['team']}, R{removed['round']})", state)

    return redirect(
        url_for("entry_with_msg", msg=f"Undid: {removed['name']} &rarr; {removed['team']} (Round {removed['round']}). Backup: {git_result}.", kind="ok")
    )


@app.route("/entry/generate-grades", methods=["POST"])
def generate_grades():
    """Manually triggered (never automatic on a pick/undo -- see generate.py's
    AI-roast module note for why): calls the Anthropic API for the AI roast
    on each team that's finished drafting and doesn't have one cached yet,
    or for a single --team-- team if the form specifies one (used for a
    deliberate re-roll). Always safe to click even with no API key
    configured or no teams finished -- both are handled as a clean message,
    never a crash, and any team the API call fails for just keeps showing
    its free built-in roast."""
    if not require_auth():
        return redirect(url_for("login"))

    api_key = read_anthropic_key()
    if not api_key:
        return redirect(url_for(
            "entry_with_msg",
            msg="No Anthropic API key configured on this server -- see anthropic_key.txt. Grade pages are still using the built-in roast.",
            kind="err",
        ))

    only_team = request.form.get("team", "").strip() or None

    with StateLock():
        state = load_state()
        pool = load_pool()
        grades = g.compute_team_grades(state, pool)
        state.setdefault("roasts", {})

        def is_final(team):
            gd = grades[team]
            return gd["roundsPicked"] > 0 and gd["roundsPicked"] >= gd["liveRounds"]

        if only_team:
            if only_team not in state["teams"]:
                return redirect(url_for("entry_with_msg", msg=f"Unknown team: {html.escape(only_team)}", kind="err"))
            if not is_final(only_team):
                return redirect(url_for("entry_with_msg", msg=f"{html.escape(only_team)} hasn't finished drafting yet.", kind="err"))
            targets = [only_team]
        else:
            targets = [t for t in state["teams"] if is_final(t) and t not in state["roasts"]]

        if not targets:
            msg = "Nothing to generate -- every finished team already has an AI roast." if not only_team else "Nothing to generate."
            return redirect(url_for("entry_with_msg", msg=msg, kind="ok"))

        generated, failed = [], []
        for team in targets:
            roast = g.generate_ai_roast(grades[team], api_key)
            if roast:
                state["roasts"][team] = roast
                generated.append(team)
            else:
                failed.append(team)

        save_state(state)
        regenerate_pages(state, pool)
        broadcast_update()
        git_result = push_backup(f"AI roast generated: {', '.join(generated) or 'none'}", state) if generated else "skipped (nothing generated)"

    if generated and not failed:
        msg = f"Generated AI roast{'s' if len(generated) != 1 else ''} for: {html.escape(', '.join(generated))}. Backup: {git_result}."
        kind = "ok"
    elif generated and failed:
        msg = f"Generated for {html.escape(', '.join(generated))}. Failed for {html.escape(', '.join(failed))} (built-in roast still showing for them). Backup: {git_result}."
        kind = "err"
    else:
        msg = f"AI generation failed for {html.escape(', '.join(failed))} -- check the API key and Web01's internet access. Built-in roast is still showing."
        kind = "err"

    return redirect(url_for("entry_with_msg", msg=msg, kind=kind))


@app.route("/entry/clear-grade", methods=["POST"])
def clear_grade():
    """Removes a team's cached AI roast so its grade page falls back to the
    free built-in roast -- for when a generated one isn't funny, or is just
    wrong somehow. No API call at all, so this can never fail on the network
    side; the only failure modes are a bad team name or nothing to clear."""
    if not require_auth():
        return redirect(url_for("login"))

    team = request.form.get("team", "").strip()
    if not team:
        return redirect(url_for("entry_with_msg", msg="Pick a team to clear.", kind="err"))

    with StateLock():
        state = load_state()
        pool = load_pool()

        if team not in state["teams"]:
            return redirect(url_for("entry_with_msg", msg=f"Unknown team: {html.escape(team)}", kind="err"))
        if team not in state.get("roasts", {}):
            return redirect(url_for("entry_with_msg", msg=f"{html.escape(team)} doesn't have an AI roast to clear.", kind="ok"))

        del state["roasts"][team]
        save_state(state)
        regenerate_pages(state, pool)
        broadcast_update()
        git_result = push_backup(f"Cleared AI roast: {team}", state)

    return redirect(url_for(
        "entry_with_msg",
        msg=f"Cleared the AI roast for {html.escape(team)} -- back to the built-in one. Backup: {git_result}.",
        kind="ok",
    ))


@app.route("/entry/msg")
def entry_with_msg():
    if not require_auth():
        return redirect(url_for("login"))
    msg = request.args.get("msg", "")
    kind = request.args.get("kind", "ok")
    resp = make_response(entry())
    # simplest way to surface a one-shot message without a session-based
    # flash mechanism: re-render entry() then splice the message banner in.
    # (named page_html, not html, so it doesn't shadow the `html` module
    # imported at the top of this file for html.escape())
    page_html = resp.get_data(as_text=True)
    banner = f'<div class="msg {kind}">{msg}</div>'
    page_html = page_html.replace('<div class="wrap">', '<div class="wrap">' + banner, 1)
    resp.set_data(page_html)
    return resp


# === Mock draft sandbox (added 2026-08-22) ================================
# Deliberate near-duplicates of the real /entry routes above, not a shared
# refactor -- the real routes are the ones that must never break on draft
# night, so they're left completely untouched here. Everything below reads
# and writes MOCK_STATE_PATH instead of STATE_PATH, shares the SAME PIN/
# session (require_auth()) as the real entry page since anyone who knows the
# real PIN already has no meaningful new access by also touching fake data,
# and skips push_backup() entirely -- there's nothing here worth a git
# history for.

@app.route("/mock/entry", methods=["GET"])
def mock_entry():
    if not require_auth():
        return redirect(url_for("login"))
    ensure_mock_state()

    state = load_state(MOCK_STATE_PATH)
    pool = load_pool()

    slot = g.next_pick_slot(state)
    if slot:
        on_clock_html = f"""
      <div class="on-clock">
        <div>
          <div class="round">Round {slot['round']} &middot; Pick {len(state['picks']) + 1}</div>
          <div class="who">{slot['team']} is on the clock</div>
        </div>
        <span class="toggle-link" onclick="document.getElementById('override').classList.toggle('open')">Wrong? Override &rarr;</span>
      </div>
      <div id="override" class="override-row">
        <div>
          <label for="ovTeam">Team</label>
          <select id="ovTeam" name="override_team">
            <option value="">(use on-the-clock team)</option>
            {''.join(f'<option value="{t}">{t}</option>' for t in state['teams'])}
          </select>
        </div>
        <div>
          <label for="ovRound">Round</label>
          <select id="ovRound" name="override_round">
            <option value="">(use next round)</option>
            {''.join(f'<option value="{r}">{r}</option>' for r in range(1, state['liveRounds'] + 1))}
          </select>
        </div>
      </div>
      """
    else:
        on_clock_html = '<div class="on-clock"><div class="who">All 12 live rounds are full.</div></div>'

    available_players = sorted(
        [p for p in pool if p["status"] == "available"],
        key=lambda p: (p["pos"], p.get("rank") or 999),
    )
    player_payload = json.dumps(
        [{"name": p["name"], "pos": p["pos"], "team": p.get("nflTeam", "")} for p in available_players]
    )

    recent = list(reversed(state["picks"][-8:]))
    recent_html = (
        "".join(
            f'<div class="row"><span class="name">{pk["name"]}</span><span>R{pk["round"]} &middot; {pk["team"]}</span></div>'
            for pk in recent
        )
        if recent
        else '<div class="row"><span>No picks recorded yet.</span></div>'
    )

    has_ai_key = read_anthropic_key() is not None
    grades = g.compute_team_grades(state, pool)
    final_teams = [
        t for t in state["teams"]
        if grades[t]["roundsPicked"] > 0 and grades[t]["roundsPicked"] >= grades[t]["liveRounds"]
    ]
    roasted_teams = [t for t in final_teams if t in state.get("roasts", {})]

    if not has_ai_key:
        roast_card = """
  <div class="card">
    <div class="sub" style="margin-bottom:8px;">Draft grade roasts (AI)</div>
    <div style="font-size:12.5px;color:var(--text-dim);">No Anthropic API key configured yet on this server -- grade pages are using the free built-in roast. See anthropic_key.txt.</div>
  </div>
  """
    elif not final_teams:
        roast_card = """
  <div class="card">
    <div class="sub" style="margin-bottom:8px;">Draft grade roasts (AI)</div>
    <div style="font-size:12.5px;color:var(--text-dim);">No teams have finished their draft yet -- nothing to generate.</div>
  </div>
  """
    else:
        n_final = len(final_teams)
        status_line = (
            f"{len(roasted_teams)} of {n_final} finished team{'s' if n_final != 1 else ''} "
            f"{'have' if n_final != 1 else 'has'} an AI roast; the rest use the built-in one."
        )
        roast_card = f"""
  <div class="card">
    <div class="sub" style="margin-bottom:8px;">Draft grade roasts (AI)</div>
    <div style="font-size:12.5px;color:var(--text-dim);margin-bottom:10px;">{status_line}</div>
    <form method="post" action="/mock/entry/generate-grades">
      <button class="primary" type="submit">Generate missing AI roasts</button>
    </form>
    <div style="margin-top:10px;">
      <span class="toggle-link" onclick="document.getElementById('regen').classList.toggle('open')">Regenerate one team &rarr;</span>
    </div>
    <div id="regen" class="override-row">
      <form method="post" action="/mock/entry/generate-grades" style="display:flex;gap:10px;width:100%;align-items:flex-end;">
        <div style="flex:1;">
          <label for="regenTeam">Team</label>
          <select id="regenTeam" name="team">
            {''.join(f'<option value="{t}">{t}</option>' for t in final_teams)}
          </select>
        </div>
        <button class="ghost" type="submit" formaction="/mock/entry/generate-grades">Regenerate</button>
        <button class="danger" type="submit" formaction="/mock/entry/clear-grade" onclick="return confirm('Clear the AI roast for this team? It will fall back to the built-in roast.');">Clear</button>
      </form>
    </div>
  </div>
  """

    body = MOCK_BANNER_HTML + f"""
  <div class="card">
    <form method="post" action="/mock/entry/pick" id="pickForm">
      {on_clock_html}
      <label for="playerSearch">Player</label>
      <input type="text" id="playerSearch" autocomplete="off" placeholder="Start typing a name...">
      <div id="suggestions" class="suggestions"></div>
      <input type="hidden" id="playerName" name="player_name">
      <button class="primary" type="submit" id="submitBtn" disabled>Record pick</button>
    </form>
  </div>

  <div class="card">
    <form method="post" action="/mock/entry/undo" onsubmit="return confirm('Undo the most recent mock pick?');">
      <button class="danger" type="submit">Undo last pick</button>
    </form>
  </div>

  <div class="card">
    <div class="sub" style="margin-bottom:8px;">Recent picks</div>
    <div class="recent">{recent_html}</div>
  </div>
  {roast_card}
  <div class="card">
    <div class="sub" style="margin-bottom:8px;">Reset</div>
    <div style="font-size:12.5px;color:var(--text-dim);margin-bottom:10px;">Restores the mock draft to its seed state -- a full, already-completed 12-round demo draft -- discarding any picks/undos/roasts you've made here.</div>
    <form method="post" action="/mock/reset" onsubmit="return confirm('Reset the mock draft back to the seed state? This discards everything you\\'ve done here.');">
      <button class="danger" type="submit">Reset mock draft</button>
    </form>
  </div>

  <div class="sub">
    <a class="home-link" href="/mock/board/draft-board.html" style="text-decoration:underline;">View mock board</a>
    &middot;
    <a class="home-link" href="/entry/logout" style="text-decoration:underline;">Log out</a>
  </div>

  <script>
    const PLAYERS = {player_payload};
    const searchEl = document.getElementById('playerSearch');
    const suggEl = document.getElementById('suggestions');
    const hiddenEl = document.getElementById('playerName');
    const submitBtn = document.getElementById('submitBtn');

    function renderSuggestions(matches) {{
      if (!matches.length) {{ suggEl.classList.remove('open'); suggEl.innerHTML = ''; return; }}
      suggEl.innerHTML = matches.slice(0, 12).map(p =>
        `<div class="suggestion" data-name="${{p.name}}">${{p.name}}<span class="pos">${{p.pos}}${{p.team ? ' &middot; ' + p.team : ''}}</span></div>`
      ).join('');
      suggEl.classList.add('open');
    }}

    searchEl.addEventListener('input', () => {{
      hiddenEl.value = '';
      submitBtn.disabled = true;
      const q = searchEl.value.trim().toLowerCase();
      if (!q) {{ renderSuggestions([]); return; }}
      const matches = PLAYERS.filter(p => p.name.toLowerCase().includes(q));
      renderSuggestions(matches);
    }});

    suggEl.addEventListener('click', (e) => {{
      const row = e.target.closest('.suggestion');
      if (!row) return;
      searchEl.value = row.dataset.name;
      hiddenEl.value = row.dataset.name;
      submitBtn.disabled = false;
      renderSuggestions([]);
    }});

    document.addEventListener('click', (e) => {{
      if (!e.target.closest('#suggestions') && e.target !== searchEl) renderSuggestions([]);
    }});
  </script>
  """
    return page("Mock Draft Entry", body)


@app.route("/mock/entry/pick", methods=["POST"])
def mock_submit_pick():
    if not require_auth():
        return redirect(url_for("login"))
    ensure_mock_state()

    player_name = request.form.get("player_name", "").strip()
    override_team = request.form.get("override_team", "").strip()
    override_round = request.form.get("override_round", "").strip()
    player_name_safe = html.escape(player_name)
    override_team_safe = html.escape(override_team)

    if not player_name:
        return redirect(url_for("mock_entry_with_msg", msg="Pick a player from the suggestions list first.", kind="err"))

    with StateLock(MOCK_LOCK_PATH):
        state = load_state(MOCK_STATE_PATH)
        pool = load_pool()
        pool_by_name = {p["name"]: p for p in pool}

        player = pool_by_name.get(player_name)
        if not player:
            return redirect(url_for("mock_entry_with_msg", msg=f'"{player_name_safe}" not found in the player pool.', kind="err"))

        derived = g.build_derived_state(state, pool)
        status = pool_by_name[player_name].get("status")
        if status != "available":
            return redirect(
                url_for("mock_entry_with_msg", msg=f"{player_name} is already {status} &mdash; not available.", kind="err")
            )

        if override_team or override_round:
            if not (override_team and override_round):
                return redirect(url_for("mock_entry_with_msg", msg="Set both team and round to override, or leave both blank.", kind="err"))
            if override_team not in state["teams"]:
                return redirect(url_for("mock_entry_with_msg", msg=f"Unknown team: {override_team_safe}", kind="err"))
            try:
                round_ = int(override_round)
            except ValueError:
                return redirect(url_for("mock_entry_with_msg", msg=f"Invalid round: {html.escape(override_round)}", kind="err"))
            if not (1 <= round_ <= state["liveRounds"]):
                return redirect(url_for("mock_entry_with_msg", msg=f"Round must be between 1 and {state['liveRounds']}.", kind="err"))
            team = override_team
            if any(pk["team"] == team and pk["round"] == round_ for pk in state["picks"]):
                return redirect(url_for("mock_entry_with_msg", msg=f"{team} already has a Round {round_} pick recorded.", kind="err"))
        else:
            slot = g.next_pick_slot(state)
            if not slot:
                return redirect(url_for("mock_entry_with_msg", msg="All 12 live rounds are already full.", kind="err"))
            round_, team = slot["round"], slot["team"]

        state["picks"].append({"round": round_, "team": team, "name": player_name, "pos": player["pos"]})
        state["protectResolution"] = g.compute_protect_resolution(state, pool)
        save_state(state, MOCK_STATE_PATH)
        regenerate_mock_pages(state, pool)
        broadcast_update()

    return redirect(
        url_for("mock_entry_with_msg", msg=f"Recorded: {player_name} &rarr; {team} (Round {round_}).", kind="ok")
    )


@app.route("/mock/entry/undo", methods=["POST"])
def mock_undo_pick():
    if not require_auth():
        return redirect(url_for("login"))
    ensure_mock_state()

    with StateLock(MOCK_LOCK_PATH):
        state = load_state(MOCK_STATE_PATH)
        pool = load_pool()
        if not state["picks"]:
            return redirect(url_for("mock_entry_with_msg", msg="No picks to undo.", kind="err"))
        removed = state["picks"].pop()
        state["protectResolution"] = g.compute_protect_resolution(state, pool)
        save_state(state, MOCK_STATE_PATH)
        regenerate_mock_pages(state, pool)
        broadcast_update()

    return redirect(
        url_for("mock_entry_with_msg", msg=f"Undid: {removed['name']} &rarr; {removed['team']} (Round {removed['round']}).", kind="ok")
    )


@app.route("/mock/entry/generate-grades", methods=["POST"])
def mock_generate_grades():
    if not require_auth():
        return redirect(url_for("login"))
    ensure_mock_state()

    api_key = read_anthropic_key()
    if not api_key:
        return redirect(url_for(
            "mock_entry_with_msg",
            msg="No Anthropic API key configured on this server -- see anthropic_key.txt. Grade pages are still using the built-in roast.",
            kind="err",
        ))

    only_team = request.form.get("team", "").strip() or None

    with StateLock(MOCK_LOCK_PATH):
        state = load_state(MOCK_STATE_PATH)
        pool = load_pool()
        grades = g.compute_team_grades(state, pool)
        state.setdefault("roasts", {})

        def is_final(team):
            gd = grades[team]
            return gd["roundsPicked"] > 0 and gd["roundsPicked"] >= gd["liveRounds"]

        if only_team:
            if only_team not in state["teams"]:
                return redirect(url_for("mock_entry_with_msg", msg=f"Unknown team: {html.escape(only_team)}", kind="err"))
            if not is_final(only_team):
                return redirect(url_for("mock_entry_with_msg", msg=f"{html.escape(only_team)} hasn't finished drafting yet.", kind="err"))
            targets = [only_team]
        else:
            targets = [t for t in state["teams"] if is_final(t) and t not in state["roasts"]]

        if not targets:
            msg = "Nothing to generate -- every finished team already has an AI roast." if not only_team else "Nothing to generate."
            return redirect(url_for("mock_entry_with_msg", msg=msg, kind="ok"))

        generated, failed = [], []
        for team in targets:
            roast = g.generate_ai_roast(grades[team], api_key)
            if roast:
                state["roasts"][team] = roast
                generated.append(team)
            else:
                failed.append(team)

        save_state(state, MOCK_STATE_PATH)
        regenerate_mock_pages(state, pool)
        broadcast_update()

    if generated and not failed:
        msg = f"Generated AI roast{'s' if len(generated) != 1 else ''} for: {html.escape(', '.join(generated))}."
        kind = "ok"
    elif generated and failed:
        msg = f"Generated for {html.escape(', '.join(generated))}. Failed for {html.escape(', '.join(failed))} (built-in roast still showing for them)."
        kind = "err"
    else:
        msg = f"AI generation failed for {html.escape(', '.join(failed))} -- check the API key and Web01's internet access. Built-in roast is still showing."
        kind = "err"

    return redirect(url_for("mock_entry_with_msg", msg=msg, kind=kind))


@app.route("/mock/entry/clear-grade", methods=["POST"])
def mock_clear_grade():
    if not require_auth():
        return redirect(url_for("login"))
    ensure_mock_state()

    team = request.form.get("team", "").strip()
    if not team:
        return redirect(url_for("mock_entry_with_msg", msg="Pick a team to clear.", kind="err"))

    with StateLock(MOCK_LOCK_PATH):
        state = load_state(MOCK_STATE_PATH)
        pool = load_pool()

        if team not in state["teams"]:
            return redirect(url_for("mock_entry_with_msg", msg=f"Unknown team: {html.escape(team)}", kind="err"))
        if team not in state.get("roasts", {}):
            return redirect(url_for("mock_entry_with_msg", msg=f"{html.escape(team)} doesn't have an AI roast to clear.", kind="ok"))

        del state["roasts"][team]
        save_state(state, MOCK_STATE_PATH)
        regenerate_mock_pages(state, pool)
        broadcast_update()

    return redirect(url_for(
        "mock_entry_with_msg",
        msg=f"Cleared the AI roast for {html.escape(team)} -- back to the built-in one.",
        kind="ok",
    ))


@app.route("/mock/reset", methods=["POST"])
def mock_reset():
    """Copies mock_state.seed.json back over the live mock_state.json --
    the mock equivalent of state.template.json, except resettable any time
    since there's no real draft-day stakes riding on it."""
    if not require_auth():
        return redirect(url_for("login"))

    if not os.path.exists(MOCK_SEED_PATH):
        return redirect(url_for("mock_entry_with_msg", msg=f"No seed file found at {MOCK_SEED_PATH}.", kind="err"))

    with StateLock(MOCK_LOCK_PATH):
        seed = json.load(open(MOCK_SEED_PATH))
        save_state(seed, MOCK_STATE_PATH)
        pool = load_pool()
        regenerate_mock_pages(seed, pool)
        broadcast_update()

    return redirect(url_for("mock_entry_with_msg", msg="Mock draft reset to the seed state (a full 12-round demo draft).", kind="ok"))


@app.route("/mock/entry/msg")
def mock_entry_with_msg():
    if not require_auth():
        return redirect(url_for("login"))
    msg = request.args.get("msg", "")
    kind = request.args.get("kind", "ok")
    resp = make_response(mock_entry())
    page_html = resp.get_data(as_text=True)
    banner = f'<div class="msg {kind}">{msg}</div>'
    page_html = page_html.replace('<div class="wrap">', '<div class="wrap">' + banner, 1)
    resp.set_data(page_html)
    return resp


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5055"))
    # Every (re)start rebuilds the static pages from the current code +
    # state.json. Without this, a code-only update (a modal style tweak, a
    # new column) sits invisible on disk until the next real pick or undo
    # regenerates the pages -- deploy.sh restarts the service but nothing
    # else triggers a rebuild. Best-effort: a missing/corrupt state.json at
    # this exact instant shouldn't stop the app from starting.
    try:
        regenerate_pages(load_state(), load_pool())
    except Exception as e:
        print(f"Startup page regeneration skipped: {e}")
    # Same idea for the mock sandbox (added 2026-08-22) -- without this, the
    # mock board pages only refresh when someone actually submits/undoes a
    # mock pick, generates/clears a roast, or hits reset, so they'd silently
    # keep showing whatever version was current the last time any of that
    # happened -- exactly the same staleness bug the real board pages had
    # before the fix above, just for the mock side. ensure_mock_state() first
    # so this also works as the very first bootstrap on a brand new install,
    # with nobody needing to visit /mock/entry by hand before it exists.
    try:
        ensure_mock_state()
        regenerate_mock_pages(load_state(MOCK_STATE_PATH), load_pool())
    except Exception as e:
        print(f"Startup mock page regeneration skipped: {e}")
    # threaded=True is required now, not just nice-to-have -- /entry/events
    # holds a long-lived connection per viewer, and without threading that
    # single connection would block every other request (pick entry, board
    # loads) for as long as it's open. Fine for Werkzeug's dev server at this
    # scale (a home-lab league, a handful of concurrent viewers).
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
