#!/usr/bin/env bash
# PreToolUse(Bash) hook — block `git commit` when staged changes contain high-signal secrets.
#
# Conservative by design: it only matches well-known provider token FORMATS (AWS/GCP/GitHub/
# Slack/Stripe keys, private-key blocks, JWTs), which almost never false-positive. It deliberately
# does NOT try to catch every `password = "..."` — the pr-review agent is the thorough check, and
# a hook that blocks legitimate commits is worse than one that occasionally defers to review.
# See steering/01-security.md (rule #1).
set -uo pipefail

input="$(cat)"
cmd="$(printf '%s' "$input" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || true)"

# Only act on git commit; everything else passes straight through.
case "$cmd" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

added="$(git diff --cached 2>/dev/null | grep -E '^\+' || true)"
[ -z "$added" ] && exit 0

hits="$(printf '%s\n' "$added" | grep -inE \
  -e 'BEGIN [A-Z ]*PRIVATE KEY' \
  -e '(AKIA|ASIA)[0-9A-Z]{16}' \
  -e 'AIza[0-9A-Za-z_-]{35}' \
  -e 'ghp_[0-9A-Za-z]{36}' \
  -e 'github_pat_[0-9A-Za-z_]{22,}' \
  -e 'xox[baprs]-[0-9A-Za-z-]{10,}' \
  -e '(sk|rk)_(live|test)_[0-9A-Za-z]{16,}' \
  -e 'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.' \
  || true)"

if [ -n "$hits" ]; then
  echo "BLOCKED: staged changes look like they contain a hardcoded secret (steering/01-security.md rule #1)." >&2
  printf '%s\n' "$hits" | sed 's/^/  /' >&2
  echo "Move it to Secret Manager / .env (KEY only in .env.example), unstage the file, and retry." >&2
  exit 2
fi
exit 0
