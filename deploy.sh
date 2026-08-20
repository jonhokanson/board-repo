#!/bin/bash
# deploy.sh -- pulls the latest app code (draft_app.py / generate.py / etc.)
# from GitHub and restarts the live draft app. Run this on Web01 whenever
# Claude says a code fix or update is ready.
#
# Usage:  sudo /opt/tbml-draft-app/deploy.sh
#
# Safe to run any time EXCEPT mid-pick -- restarting the service takes about
# a second and will interrupt any request that's in flight at that exact
# moment. Best used between picks, not while someone's mid-submit.
#
# What this does NOT touch: state.json, pin.txt, secret_key.txt. Those are
# runtime config/data, not code -- they're git-ignored on purpose so a pull
# here can never clobber live draft picks or your PIN.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Pulling latest app code from v2-live-app..."
sudo -u www-data git pull origin v2-live-app

echo "==> Restarting tbml-draft-app..."
systemctl restart tbml-draft-app

sleep 1
echo "==> Status:"
systemctl status tbml-draft-app --no-pager -l | head -15
