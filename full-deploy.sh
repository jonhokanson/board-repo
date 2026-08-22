#!/bin/bash
# full-deploy.sh -- the one command for every update Claude ships.
#
# Combines the two steps that previously had to be run by hand:
#   1. site sync   -- pulls site content (main: index.html, favicons, and
#                      the board/*.html pages) into /var/www/html.
#   2. deploy.sh   -- pulls app code (v2-live-app: draft_app.py, generate.py,
#                      etc.) and restarts the service.
#
# Usage: sudo bash /opt/tbml-draft-app/full-deploy.sh
#
# Same caveat as deploy.sh: safe to run any time EXCEPT mid-pick -- the
# restart takes about a second and will interrupt a request that's in
# flight at that exact moment. Best used between picks.
#
# ORDER MATTERS HERE (fixed 2026-08-22 -- see below). Site sync runs FIRST,
# app deploy/restart runs SECOND -- this is the opposite of how this script
# originally worked, and the original order silently threw away every
# board-page update shipped through it. Read the comment above the site-sync
# block for the full story before reordering these again.
set -euo pipefail

echo "=== 1/2: site content (main) ==="
# The live app writes board/draft-board.html, board/draft-players.html, and
# board/keep-protect.html directly to disk on every pick/undo AND on every
# app restart (it regenerates on startup so a code-only change doesn't sit
# invisible until the next real pick -- see draft_app.py's __main__ block).
# That means these three files almost always have uncommitted local changes
# relative to git's last commit, which `git pull` refuses to clobber. The
# checkout here discards those local changes so the pull can proceed
# cleanly -- it's *supposed* to only be throwing away stale leftovers from
# before this deploy, not anything meaningful.
#
# THIS STEP MUST RUN BEFORE deploy.sh, NOT AFTER. The original version of
# this script ran deploy.sh first (which restarts the app and regenerates
# fresh board pages, embedding whatever APP_VERSION was just deployed) and
# THEN ran this checkout+pull -- which discarded that freshly-regenerated
# content and reset the three board files back to whatever was last
# actually committed to main (from the last real pick's push_backup(), or
# further back than that if no real picks have landed yet). Every version
# bump shipped through the old ordering was silently reverted on the live
# board pages the moment full-deploy.sh ran, while index.html (synced
# separately, not touched by this checkout) kept showing the correct
# version -- which is exactly the mismatch Jon caught (index at v0.2.6.1,
# board/players/keep-protect stuck at v0.2.1.12, the version last actually
# committed). Running site-sync first means the checkout+pull discards only
# genuinely-stale content, and deploy.sh's restart afterward writes the
# final, correct version straight to disk -- with nothing left to revert it.
for attempt in 1 2; do
    sudo -u www-data git -C /var/www/html checkout -- board/draft-board.html board/draft-players.html board/keep-protect.html
    if sudo -u www-data git -C /var/www/html pull github main; then
        break
    fi
done

echo
echo "=== 2/2: app code (v2-live-app) ==="
bash /opt/tbml-draft-app/deploy.sh

echo
echo "=== Done. Live site is fully up to date. ==="
