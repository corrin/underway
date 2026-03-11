# CI/CD & Branch Protection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up CI enhancements, manual-trigger CD to UAT (PythonAnywhere) and Prod (Oracle Cloud), and branch protection on main.

**Architecture:** Enhance existing GitHub Actions CI with caching and concurrency. Add two separate `workflow_dispatch` deploy workflows that SSH into servers. Configure branch protection via `gh api`. No server provisioning in this plan — just the GitHub-side automation.

**Tech Stack:** GitHub Actions, `appleboy/ssh-action`, `gh` CLI

---

### Task 1: Enhance CI Workflow — Caching & Concurrency

**Files:**
- Modify: `.github/workflows/ci.yml`

**Step 1: Add concurrency control and caching to ci.yml**

Replace the entire `.github/workflows/ci.yml` with:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      mariadb:
        image: mariadb:11
        env:
          MARIADB_ROOT_PASSWORD: root
          MARIADB_DATABASE: underway_test
          MARIADB_USER: underway
          MARIADB_PASSWORD: underway-ci-pass
        ports:
          - 3306:3306
        options: >-
          --health-cmd="healthcheck.sh --connect --innodb_initialized"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=5
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install Poetry
        run: pipx install poetry
      - name: Cache Poetry virtualenv
        uses: actions/cache@v4
        with:
          path: backend/.venv
          key: poetry-${{ runner.os }}-${{ hashFiles('backend/poetry.lock') }}
          restore-keys: poetry-${{ runner.os }}-
      - name: Install dependencies
        run: poetry install
      - name: mypy
        run: poetry run mypy underway --strict
      - name: ruff check
        run: poetry run ruff check underway
      - name: ruff format
        run: poetry run ruff format --check underway
      - name: pytest
        run: poetry run pytest -v
        env:
          TEST_DATABASE_URL: mysql+aiomysql://underway:underway-ci-pass@127.0.0.1:3306/underway_test
          JWT_SECRET_KEY: test-secret

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install dependencies
        run: npm ci
      - name: Lint
        run: npm run lint
      - name: Type check
        run: npx vue-tsc --build
      - name: Build
        run: npm run build
```

**Step 2: Verify the workflow is valid YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: No output (valid YAML)

**Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add dependency caching and concurrency control"
```

---

### Task 2: Deploy UAT Workflow (PythonAnywhere)

**Files:**
- Create: `.github/workflows/deploy-uat.yml`

**Step 1: Create the UAT deploy workflow**

```yaml
name: Deploy UAT (PythonAnywhere)

on:
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: uat
    steps:
      - name: Deploy to PythonAnywhere
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.PA_SSH_HOST }}
          username: ${{ secrets.PA_SSH_USER }}
          key: ${{ secrets.PA_SSH_KEY }}
          script: |
            set -euo pipefail
            cd ~/underway
            git fetch origin main
            git checkout main
            git pull origin main

            cd backend
            poetry install --no-interaction --no-ansi
            poetry run alembic upgrade head

            cd ../frontend
            npm ci
            npm run build

      - name: Reload web app
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.PA_SSH_HOST }}
          username: ${{ secrets.PA_SSH_USER }}
          key: ${{ secrets.PA_SSH_KEY }}
          script: |
            # PythonAnywhere API to reload the web app
            curl -s -X POST \
              "https://www.pythonanywhere.com/api/v0/user/${{ secrets.PA_SSH_USER }}/webapps/${{ secrets.PA_DOMAIN }}/reload/" \
              -H "Authorization: Token ${{ secrets.PA_API_TOKEN }}"

      - name: Health check
        run: |
          sleep 10
          STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://${{ secrets.PA_DOMAIN }}/")
          if [ "$STATUS" -ne 200 ]; then
            echo "Health check failed with status $STATUS"
            exit 1
          fi
          echo "Health check passed (HTTP $STATUS)"
```

**Step 2: Verify valid YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-uat.yml'))"`
Expected: No output

**Step 3: Commit**

```bash
git add .github/workflows/deploy-uat.yml
git commit -m "ci: add manual deploy workflow for UAT (PythonAnywhere)"
```

---

### Task 3: Deploy Prod Workflow (Oracle Cloud)

**Files:**
- Create: `.github/workflows/deploy-prod.yml`

**Step 1: Create the prod deploy workflow**

```yaml
name: Deploy Prod (Oracle Cloud)

on:
  workflow_dispatch:
    inputs:
      ref:
        description: "Git ref to deploy (branch, tag, or SHA)"
        required: false
        default: "main"

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Deploy to Oracle Cloud
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.OC_SSH_HOST }}
          username: ${{ secrets.OC_SSH_USER }}
          key: ${{ secrets.OC_SSH_KEY }}
          script: |
            set -euo pipefail
            cd /opt/underway
            git fetch origin
            git checkout ${{ github.event.inputs.ref }}
            git pull origin ${{ github.event.inputs.ref }}

            cd backend
            poetry install --no-interaction --no-ansi
            poetry run alembic upgrade head

            cd ../frontend
            npm ci
            npm run build

            sudo systemctl restart underway
            sudo systemctl reload nginx

      - name: Health check
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.OC_SSH_HOST }}
          username: ${{ secrets.OC_SSH_USER }}
          key: ${{ secrets.OC_SSH_KEY }}
          script: |
            sleep 5
            STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs)
            if [ "$STATUS" -ne 200 ]; then
              echo "Health check failed with status $STATUS"
              exit 1
            fi
            echo "Health check passed (HTTP $STATUS)"
```

**Step 2: Verify valid YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-prod.yml'))"`
Expected: No output

**Step 3: Commit**

```bash
git add .github/workflows/deploy-prod.yml
git commit -m "ci: add manual deploy workflow for Prod (Oracle Cloud)"
```

---

### Task 4: Configure Branch Protection via gh CLI

This task uses `gh api` to configure branch protection rules on `main`. This runs once interactively, not in CI.

**Step 1: Create GitHub environments**

```bash
# Create UAT environment
gh api repos/corrin/underway/environments/uat -X PUT

# Create production environment with required reviewers
gh api repos/corrin/underway/environments/production -X PUT \
  --input - <<'EOF'
{
  "reviewers": [],
  "deployment_branch_policy": {
    "protected_branches": true,
    "custom_branch_policies": false
  }
}
EOF
```

Note: `reviewers` is empty for now (solo dev). Add reviewer IDs later if needed.

**Step 2: Enable auto-delete head branches**

```bash
gh repo edit corrin/underway --delete-branch-on-merge
```

**Step 3: Create branch protection ruleset**

Using the newer rulesets API (more flexible than legacy branch protection):

```bash
gh api repos/corrin/underway/rulesets -X POST \
  --input - <<'EOF'
{
  "name": "Protect main",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [
    {
      "actor_type": "RepositoryRole",
      "actor_id": 5,
      "bypass_mode": "always"
    }
  ],
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [
          { "context": "backend" },
          { "context": "frontend" }
        ]
      }
    },
    {
      "type": "commit_message_pattern",
      "parameters": {
        "name": "Signed commits",
        "negate": false,
        "operator": "regex",
        "pattern": ".*"
      }
    },
    {
      "type": "non_fast_forward"
    }
  ]
}
EOF
```

Note on signed commits: GitHub rulesets support `"required_signatures"` rule type on GitHub Enterprise. For GitHub Free/Pro, commit signing is enforced via the branch protection (legacy) API instead:

```bash
# Fallback: enable signed commits via legacy API if rulesets don't support it
gh api repos/corrin/underway/branches/main/protection/required_signatures \
  -X POST \
  -H "Accept: application/vnd.github.zzzax-preview+json"
```

**Step 4: Verify protection is applied**

```bash
gh api repos/corrin/underway/rulesets --jq '.[].name'
```

Expected: `Protect main`

**Step 5: Commit the design doc**

```bash
git add docs/plans/2026-03-08-ci-cd-branch-protection-design.md \
       docs/plans/2026-03-08-ci-cd-branch-protection.md \
       docs/plans/03-phase2-tasks.md
git commit -m "docs: add CI/CD design and implementation plan, add test auth bypass to phase 2"
```

---

### Task 5: Verify End-to-End

**Step 1: Push branch and open PR**

```bash
git push -u origin feature/ci-cd-branch-protection
gh pr create --title "ci: add CD workflows and branch protection" --body "$(cat <<'EOF'
## Summary
- Enhanced CI with dependency caching and concurrency control
- Added manual-trigger deploy workflow for UAT (PythonAnywhere)
- Added manual-trigger deploy workflow for Prod (Oracle Cloud)
- Configured branch protection on main (PR required, status checks, signed commits, no force push)
- Added test auth bypass plan to Phase 2

## Test plan
- [ ] CI runs on this PR (backend + frontend jobs)
- [ ] Verify branch protection prevents direct push to main
- [ ] After merge, verify deploy-uat and deploy-prod appear in Actions tab
- [ ] (Later) Configure secrets and test actual deployments

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Step 2: Verify CI runs on the PR**

```bash
gh pr checks
```

Expected: `backend` and `frontend` jobs running or passed

---

## Secrets to Configure (Manual)

After the PR merges, configure these in GitHub Settings > Secrets and variables > Actions:

| Secret | Value |
|--------|-------|
| `PA_SSH_HOST` | PythonAnywhere SSH host |
| `PA_SSH_USER` | PythonAnywhere username |
| `PA_SSH_KEY` | SSH private key for PythonAnywhere |
| `PA_API_TOKEN` | PythonAnywhere API token (Account > API Token) |
| `PA_DOMAIN` | PythonAnywhere domain (e.g., `username.pythonanywhere.com`) |
| `OC_SSH_HOST` | Oracle Cloud VM public IP |
| `OC_SSH_USER` | SSH user on Oracle Cloud |
| `OC_SSH_KEY` | SSH private key for Oracle Cloud |
