#!/usr/bin/env bash
# View a Playwright trace from /tmp/e2e-results.
#
# Usage:
#   ./view-trace.sh                     # list available traces
#   ./view-trace.sh test_name           # open trace in browser (partial match)
#   ./view-trace.sh test_name --png     # extract last screenshot to /tmp and print path

set -euo pipefail

RESULTS_DIR="/tmp/e2e-results"

if [[ ! -d "$RESULTS_DIR" ]]; then
    echo "No results directory at $RESULTS_DIR — run tests first."
    exit 1
fi

# No args — list available traces
if [[ $# -eq 0 ]]; then
    echo "Available traces:"
    for d in "$RESULTS_DIR"/*/; do
        name=$(basename "$d")
        trace="$d/trace.zip"
        if [[ -f "$trace" ]]; then
            size=$(du -h "$trace" | cut -f1)
            echo "  $name  ($size)"
        fi
    done
    echo ""
    echo "Usage: $0 <test_name> [--png]"
    exit 0
fi

# Find matching trace
pattern="$1"
shift
match=""
for d in "$RESULTS_DIR"/*/; do
    name=$(basename "$d")
    if [[ "$name" == *"$pattern"* ]]; then
        match="$d"
        break
    fi
done

if [[ -z "$match" ]]; then
    echo "No trace matching '$pattern' found."
    exit 1
fi

trace_file="$match/trace.zip"
if [[ ! -f "$trace_file" ]]; then
    echo "No trace.zip in $match"
    exit 1
fi

# --png mode: extract last screenshot
if [[ "${1:-}" == "--png" ]]; then
    python3 -c "
import zipfile, sys, shutil
from pathlib import Path

with zipfile.ZipFile('$trace_file') as z:
    jpgs = sorted([n for n in z.namelist() if n.endswith('.jpeg') or n.endswith('.png')])
    if not jpgs:
        print('No screenshots in trace.')
        sys.exit(1)

    out_dir = Path('/tmp/e2e-screenshots')
    out_dir.mkdir(exist_ok=True)

    # Extract last 5 screenshots
    for jpg in jpgs[-5:]:
        z.extract(jpg, out_dir)
        print(f'{out_dir}/{jpg}')
"
    exit 0
fi

# Default: open in Playwright trace viewer
echo "Opening trace: $(basename "$match")"
npx playwright show-trace "$trace_file"
