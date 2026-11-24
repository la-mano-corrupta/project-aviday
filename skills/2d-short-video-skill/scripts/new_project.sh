#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: bash scripts/new_project.sh <canvas-2d|remotion-2d> <project-slug> [dest-root]"
  exit 1
fi

ENGINE="$1"
SLUG="$2"
DEST_ROOT="${3:-$HOME/2d-short-videos}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$SKILL_DIR/templates/$ENGINE"

if [ ! -d "$TEMPLATE" ]; then
  echo "Unknown engine '$ENGINE'. Choose: canvas-2d or remotion-2d"
  exit 1
fi

DEST="$DEST_ROOT/$SLUG"
if [ -e "$DEST" ]; then
  echo "Destination already exists: $DEST"
  exit 1
fi

mkdir -p "$DEST_ROOT"
cp -R "$TEMPLATE" "$DEST"

if [ "$ENGINE" = "canvas-2d" ]; then
  mkdir -p "$DEST/tools" "$DEST/renders" "$DEST/review" "$DEST/data"
  cp "$SKILL_DIR/scripts/render_canvas.mjs" "$DEST/tools/render_canvas.mjs"
  cp "$SKILL_DIR/scripts/mix.py" "$DEST/tools/mix.py"
fi

echo "Created $ENGINE project at: $DEST"
