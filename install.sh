#!/usr/bin/env bash
set -euo pipefail

if (( EUID == 0 )); then
  echo 'Run this installer as your desktop user, without sudo.' >&2
  exit 1
fi
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
plugin_dir="$HOME/.config/omarchy/plugins/soheib.screenpad"
# Discovery/reloading can take longer than the wrapper's two-second default.
export OMARCHY_SHELL_IPC_TIMEOUT="${OMARCHY_SHELL_IPC_TIMEOUT:-10s}"
command -v omarchy >/dev/null
command -v brightnessctl >/dev/null
command -v python3 >/dev/null
stage_dir=$(mktemp -d)
trap 'rm -rf -- "$stage_dir"' EXIT
for file in manifest.json Panel.qml screenpadctl README.md LICENSE; do
  install -m644 -- "$source_dir/$file" "$stage_dir/$file"
done
omarchy plugin validate "$stage_dir"
if [[ -f "$HOME/.config/omarchy/shell.json" ]]; then
  mkdir -p "$HOME/.local/state/omarchy-screenpad/backups"
  cp -p -- "$HOME/.config/omarchy/shell.json" \
    "$HOME/.local/state/omarchy-screenpad/backups/shell.$(date +%Y%m%d-%H%M%S-%N).json"
fi
mkdir -p -- "$plugin_dir"
for file in manifest.json Panel.qml screenpadctl README.md LICENSE; do
  install -m644 -- "$stage_dir/$file" "$plugin_dir/$file"
done
chmod 755 "$plugin_dir/screenpadctl"
omarchy plugin validate "$plugin_dir"
# File copies can briefly coincide with the shell's plugin hot reload.
for attempt in 1 2 3 4 5; do
  if omarchy-shell shell rescanPlugins; then break; fi
  if [[ $attempt == 5 ]]; then exit 1; fi
  sleep 0.5
done
for attempt in 1 2 3; do
  if omarchy plugin enable soheib.screenpad --before omarchy.monitor; then exit 0; fi
  sleep 0.5
done
exit 1
