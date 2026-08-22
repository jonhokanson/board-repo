# Deploying the live pick-entry app to Web01

This adds a small self-hosted app (`draft_app.py`) that runs on Web01 itself, so picks can be
entered directly at the draft table instead of routing through chat. Once it's live, it becomes
the single source of truth for `state.json` and regenerates the board pages instantly on every
pick, with a background push to GitHub for backup/history.

The app's code lives in the `v2-live-app` branch of `board-repo` (the same repo the static site
syncs from, on `main` -- these are two independent branches serving two independent purposes).
That means updates to the code itself can ship the same way the board always has: Claude pushes
a fix to `v2-live-app`, you run `deploy.sh` on Web01 to pull it and restart -- no manual file
copying needed after this initial setup.

**Do this well before draft night, with time to test.** This is a real architecture change --
static-only becomes "static pages + a small live backend" -- and it deserves a dry run.

## 1. Clone the app code

```
sudo git clone -b v2-live-app https://github.com/jonhokanson/board-repo.git /opt/tbml-draft-app
sudo git config --system --add safe.directory /opt/tbml-draft-app
```
(The `safe.directory` line avoids the same "dubious ownership" error we hit setting up the
static-site sync -- needed because the clone happens as root/you, but the service later runs as
`www-data`.)

You should now have `/opt/tbml-draft-app/draft_app.py`, `generate.py`, `yahoo_ids.py`,
`pool.json`, `requirements.txt`, `tbml-draft-app.service`, `deploy.sh`, and
`state.template.json` (the real, all-10-teams Keep/Protect data with zero picks -- this becomes
your live `state.json` in step 3, and only that one time).

## 2. Python environment

```
cd /opt/tbml-draft-app
sudo apt install -y python3-venv   # if not already present
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt
```

## 3. Config/data files (created once, never touched by future `deploy.sh` runs)

**The live state file** -- one-time copy from the template committed to git:
```
sudo cp /opt/tbml-draft-app/state.template.json /opt/tbml-draft-app/state.json
```
From this point on, `state.json` is git-ignored -- `deploy.sh` pulls code updates but will never
overwrite it, so your live picks are safe across every future update.

**PIN** -- choose a real one, not a placeholder:
```
echo "YOUR_PIN_HERE" | sudo tee /opt/tbml-draft-app/pin.txt
```

**Session secret** -- generated once so restarting the app doesn't log everyone out mid-draft:
```
sudo python3 -c "import os; print(os.urandom(24).hex())" | sudo tee /opt/tbml-draft-app/secret_key.txt
```

**Anthropic API key** -- optional, only needed for the AI-generated draft-grade roast (added
2026-08-22; without this file the feature just falls back to the free built-in roast, so it's
safe to skip this step entirely and add it later). Get a key from console.anthropic.com (Settings
-> API Keys), then:
```
echo "YOUR_KEY_HERE" | sudo tee /opt/tbml-draft-app/anthropic_key.txt
sudo chown www-data:www-data /opt/tbml-draft-app/anthropic_key.txt
sudo chmod 600 /opt/tbml-draft-app/anthropic_key.txt
```
No systemd/env var changes or restart needed -- `draft_app.py` reads this file fresh every time
someone clicks "Generate" on the `/entry` page.

## 3b. Mock draft sandbox (added 2026-08-22, optional)

A second, fully independent copy of the live app -- its own state file, its own board pages, its
own AI roasts -- for trying things out (a new feature, a scoring question, "what does this look
like mid-draft") without any risk of touching the real draft. Same PIN, same `/entry`-style pick
form, reachable at `/mock/entry`; its landing page (`/mock`) links to the mock board/players/
keep-protect/grades pages. It's on the `v2-live-app` branch alongside everything else, so
`deploy.sh`/`full-deploy.sh` picks it up automatically -- these steps are just the one-time setup.

**Seed the mock state** -- same one-time-copy idea as `state.template.json` -> `state.json`, except
this seed is a full, already-completed 12-round demo draft (so the mock board looks populated
immediately) and can be replayed any time from a "Reset mock draft" button on `/mock/entry`:
```
sudo cp /opt/tbml-draft-app/mock_state.seed.json /opt/tbml-draft-app/mock_state.json
sudo chown www-data:www-data /opt/tbml-draft-app/mock_state.json
```
(If you skip this, the first visit to `/mock/entry` or click of "Reset mock draft" does it for you.)

**Output directory** -- the mock board pages are served the same static way as the real ones, from
a new `/var/www/html/mock/board` directory that nothing else creates. The app will create it on
first write if it's missing, but it's cleaner to make it explicit up front:
```
sudo mkdir -p /var/www/html/mock/board
sudo chown -R www-data:www-data /var/www/html/mock
```

**Systemd env vars** -- `MOCK_BOARD_OUT`/`MOCK_LIST_OUT`/`MOCK_KP_OUT`/`MOCK_GRADES_OUT_DIR` are new
`Environment=` lines added to `tbml-draft-app.service` (see step 7's file) pointing at
`/var/www/html/mock/board/*`. `deploy.sh`/`full-deploy.sh` only pull *code*, never the systemd unit
file itself -- so after this update lands, install the refreshed unit file once by hand and restart
(this is the same one-time step needed any time a new `Environment=` line is added):
```
sudo cp /opt/tbml-draft-app/tbml-draft-app.service /etc/systemd/system/tbml-draft-app.service
sudo systemctl daemon-reload
sudo systemctl restart tbml-draft-app
```

**nginx** -- the rendered mock *pages* (`/mock/board/*.html`, `/mock/index.html`) are plain static
files under the existing document root, so they need no nginx changes. But the mock *pick-entry
routes* (`/mock/entry` and everything under it, `/mock/reset`) are Flask routes, exactly like
`/entry` -- they need their own proxy block, or nginx will 404 them as missing static files before
they ever reach the app. See step 8 below, which now includes these alongside `/entry`.

**No separate git remote/token needed** -- mock picks are never pushed to GitHub (see the code
comment on `push_backup()`), and `mock_state.json`/`mock_state.json.lock` are already git-ignored
so `deploy.sh` will never touch your in-progress mock picks.

## 4. Ownership

The service runs as `www-data` (same user as `board-sync.service` used to), and needs to write
`state.json`, the lock file, and the regenerated pages -- and to `git pull` during a `deploy.sh`
run:
```
sudo chown -R www-data:www-data /opt/tbml-draft-app
```

## 5. Git push access for backups

Web01's `github` remote (in `/var/www/html`) has only ever been used to *fetch*. For the app to
*push* pick history back to GitHub, it needs its own write-scoped token. Get a fresh fine-grained
PAT from GitHub (same process as before: Settings -> Developer settings -> Fine-grained tokens --
scope it to just `board-repo`, Contents: Read and write), then embed it directly in the remote URL
so it works regardless of which user's `$HOME` the service ends up using:
```
sudo git -C /var/www/html remote set-url github https://x-access-token:<NEW_TOKEN>@github.com/jonhokanson/board-repo.git
```
Note this token is only for the `/var/www/html` remote (state/page backups pushed to `main`).
The `/opt/tbml-draft-app` clone only ever *pulls* from the public repo's `v2-live-app` branch, so
it needs no credentials at all.

## 6. Stop the old sync timer

**This is the important part.** Once the app is live, it owns `/var/www/html/board/*.html`
directly -- it writes there itself and pushes its own commits. If `board-sync.timer` is still
running, it'll `git reset --hard` on its next tick and can clobber whatever the app just wrote
before that write gets committed. Turn it off:
```
sudo systemctl stop board-sync.timer
sudo systemctl disable board-sync.timer
```
(If you ever want to push a *style/code* update to `index.html` from the Claude cloud sandbox
again after this point, do it manually with `sudo git -C /var/www/html pull github main` rather
than re-enabling the timer.)

## 7. Install and start the service

```
sudo cp /opt/tbml-draft-app/tbml-draft-app.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tbml-draft-app
sudo systemctl status tbml-draft-app --no-pager
sudo journalctl -u tbml-draft-app -n 20 --no-pager
```
Should show the Flask app running and listening on `127.0.0.1:5055` with no errors.

## 8. nginx: proxy /entry (and /mock/entry, /mock/reset) to the app

Everything else keeps being served as static files exactly as today -- only the pick-entry paths
(the forms and their APIs, real and mock alike) need to reach the live app. Add this inside the
existing `server {}` block (same file as the current `root /var/www/html;` line):
```
location /entry {
    proxy_pass http://127.0.0.1:5055;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

location /entry/events {
    proxy_pass http://127.0.0.1:5055;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
}

location /mock/entry {
    proxy_pass http://127.0.0.1:5055;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

location /mock/reset {
    proxy_pass http://127.0.0.1:5055;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```
The `/entry/events` block is for the real-time board updates (Server-Sent Events) -- every open
board page holds a long-lived connection here so it can be pushed a refresh the instant a pick
lands, instead of polling on a timer. It needs `proxy_buffering off` specifically, or nginx will
hold the whole response in a buffer instead of streaming it through as it's generated, which
silently breaks the real-time push (the page would still work, just fall back to the safety-net
poll every 30s). nginx matches the more specific `/entry/events` block for that path automatically,
so this doesn't change anything about how `/entry` itself is handled.

The `/mock/entry` block is a prefix match, so it also covers `/mock/entry/pick`,
`/mock/entry/undo`, `/mock/entry/generate-grades`, `/mock/entry/clear-grade`, and
`/mock/entry/msg` -- every mock pick-entry route lives under that one path. `/mock/reset` needs
its own block since it doesn't start with `/mock/entry`. Neither needs the SSE-specific settings
-- the mock pages reuse the real `/entry/events` stream rather than opening a second one (see
"Mock draft sandbox" above), so there's no long-lived connection to worry about here. Without
these two blocks, `/mock/entry` and `/mock/reset` 404 as missing static files before ever
reaching the app -- this is exactly what happened on first rollout (2026-08-22): the mock routes
existed in the code and the self-healing bootstrap worked fine once traffic reached them, but
nginx was never told to send that traffic there in the first place, so `/var/www/html/mock/board`
stayed empty no matter how many times the app was redeployed or restarted.

Then:
```
sudo nginx -t
sudo systemctl reload nginx
```

## 9. Test it

Visit `http://192.168.200.223/entry` -- should prompt for the PIN, then show the entry form with
"Chili Dogs is on the clock" (Round 1, Pick 1) and a player search box. Enter a test pick, confirm
`http://192.168.200.223/board/draft-board.html` updates within a second or two (no 15s wait
anymore), then use "Undo last pick" to clean it back up before draft night.

If the mock draft sandbox is set up, also visit `http://192.168.200.223/mock/entry` -- same PIN,
should show a fully-populated demo draft (via the self-healing bootstrap from
`mock_state.seed.json`) with an amber "Mock Draft" banner. Confirm
`http://192.168.200.223/mock/board/draft-board.html` loads too. If either 404s, it's almost always
the nginx blocks from step 8 above being missing.

## Shipping a code fix or update after this

When Claude has a fix or a new feature ready, it pushes to the `v2-live-app` branch same as
always. On Web01, just run:
```
sudo /opt/tbml-draft-app/deploy.sh
```
This pulls the latest code and restarts the service -- one command, nothing to copy by hand.
Avoid running it in the middle of someone submitting a pick (the ~1 second restart will interrupt
that one request); between picks is always safe. `state.json`, `pin.txt`, and `secret_key.txt`
are git-ignored, so this can never touch your live draft data or PIN.

If a *style-only* update to `index.html` ships (the one page the live app doesn't manage), that
still goes through the old path since the timer is off: `sudo git -C /var/www/html pull github main`.

## If something's badly broken and you need to fall back

Stop the app (`sudo systemctl stop tbml-draft-app`), re-enable the timer
(`sudo systemctl enable --now board-sync.timer`), and go back to telling Claude picks in chat like
before. `main`'s own commit history is the safety net here (there's no separate rollback tag to
maintain) -- `git -C /var/www/html log --oneline` shows every past state, and
`git -C /var/www/html reset --hard <commit>` (as `www-data`, matching the timer's own permissions)
gets you back to any of them if a bad push ever needs undoing.
