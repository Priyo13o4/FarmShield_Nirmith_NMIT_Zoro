"""
Tests for ML runner.

services/ml/runner.py:
  - predict() with mock model → returns dict with action key
  - ML_ENABLED=true + missing model → FileNotFoundError
  - ML_ENABLED=false → runner does nothing
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_ml_runner_disabled_does_nothing():
    """MLRunner.load() with ML_ENABLED=false is a no-op."""
    with patch("app.services.ml.runner.settings") as mock_settings:
        mock_settings.ml_enabled = False

        from app.services.ml.runner import MLRunner

        runner = MLRunner()
        runner.load()  # Should not raise

        # predict should return error dict since model is not loaded
        result = runner.predict({"soil_pct": 42.5})
        assert result["action"] == "UNKNOWN"
        assert result["confidence"] == 0.0


def test_ml_runner_missing_model_raises():
    """MLRunner.load() with ML_ENABLED=true and missing file raises FileNotFoundError."""
    with patch("app.services.ml.runner.settings") as mock_settings:
        mock_settings.ml_enabled = True
        mock_settings.ml_model_path = "/nonexistent/path/model.pkl"
        mock_settings.ml_model_type = "sklearn"

        from app.services.ml.runner import MLRunner

        runner = MLRunner()
        with pytest.raises(FileNotFoundError, match="ML model file not found"):
            runner.load()


def test_ml_runner_invalid_model_type_raises():
    """MLRunner.load() with unsupported ML_MODEL_TYPE raises ValueError."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".xyz") as tmp:
        with patch("app.services.ml.runner.settings") as mock_settings:
            mock_settings.ml_enabled = True
            mock_settings.ml_model_path = tmp.name
            mock_settings.ml_model_type = "unknown_type"

            from app.services.ml.runner import MLRunner

            runner = MLRunner()
            with pytest.raises(ValueError, match="Unsupported ML_MODEL_TYPE"):
                runner.load()


def test_ml_runner_predict_never_raises():
    """predict() must never raise — returns error dict on failure."""
    from app.services.ml.runner import MLRunner

    runner = MLRunner()
    runner._model = MagicMock(side_effect=Exception("kaboom"))
    runner._model_type = "sklearn"

    result = runner.predict({"soil_pct": 42.5})
    assert result["action"] == "UNKNOWN"
    assert "error" in result
