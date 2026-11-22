#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[31mxx\033[0m %s\n' "$*" >&2; exit 1; }
ask()  { [ -t 0 ] || return 1; read -r -p "$1 [Y/n] " a; [[ -z "$a" || "$a" =~ ^[Yy] ]]; }

command -v python3 >/dev/null || die "python3 not found. Install Python 3.12+ first."

if [ ! -x .venv/bin/python ]; then
  say "Creating .venv"
  python3 -m venv .venv
fi
req_hash=$(shasum requirements.txt | cut -d' ' -f1)
if [ "$(cat .venv/.requirements.sha 2>/dev/null)" != "$req_hash" ]; then
  say "Installing requirements"
  .venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
  echo "$req_hash" > .venv/.requirements.sha
fi

if ! command -v ant >/dev/null; then
  if command -v brew >/dev/null && ask "The ant CLI is missing. Install it with Homebrew now?"; then
    brew install anthropics/tap/ant
  else
    die "Install the ant CLI (brew install anthropics/tap/ant), then rerun."
  fi
fi

if [ -f .env ] && grep -q '^ANTHROPIC_API_KEY=' .env; then
  if ask ".env still holds ANTHROPIC_API_KEY, which would override your ant login. Remove that line?"; then
    sed -i.bak '/^ANTHROPIC_API_KEY=/d' .env && rm -f .env.bak
  else
    die "Remove ANTHROPIC_API_KEY from .env, then rerun."
  fi
fi
if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ -n "${ANTHROPIC_API_KEY+x}" ] || [ -n "${ANTHROPIC_AUTH_TOKEN+x}" ]; then
  say "Ignoring ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN from your shell so the ant login is used"
  unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN
fi

check_auth() { ant models list --max-items 1 >/dev/null 2>&1; }
if ! check_auth; then
  if ask "No working Anthropic sign-in (missing or expired). Run 'ant auth login' now?"; then
    ant auth login
    check_auth || die "Still can't reach the API. Check 'ant auth status'."
  else
    die "Run 'ant auth login', then rerun."
  fi
fi
say "Anthropic sign-in OK"

exec .venv/bin/python -m newsletter.run "$@"
