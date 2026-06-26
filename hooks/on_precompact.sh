#!/usr/bin/env bash
# PreCompact hook.
#
# IMPORTANT: per the official docs (code.claude.com/docs/en/hooks),
# PreCompact's JSON output only supports `decision`/`reason` (to block
# compaction) plus universal fields — it does NOT support
# `additionalContext`. It cannot inject anything into the compacted
# summary. Re-injection is PostCompact's job (see hooks/on_postcompact.sh).
#
# So this hook's honest, achievable job: snapshot the current checkpoint
# to a durable file *before* compaction happens, as a safety net in case
# the checkpoint itself is mid-edit or something goes wrong. It never
# blocks compaction (decision: block is not used here) and always exits 0.
set -euo pipefail

input="$(cat)"

python3 -c '
import json, os, sys, datetime

try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)

cwd = data.get("cwd") or os.getcwd()
breadcrumbs_dir = os.path.join(cwd, ".breadcrumbs")
checkpoint = os.path.join(breadcrumbs_dir, "checkpoint.md")
snapshot = os.path.join(breadcrumbs_dir, "last_precompact_snapshot.md")

if not os.path.exists(checkpoint):
    sys.exit(0)

with open(checkpoint, "r") as f:
    content = f.read()

os.makedirs(breadcrumbs_dir, exist_ok=True)
ts = datetime.datetime.now().isoformat(timespec="seconds")
with open(snapshot, "w") as f:
    f.write("<!-- snapshotted by breadcrumbs PreCompact hook at " + ts + " -->\n")
    f.write(content)

print(json.dumps({
    "systemMessage": "breadcrumbs: checkpoint snapshotted before compaction."
}))
' "$input"

exit 0
