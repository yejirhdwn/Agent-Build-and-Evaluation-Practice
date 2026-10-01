#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/mock_data/logs"
TARGET_DIR="$ROOT_DIR/workspace/input/logs"

mkdir -p "$TARGET_DIR"
cp -a "$SOURCE_DIR/." "$TARGET_DIR/"
printf 'Loaded mock logs into %s\n' "$TARGET_DIR"