#!/bin/bash
# Saves an API key from the clipboard into this project's own Keychain item and prints only its length. Keys never go
# in a file. The Keychain may ask to allow access, so click Allow.
#
#   bash owner/keys.sh                       says which of the two keys are saved
#   bash owner/keys.sh --clipboard openai    saves a key from the clipboard (anthropic or openai)
#
# A key typed into the Keychain prompt can be cut short, which is why a key comes from the clipboard.
set -euo pipefail

save() {
  security add-generic-password -U -a "$USER" -s "agent-console-$1" -w "$2"
  echo "Saved the $1 key as agent-console-$1 (${#2} characters)."
}

if [ "${1:-}" = "--clipboard" ]; then
  vendor="${2:-}"
  case "$vendor" in
    anthropic|openai) ;;
    *) echo "Usage: bash owner/keys.sh --clipboard anthropic|openai"; exit 1 ;;
  esac
  key="$(pbpaste)"
  if [ ${#key} -lt 20 ]; then
    echo "That doesn't look like a key. Copy it and run this again."
    exit 1
  fi
  save "$vendor" "$key"
  exit 0
fi

for vendor in anthropic openai; do
  if security find-generic-password -s "agent-console-$vendor" >/dev/null 2>&1; then
    echo "Saved as agent-console-$vendor."
  else
    echo "No $vendor key yet. Copy one and run: bash owner/keys.sh --clipboard $vendor"
  fi
done
