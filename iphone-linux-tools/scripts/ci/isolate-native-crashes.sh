#!/usr/bin/env bash
# Expected assertion crashes must not start an external handler on a hosted CI VM.
set -euo pipefail

if (($# != 0)) || [[ "${GITHUB_ACTIONS:-}" != true || "${RUNNER_OS:-}" != Linux ||
                    "${RUNNER_ENVIRONMENT:-}" != github-hosted ]]; then
  echo 'CI_NATIVE_CRASH_ISOLATION_REFUSED: hosted GitHub Linux job required' >&2
  exit 2
fi

core_handler_before="$(sysctl -n kernel.core_pattern)"
if [[ "$core_handler_before" == \|* ]]; then
  sudo -n sysctl -q -w kernel.core_pattern=core
  core_handler_after="$(sysctl -n kernel.core_pattern)"
  [[ "$core_handler_after" == core ]] || {
    echo 'CI_NATIVE_CRASH_ISOLATION_FAILED: handler write not confirmed' >&2
    exit 1
  }
else
  core_handler_after="$(sysctl -n kernel.core_pattern)"
  [[ "$core_handler_after" == "$core_handler_before" ]] || {
    echo 'CI_NATIVE_CRASH_ISOLATION_FAILED: handler changed unexpectedly' >&2
    exit 1
  }
fi

printf 'CI_NATIVE_CRASH_ISOLATION_OK handler_before=%s handler_after=%s\n' \
  "$core_handler_before" "$core_handler_after"
