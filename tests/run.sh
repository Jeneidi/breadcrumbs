#!/usr/bin/env bash
# Test suite for breadcrumbs hooks. Plain bash + python3 stdlib asserts.
# Exits non-zero if any test fails.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS="$ROOT/hooks"
PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); echo "PASS: $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL: $1"; }

# --- Test 1: PreCompact creates a matching snapshot ---
t1_dir=$(mktemp -d)
mkdir -p "$t1_dir/.breadcrumbs"
cat > "$t1_dir/.breadcrumbs/checkpoint.md" <<'EOF'
## Active Task
PRECOMPACT_MARKER_AAA111

## Decisions

## Files Touched

## Open TODOs

## Hard Constraints
EOF

t1_out=$(echo "{\"cwd\": \"$t1_dir\"}" | "$HOOKS/on_precompact.sh")
t1_status=$?
t1_snapshot="$t1_dir/.breadcrumbs/last_precompact_snapshot.md"

if [ $t1_status -eq 0 ] && [ -f "$t1_snapshot" ] && grep -q "PRECOMPACT_MARKER_AAA111" "$t1_snapshot"; then
    ok "PreCompact creates snapshot with matching content, exits 0"
else
    bad "PreCompact creates snapshot with matching content, exits 0 (status=$t1_status, output=$t1_out)"
fi
rm -rf "$t1_dir"

# --- Test 2: PostCompact re-injects checkpoint verbatim via additionalContext ---
t2_dir=$(mktemp -d)
mkdir -p "$t2_dir/.breadcrumbs"
cat > "$t2_dir/.breadcrumbs/checkpoint.md" <<'EOF'
## Active Task
POSTCOMPACT_MARKER_BBB222

## Decisions

## Files Touched

## Open TODOs

## Hard Constraints
EOF

t2_out=$(echo "{\"cwd\": \"$t2_dir\"}" | "$HOOKS/on_postcompact.sh")
t2_status=$?

t2_check=$(printf '%s' "$t2_out" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
    ctx = data.get('hookSpecificOutput', {}).get('additionalContext', '')
    print('FOUND' if 'POSTCOMPACT_MARKER_BBB222' in ctx else 'MISSING')
except Exception as e:
    print('ERROR:', e)
")

if [ $t2_status -eq 0 ] && [ "$t2_check" = "FOUND" ]; then
    ok "PostCompact additionalContext contains marker verbatim"
else
    bad "PostCompact additionalContext contains marker verbatim (status=$t2_status, check=$t2_check)"
fi
rm -rf "$t2_dir"

# --- Test 3: Stop hook with missing checkpoint emits non-empty additionalContext ---
t3_dir=$(mktemp -d)
t3_transcript="$t3_dir/transcript.jsonl"
touch "$t3_transcript"

t3_out=$(echo "{\"cwd\": \"$t3_dir\", \"transcript_path\": \"$t3_transcript\"}" | "$HOOKS/on_stop.sh")
t3_status=$?

t3_check=$(printf '%s' "$t3_out" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
    ctx = data.get('hookSpecificOutput', {}).get('additionalContext', '')
    print('NONEMPTY' if ctx else 'EMPTY')
except Exception as e:
    print('ERROR:', e)
")

if [ $t3_status -eq 0 ] && [ "$t3_check" = "NONEMPTY" ]; then
    ok "Stop hook with missing checkpoint emits non-empty additionalContext"
else
    bad "Stop hook with missing checkpoint emits non-empty additionalContext (status=$t3_status, check=$t3_check)"
fi
rm -rf "$t3_dir"

# --- Test 4: Stop hook with fresh checkpoint emits nothing ---
t4_dir=$(mktemp -d)
t4_transcript="$t4_dir/transcript.jsonl"
touch "$t4_transcript"
mkdir -p "$t4_dir/.breadcrumbs"
sleep 1
echo "## Active Task" > "$t4_dir/.breadcrumbs/checkpoint.md"
touch "$t4_dir/.breadcrumbs/checkpoint.md"  # newer than transcript

t4_out=$(echo "{\"cwd\": \"$t4_dir\", \"transcript_path\": \"$t4_transcript\"}" | "$HOOKS/on_stop.sh")
t4_status=$?

if [ $t4_status -eq 0 ] && [ -z "$t4_out" ]; then
    ok "Stop hook with fresh checkpoint emits nothing"
else
    bad "Stop hook with fresh checkpoint emits nothing (status=$t4_status, output='$t4_out')"
fi
rm -rf "$t4_dir"

echo ""
echo "----------------------------------------"
echo "Results: $PASS passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
