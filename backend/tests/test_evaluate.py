"""scripts/evaluate.py runs end to end and the planted cases + held-out F4 check still pass."""

import importlib.util

from backend.app.settings import REPO_ROOT


def _load_evaluate():
    spec = importlib.util.spec_from_file_location("evaluate", REPO_ROOT / "scripts" / "evaluate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evaluate_writes_report(tmp_path):
    out = tmp_path / "EVALUATION.md"
    assert _load_evaluate().main(["--out", str(out)]) == 0  # 0 = every planted case PASS
    text = out.read_text(encoding="utf-8")
    assert "planted cases: 6/6 PASS" in text
    assert "| F4 | 2020-07-15 14:30 - 2020-07-15 19:00 | held-out | YES |" in text
    assert "No AMD numbers are claimed" in text or "saved real AI report" in text
