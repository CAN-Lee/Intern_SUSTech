#!/usr/bin/env bash
set -euo pipefail
mesh_rsi_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
printf -v mesh_rsi_command '%q ' "$mesh_rsi_root/.venv-rsi/bin/python" "$mesh_rsi_root/run_rsi.py" "$@"
exec sg docker -c "$mesh_rsi_command"
