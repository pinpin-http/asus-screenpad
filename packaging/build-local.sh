#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
version=$(python3 -c 'import json; print(json.load(open("manifest.json"))["version"])')
archive="omarchy-screenpad-$version.tar.gz"
tar --sort=name --mtime='2026-01-01' --owner=0 --group=0 --numeric-owner \
  --transform="s,^,omarchy-screenpad-$version/," \
  -czf "packaging/$archive" manifest.json Panel.qml screenpadctl install.sh README.md \
  LICENSE tests/test_controller.py packaging/omarchy-screenpad-install
cd packaging
checksum=$(sha256sum "$archive" | cut -d' ' -f1)
# Keep the public PKGBUILD and its release checksum untouched by local builds.
local_build=$(mktemp -d)
trap 'rm -rf -- "$local_build"' EXIT
cp PKGBUILD "$local_build/PKGBUILD"
cp "$archive" "$local_build/$archive"
sed -i "s|^source=.*|source=(\"$archive\")|; s/^sha256sums=.*/sha256sums=('$checksum')/" "$local_build/PKGBUILD"
cd "$local_build"
makepkg --force --clean
cp -- ./*.pkg.tar.* "$root/packaging/"
