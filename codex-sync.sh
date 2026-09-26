#!/usr/bin/env bash
# Entry point on macOS: ./codex-sync.sh <command> [options]
# Commands: catalog, bootstrap, preview, apply, verify, detail, rollback, prepare, scan, publish.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${PYTHON_BIN:-python3}"
command="${1:-preview}"
if [[ $# -gt 0 ]]; then
  shift
fi

command -v "$python_bin" >/dev/null || {
  echo "Python 3.11 or newer is required" >&2
  exit 1
}

case "$command" in
  publish)
    if [[ $# -lt 2 ]]; then
      echo 'Usage: ./codex-sync.sh publish "commit message" file1 [file2 ...]' >&2
      exit 2
    fi
    message="$1"
    shift
    exec "$python_bin" "$repo_root/scripts/publish_profile.py" --repo-root "$repo_root" --message "$message" --paths "$@"
    ;;
  scan)
    exec "$python_bin" "$repo_root/scripts/portable_config.py" scan --repo-root "$repo_root" "$@"
    ;;
  *)
    exec "$python_bin" "$repo_root/scripts/sync_profile.py" "$command" --repo-root "$repo_root" --platform macos "$@"
    ;;
esac
