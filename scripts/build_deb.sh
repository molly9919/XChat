#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Building Debian package for xchat-tor..."
dpkg-buildpackage -us -uc -b

echo "Done. Package artifacts are in: $(dirname "$ROOT_DIR")"
