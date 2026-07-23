import ast
import contextlib
import io
from pathlib import Path
import unittest

from pqc_sat.cli import parse_args
from pqc_sat.ui.game import GamePanel
from tools.benchmark_dashboard import run_benchmark


ROOT = Path(__file__).resolve().parents[1]


class DashboardArchitectureTests(unittest.TestCase):
    def test_dashboard_is_the_only_thin_python_entrypoint(self):
        lines = (ROOT / "dashboard.py").read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(lines), 12)
        self.assertFalse((ROOT / "stand_demo.py").exists())
        self.assertFalse(list(ROOT.rglob("*.sh")))
        self.assertFalse(list(ROOT.rglob("*.bash")))

    def test_production_cli_has_no_simulation_or_legacy_flow(self):
        for removed in ("--simulated", "--stand-flow", "--stand", "--presentation", "--stand-fixture"):
            with self.subTest(flag=removed), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parse_args([removed])

        tree = ast.parse((ROOT / "pqc_sat" / "cli.py").read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertNotIn("pqc_sat.stand.fixture", imports)
        self.assertNotIn("pqc_sat.testing.fixture", imports)
        self.assertNotIn("pqc_sat.infrastructure.wisdom", imports)

    def test_production_panel_rejects_non_hardware_controller(self):
        controller = type("Controller", (), {"mode": "simulated"})()
        with self.assertRaisesRegex(ValueError, "hardware"):
            GamePanel(object(), controller)

    def test_headless_benchmark_uses_only_staged_game(self):
        result = run_benchmark(width=640, height=360, frames=2, warmup=1)
        self.assertEqual(result["schema_version"], "pqc-sat-game-render-benchmark-v1")
        self.assertEqual(result["flow"], "staged_game")
        self.assertEqual(result["resolution"], [640, 360])
        self.assertGreater(result["mean_frame_ms"], 0)


if __name__ == "__main__":
    unittest.main()
