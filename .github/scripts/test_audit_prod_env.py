"""Tests for ``.github/scripts/audit_prod_env.py``.

Self-contained — no pytest required, runs as ``python3 test_audit_prod_env.py``.
Used by the CI workflow ``audit-prod-env.yml`` as a sanity check before the
script is invoked against live Railway data.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import audit_prod_env as mod  # noqa: E402


class AuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.block = Path(self.tmp) / "block.txt"
        self.allow = Path(self.tmp) / "allow.txt"
        self.kv = Path(self.tmp) / "kv.env"
        self.block.write_text(
            textwrap.dedent(
                """
                # comment
                PYTHONASYNCIODEBUG
                DEBUG
                TRACE_*
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        self.allow.write_text(
            textwrap.dedent(
                """
                DATABASE_URL
                SUPABASE_*
                RAILWAY_*
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def _run(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                exit_code = mod.main(list(args))
            except SystemExit as exc:
                exit_code = int(exc.code or 0)
        return exit_code, out.getvalue(), err.getvalue()

    def test_blocklisted_var_fails(self) -> None:
        self.kv.write_text("DATABASE_URL=x\nPYTHONASYNCIODEBUG=1\n")
        rc, out, _ = self._run(
            "--from-file",
            str(self.kv),
            "--blocklist",
            str(self.block),
            "--allowlist",
            str(self.allow),
        )
        self.assertEqual(rc, 1)
        self.assertIn("PYTHONASYNCIODEBUG", out)

    def test_wildcard_blocklist_matches(self) -> None:
        self.kv.write_text("TRACE_FOO=1\nDATABASE_URL=x\n")
        rc, out, _ = self._run(
            "--from-file",
            str(self.kv),
            "--blocklist",
            str(self.block),
            "--allowlist",
            str(self.allow),
        )
        self.assertEqual(rc, 1)
        self.assertIn("TRACE_FOO", out)
        self.assertIn("TRACE_*", out)

    def test_clean_returns_zero(self) -> None:
        self.kv.write_text("DATABASE_URL=x\nSUPABASE_URL=y\nRAILWAY_PROJECT_ID=z\n")
        rc, _, _ = self._run(
            "--from-file",
            str(self.kv),
            "--blocklist",
            str(self.block),
            "--allowlist",
            str(self.allow),
        )
        self.assertEqual(rc, 0)

    def test_allowlist_drift_warns_only(self) -> None:
        self.kv.write_text("DATABASE_URL=x\nWEIRD_VAR=1\n")
        rc, out, _ = self._run(
            "--from-file",
            str(self.kv),
            "--blocklist",
            str(self.block),
            "--allowlist",
            str(self.allow),
        )
        self.assertEqual(rc, 0)
        self.assertIn("WEIRD_VAR", out)
        self.assertIn("not in the allowlist", out)

    def test_strict_allowlist_drift_fails(self) -> None:
        self.kv.write_text("DATABASE_URL=x\nWEIRD_VAR=1\n")
        rc, out, _ = self._run(
            "--from-file",
            str(self.kv),
            "--blocklist",
            str(self.block),
            "--allowlist",
            str(self.allow),
            "--strict-allowlist",
        )
        self.assertEqual(rc, 1)
        self.assertIn("WEIRD_VAR", out)

    def test_json_output(self) -> None:
        self.kv.write_text("DATABASE_URL=x\nDEBUG=1\nWEIRD=1\n")
        rc, out, _ = self._run(
            "--from-file",
            str(self.kv),
            "--blocklist",
            str(self.block),
            "--allowlist",
            str(self.allow),
            "--json",
        )
        self.assertEqual(rc, 1)
        # Last non-empty stdout block should be valid JSON.
        json_text = out.split("::warning::")[-1] if "::warning::" in out else out
        decoded = json.loads(json_text.split("audit summary:")[0].strip().splitlines()[-1])\
            if "audit summary:" in out else None
        # More robust: find the JSON object directly.
        decoded = json.loads(out[out.find("{") : out.rfind("}") + 1])
        self.assertEqual(decoded["total_keys"], 3)
        self.assertEqual(len(decoded["violations"]), 1)
        self.assertIn("WEIRD", decoded["allowlist_drift"])

    def test_comments_and_blanks_ignored(self) -> None:
        self.kv.write_text("# comment\n\nDATABASE_URL=ok\n")
        rc, _, _ = self._run(
            "--from-file",
            str(self.kv),
            "--blocklist",
            str(self.block),
            "--allowlist",
            str(self.allow),
        )
        self.assertEqual(rc, 0)

    def test_real_repo_lists_load(self) -> None:
        # Smoke check: real lists in repo parse cleanly.
        rc, _, _ = self._run(
            "--from-file",
            "-",
            "--blocklist",
            str(mod.BLOCKLIST_DEFAULT),
            "--allowlist",
            str(mod.ALLOWLIST_DEFAULT),
        )
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
