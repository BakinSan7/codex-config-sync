#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${PYTHON_BIN:-python3}"
command="${1:-doctor}"
if [[ $# -gt 0 ]]; then
  shift
fi

command -v "$python_bin" >/dev/null || {
  echo "Python 3.11 or newer is required" >&2
  exit 1
}

exec "$python_bin" "$repo_root/scripts/codex_config_sync.py" \
  "$command" --repo-root "$repo_root" --platform macos "$@"
