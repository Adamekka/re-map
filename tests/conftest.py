"""Shared test configuration.

RE2-EVAL-001 resolves rows the older RE2 proof layers leave Unknown. Tests of
those layers assert their own isolated outcomes, often against synthetic
catalogs the committed script models do not describe. Profiles therefore load
without script evaluation unless a test requests the ``script_evaluation``
fixture. Module-scoped profile fixtures load before function fixtures run, so
the default is applied once at collection rather than per test.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re2 import re2_profile  # noqa: E402
from games.re2.script_model import ScriptEvaluationSupport  # noqa: E402

_EVALUATION = re2_profile.script_evaluation
re2_profile.script_evaluation = lambda profile, path, rooms: (
    ScriptEvaluationSupport.Unaudited
)


@pytest.fixture
def script_evaluation(monkeypatch):
    """Load RE2 profiles with their configured script evaluation."""
    monkeypatch.setattr(re2_profile, "script_evaluation", _EVALUATION)
