"""Exercise deployment against a disposable Git remote and stub server commands."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "deploy-prod.sh"
BACKEND = SCRIPT.parents[1] / "backend"


class DeployTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "server"
        self.repo.mkdir()
        self.log = self.root / "commands.log"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "deploy-test@example.com")
        self.git("config", "user.name", "Deployment test")
        for name in ("backend", "frontend"):
            (self.repo / name).mkdir()
            (self.repo / name / ".gitkeep").touch()
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        self.sha = self.git("rev-parse", "HEAD").strip()
        remote = self.root / "remote.git"
        subprocess.run(["git", "clone", "--bare", str(self.repo), str(remote)], check=True, capture_output=True)
        self.git("remote", "add", "origin", str(remote))
        self.env = dict(
            os.environ,
            PATH=f"{self.bin}:{os.environ['PATH']}",
            HOME=str(self.root),
            UNDERWAY_DIR=str(self.repo),
            COMMAND_LOG=str(self.log),
            TEST_PYTHON=sys.executable,
            PYTHONPATH=str(BACKEND),
            GOOGLE_CLIENT_ID="public-test-client-id",
            GOOGLE_CLIENT_SECRET="test-only",
            TESTING="false",
            DATABASE_URL="mysql+aiomysql://unused",
            JWT_SECRET_KEY="test-only",
        )
        self.stub("id", "echo underway")
        self.stub(
            "poetry",
            """
if [ "$1" = install ]; then exit 0; fi
shift
if [ "$1" = python ]; then shift; exec "$TEST_PYTHON" "$@"; fi
if [ "$1" = alembic ]; then exit "${MIGRATION_EXIT:-0}"; fi
exit 99
""",
        )
        self.stub(
            "npm",
            """
if [ "$1" = run ]; then
  test "$VITE_GOOGLE_CLIENT_ID" = public-test-client-id || exit 97
  exit "${BUILD_EXIT:-0}"
fi
""",
        )
        self.stub("sudo", 'test "$*" = "-n systemctl restart underway"')
        self.stub("curl", 'printf \'%s\' "${HEALTH_BODY:-{\\"status\\":\\"ok\\"}}"')
        self.stub("sleep", ":")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def stub(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text('#!/bin/bash\nprintf "%s\\n" "' + name + ' $*" >> "$COMMAND_LOG"\n' + body + "\n")
        path.chmod(0o755)

    def deploy(self, sha: str | None = None, **environment: str) -> tuple[subprocess.CompletedProcess[str], str]:
        result = subprocess.run(
            ["bash", str(SCRIPT), sha or self.sha],
            cwd=self.root,
            env=dict(self.env, **environment),
            text=True,
            capture_output=True,
            timeout=15,
        )
        commands = self.log.read_text() if self.log.exists() else ""
        return result, commands

    def test_deploys_exact_commit_and_restarts_after_build_and_migrations(self) -> None:
        result, commands = self.deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), self.sha)
        self.assertEqual(self.git("branch", "--show-current").strip(), "")
        self.assertLess(commands.index("npm run build"), commands.index("poetry run alembic"))
        self.assertLess(commands.index("poetry run alembic"), commands.index("sudo -n systemctl"))
        self.assertIn("API healthy at commit " + self.sha, result.stdout)

    def test_rejects_branch_names_and_shell_input(self) -> None:
        for ref in ("main", "--help", "a;touch injected"):
            with self.subTest(ref=ref):
                result, commands = self.deploy(ref)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("poetry", commands)
        self.assertFalse((self.root / "injected").exists())

    def test_refuses_dirty_server(self) -> None:
        (self.repo / "backend" / ".gitkeep").write_text("manual change")
        result, commands = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("poetry", commands)
        self.assertEqual((self.repo / "backend" / ".gitkeep").read_text(), "manual change")

    def test_build_failure_prevents_migration_and_restart(self) -> None:
        result, commands = self.deploy(BUILD_EXIT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("poetry run alembic", commands)
        self.assertNotIn("sudo", commands)

    def test_migration_failure_prevents_restart(self) -> None:
        result, commands = self.deploy(MIGRATION_EXIT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("sudo", commands)

    def test_rejects_testing_configuration(self) -> None:
        result, commands = self.deploy(TESTING="true")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TESTING enabled", result.stderr)
        self.assertNotIn("npm", commands)
        self.assertNotIn("sudo", commands)

    def test_requires_google_client_id_for_login(self) -> None:
        result, commands = self.deploy(GOOGLE_CLIENT_ID="")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("npm", commands)

    def test_invalid_health_response_fails_deployment(self) -> None:
        result, commands = self.deploy(HEALTH_BODY='{"status":"broken"}')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("did not become healthy", result.stderr)
        self.assertEqual(commands.count("curl "), 30)

    def test_successful_deployment_is_repeatable(self) -> None:
        self.assertEqual(self.deploy()[0].returncode, 0)
        result, _ = self.deploy()
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
