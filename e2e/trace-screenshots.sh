#!/usr/bin/env bash
# Extract screenshots from a trace for quick inspection.
#
# Usage:
#   ./trace-screenshots.sh test_name           # extract last 5 screenshots
#   ./trace-screenshots.sh test_name 10        # extract last N screenshots
#   ./trace-screenshots.sh test_name all       # extract all screenshots

set -euo pipefail

RESULTS_DIR="/tmp/e2e-results"

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <test_name> [count|all]"
    exit 1
fi

pattern="$1"
count="${2:-5}"

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
out_dir="/tmp/e2e-screenshots/$(basename "$match")"
rm -rf "$out_dir"
mkdir -p "$out_dir"

python3 -c "
import zipfile, sys
from pathlib import Path

count = '$count'
out = Path('$out_dir')

with zipfile.ZipFile('$trace_file') as z:
    imgs = sorted([n for n in z.namelist() if n.endswith(('.jpeg', '.png'))])
    if not imgs:
        print('No screenshots in trace.')
        sys.exit(1)

    if count != 'all':
        imgs = imgs[-int(count):]

    for i, name in enumerate(imgs):
        data = z.read(name)
        ext = Path(name).suffix
        dest = out / f'{i:03d}{ext}'
        dest.write_bytes(data)
        print(str(dest))

    print(f'\n{len(imgs)} screenshots extracted to {out}')
"
