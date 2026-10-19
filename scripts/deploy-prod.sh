#!/usr/bin/env bash
# Run over SSH as the underway service/deploy user.
set -euo pipefail

deploy_sha=${1:?Usage: deploy-prod.sh FULL_COMMIT_SHA}
if [[ ! "$deploy_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Deployment requires a full commit SHA.' >&2
  exit 1
fi
if [ "$(id -un)" != underway ]; then
  echo 'Run deployment as the underway service user.' >&2
  exit 1
fi

export PATH="$HOME/.local/bin:$PATH"
cd "${UNDERWAY_DIR:-/opt/underway}"

# Refuse to overwrite manual server edits. Never reset or clean the checkout.
git diff --quiet
git diff --cached --quiet
git fetch --no-tags origin "$deploy_sha"
git checkout --detach "$deploy_sha"
test "$(git rev-parse HEAD)" = "$deploy_sha"

cd backend
poetry install --no-interaction --no-ansi
# Read existing server configuration; never transfer application secrets via CI.
poetry run python - <<'PY'
from underway.config import get_settings

settings = get_settings()
settings.validate_required()
if settings.testing:
    raise SystemExit('Refusing to deploy with TESTING enabled.')
PY

google_client_id=$(poetry run python -c 'from underway.config import get_settings; print(get_settings().google_client_id)')
test -n "$google_client_id"

# Build before touching the database or restarting the API.
cd ../frontend
export VITE_GOOGLE_CLIENT_ID="$google_client_id"
npm ci --no-audit --no-fund
npm run build

cd ../backend
poetry run alembic upgrade head
sudo -n systemctl restart underway

for attempt in $(seq 1 30); do
  if curl --fail --silent --show-error --max-time 2 http://127.0.0.1:8000/api/health \
    | python3 -c 'import json, sys; assert json.load(sys.stdin) == {"status": "ok"}' 2>/dev/null; then
    echo "API healthy at commit $deploy_sha after $attempt attempt(s)"
    exit 0
  fi
  sleep 2
done
echo "API did not become healthy at commit $deploy_sha" >&2
exit 1
