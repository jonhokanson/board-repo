#!/bin/bash
# full-deploy.sh -- the one command for every update Claude ships.
#
# Combines the two steps that previously had to be run by hand:
#   1. deploy.sh   -- pulls app code (v2-live-app: draft_app.py, generate.py,
#                      etc.) and restarts the service.
#   2. site sync   -- pulls site content (main: index.html, favicons, and
#                      the board/*.html pages) into /var/www/html.
#
# Usage: sudo bash /opt/tbml-draft-app/full-deploy.sh
#
# Same caveat as deploy.sh: safe to run any time EXCEPT mid-pick -- the
# restart takes about a second and will interrupt a request that's in
# flight at that exact moment. Best used between picks.
set -euo pipefail

echo "=== 1/2: app code (v2-live-app) ==="
bash /opt/tbml-draft-app/deploy.sh

echo
echo "=== 2/2: site content (main) ==="
# The checkout+pull pair sometimes needs to run twice back to back -- the
# live app can rewrite board/*.html again in the moment between the two
# commands (it just restarted and regenerates on startup), which re-triggers
# the "local changes would be overwritten by merge" conflict on the pull.
for attempt in 1 2; do
    sudo -u www-data git -C /var/www/html checkout -- board/draft-board.html board/draft-players.html board/keep-protect.html
    if sudo -u www-data git -C /var/www/html pull github main; then
        break
    fi
done

echo
echo "=== Done. Live site is fully up to date. ==="
