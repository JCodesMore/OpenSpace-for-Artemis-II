#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."
python3 -m poller.poller --output "$SCRIPT_DIR/artemis2_live.dat" --archive-dir "$SCRIPT_DIR/archive" --log-dir "$SCRIPT_DIR/logs"
