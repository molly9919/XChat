#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

INSTALL_DEPS=0
if [[ "${1:-}" == "--install-deps" ]]; then
  INSTALL_DEPS=1
fi

missing_packages_raw() {
  local output
  output="$(dpkg-checkbuilddeps 2>&1 || true)"
  if [[ "$output" == *"Unmet build dependencies:"* ]]; then
    echo "$output" | sed -n 's/.*Unmet build dependencies: //p'
  fi
}

normalize_packages() {
  echo "$1" \
    | sed -E 's/\([^)]*\)//g; s/\[[^]]*\]//g; s/\|/ /g; s/,/ /g' \
    | xargs -n1 \
    | sed -E 's/:any$//' \
    | awk 'NF > 0' \
    | sort -u \
    | xargs
}

install_missing_deps() {
  local packages="$1"
  if [[ -z "$packages" ]]; then
    return 0
  fi

  # shellcheck disable=SC2206
  local pkgs=( $packages )

  echo "Installing missing build dependencies: ${pkgs[*]}"
  if [[ "$EUID" -eq 0 ]]; then
    apt-get update
    apt-get install -y --no-install-recommends "${pkgs[@]}"
    return
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends "${pkgs[@]}"
    return
  fi

  echo "Error: missing sudo privileges to install dependencies automatically." >&2
  echo "Please run this command as root or install the packages manually:" >&2
  echo "  apt-get install -y --no-install-recommends ${pkgs[*]}" >&2
  exit 1
}

raw_missing="$(missing_packages_raw)"
missing="$(normalize_packages "$raw_missing")"
if [[ -n "$missing" ]]; then
  if [[ "$INSTALL_DEPS" -eq 1 ]]; then
    install_missing_deps "$missing"
  else
    echo "Missing Debian build dependencies: $missing" >&2
    echo "Install them manually or rerun with --install-deps:" >&2
    echo "  ./scripts/build_deb.sh --install-deps" >&2
    exit 1
  fi
fi

echo "Building Debian package for xchat-tor..."
dpkg-buildpackage -us -uc -b

echo "Done. Package artifacts are in: $(dirname "$ROOT_DIR")"
