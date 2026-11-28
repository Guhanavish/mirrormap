#!/bin/sh
# Download and review before running. Requires curl and a SHA256 utility, not Python.
set -eu
case "$(uname -s):$(uname -m)" in
  Linux:x86_64) name=mirrormap-linux-x64 ;;
  Darwin:x86_64) name=mirrormap-macos-x64 ;;
  Darwin:arm64) name=mirrormap-macos-arm64 ;;
  *) echo "No standalone build for this platform; use Python installation." >&2; exit 2 ;;
esac
if [ "$#" -eq 0 ]; then
  echo "Usage: sh install.sh setup --agent codex --project . [--apply]" >&2
  exit 2
fi
base=https://github.com/Guhanavish/mirrormap/releases/download/installer-preview-1
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT HUP INT TERM
curl -fLsS --max-time 180 "$base/SHA256SUMS.txt" -o "$dir/SHA256SUMS.txt"
curl -fLsS --max-time 180 "$base/$name" -o "$dir/$name"
expected=$(awk -v name="$name" '$2 == name && length($1)==64 && $1 ~ /^[0-9a-fA-F]+$/ {print tolower($1)}' "$dir/SHA256SUMS.txt")
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$dir/$name" | awk '{print $1}')
else
  actual=$(shasum -a 256 "$dir/$name" | awk '{print $1}')
fi
[ "$expected" = "$actual" ] || { echo "Checksum verification failed" >&2; exit 2; }
chmod 700 "$dir/$name"
"$dir/$name" "$@"
