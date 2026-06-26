#!/usr/bin/env bash
# Stop hook: reminds Claude to update .breadcrumbs/checkpoint.md if it's
# missing or stale relative to the transcript. Never blocks stopping —
# this is a reminder, not a gate. Always exits 0.
set -euo pipefail

input="$(cat)"

python3 -c '
import json, os, sys

try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)

cwd = data.get("cwd") or os.getcwd()
transcript_path = data.get("transcript_path")
checkpoint = os.path.join(cwd, ".breadcrumbs", "checkpoint.md")

stale = True
if os.path.exists(checkpoint):
    if transcript_path and os.path.exists(transcript_path):
        stale = os.path.getmtime(checkpoint) < os.path.getmtime(transcript_path)
    else:
        stale = False  # no transcript to compare against; presence is enough

if stale:
    reminder = (
        "breadcrumbs: .breadcrumbs/checkpoint.md is missing or stale. "
        "Per the breadcrumbs skill, update it now — Active Task, Decisions, "
        "Files Touched, Open TODOs, Hard Constraints — before this session "
        "context risks being compacted."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": reminder
        }
    }))
' "$input"

exit 0
