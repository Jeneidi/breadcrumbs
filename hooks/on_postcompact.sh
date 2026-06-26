#!/usr/bin/env bash
# PostCompact hook: fires right after compaction completes, when the lossy
# summary has just replaced history. This is the hook that actually
# re-injects the checkpoint (PreCompact cannot — see on_precompact.sh).
# Falls back to the last PreCompact snapshot if the live checkpoint is
# missing. Emits nothing if neither file exists. Always exits 0.
set -euo pipefail

input="$(cat)"

python3 -c '
import json, os, sys

try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)

cwd = data.get("cwd") or os.getcwd()
breadcrumbs_dir = os.path.join(cwd, ".breadcrumbs")
checkpoint = os.path.join(breadcrumbs_dir, "checkpoint.md")
snapshot = os.path.join(breadcrumbs_dir, "last_precompact_snapshot.md")

path = checkpoint if os.path.exists(checkpoint) else (snapshot if os.path.exists(snapshot) else None)
if path is None:
    sys.exit(0)

with open(path, "r") as f:
    content = f.read()

prefix = (
    "The following task checkpoint was preserved by breadcrumbs across "
    "compaction — treat it as ground truth for active task state:\n\n"
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostCompact",
        "additionalContext": prefix + content
    }
}))
' "$input"

exit 0
