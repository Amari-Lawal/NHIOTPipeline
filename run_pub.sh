#!/usr/bin/env bash
if [ -n "$1" ]; then
    echo "[PUBLISHER] Requesting remote subscriber to switch branch to '$1'..."
    python3 -m NHIOTPub.switch_branch "$1"
fi

python3 -m unittest discover -s NHIOTPub/tests -t .