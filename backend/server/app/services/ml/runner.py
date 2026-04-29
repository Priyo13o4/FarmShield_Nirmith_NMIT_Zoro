"""
FarmShield Backend — ML Inference Runner.

Strict interface per PRD §12.1:
  - load(): called once at startup. Raises FileNotFoundError if model missing and ML_ENABLED=true.
  - predict(features): called per ingested message. Never raises — returns error dict on failure.

Supports:
  - sklearn (.pkl via joblib)
  - tflite (.tflite via tflite_runtime)
"""

from pathlib import Path

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class MLRunner:
    """ML model loader and inference runner."""

    def __init__(self):
        self._model = None
        self._model_type: str | None = None

    def load(self) -> None:
        """
        Load the ML model from disk.

        Called once during app lifespan startup.
        If ML_ENABLED=false: does nothing.
        If ML_ENABLED=true and model file not found: raises FileNotFoundError.
        The app MUST NOT start if this raises.
        """
        if not settings.ml_enabled:
            return

        model_path = Path(settings.ml_model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"ML model file not found at '{model_path.resolve()}'. "
                f"Drop a .{settings.ml_model_type} file at the configured ML_MODEL_PATH "
                f"or set ML_ENABLED=false in .env to disable ML inference."
            )

        self._model_type = settings.ml_model_type.lower()

        if self._model_type == "sklearn":
            import joblib

            self._model = joblib.load(str(model_path))
            logger.info(
                "ml_model_loaded",
                model_type="sklearn",
                path=str(model_path),
            )

        elif self._model_type == "tflite":
            import tflite_runtime.interpreter as tflite

            self._model = tflite.Interpreter(model_path=str(model_path))
            self._model.allocate_tensors()
            logger.info(
                "ml_model_loaded",
                model_type="tflite",
                path=str(model_path),
            )

        else:
            raise ValueError(
                f"Unsupported ML_MODEL_TYPE '{settings.ml_model_type}'. "
                f"Must be 'sklearn' or 'tflite'."
            )

    def predict(self, features: dict) -> dict:
        """
        Run inference on the given feature dict.

        Input: dict of sensor field names to float values (None values excluded).
        Output: dict with at least {"action": str, "confidence": float}.

        Never raises — on inference error, logs the error and returns
        {"action": "UNKNOWN", "confidence": 0.0, "error": "<message>"}.
        """
        if self._model is None:
            return {"action": "UNKNOWN", "confidence": 0.0, "error": "Model not loaded"}

        try:
            if self._model_type == "sklearn":
                return self._predict_sklearn(features)
            elif self._model_type == "tflite":
                return self._predict_tflite(features)
            else:
                return {"action": "UNKNOWN", "confidence": 0.0, "error": f"Unknown model type: {self._model_type}"}
        except Exception as e:
            logger.error(
                "ml_inference_failed",
                error=str(e),
                features_keys=list(features.keys()),
                exc_info=True,
            )
            return {"action": "UNKNOWN", "confidence": 0.0, "error": str(e)}

    def _predict_sklearn(self, features: dict) -> dict:
        """Run sklearn model prediction."""
        import numpy as np

        # Build feature vector in the expected order
        feature_order = [
            "soil_pct", "tds_ppm", "temp_c", "humidity_pct",
            "rain_raw", "npk_n", "npk_p", "npk_k",
            "leaf_r", "leaf_g", "leaf_b",
        ]
        feature_vector = [features.get(k, 0.0) for k in feature_order]
        X = np.array([feature_vector])

        prediction = self._model.predict(X)
        action = str(prediction[0])

        # Try to get probability/confidence if available
        confidence = 0.0
        if hasattr(self._model, "predict_proba"):
            proba = self._model.predict_proba(X)
            confidence = float(np.max(proba))

        return {"action": action, "confidence": confidence}

    def _predict_tflite(self, features: dict) -> dict:
        """Run TFLite model prediction."""
        import numpy as np

        feature_order = [
            "soil_pct", "tds_ppm", "temp_c", "humidity_pct",
            "rain_raw", "npk_n", "npk_p", "npk_k",
            "leaf_r", "leaf_g", "leaf_b",
        ]
        feature_vector = [features.get(k, 0.0) for k in feature_order]

        input_details = self._model.get_input_details()
        output_details = self._model.get_output_details()

        input_data = np.array([feature_vector], dtype=np.float32)
        self._model.set_tensor(input_details[0]["index"], input_data)
        self._model.invoke()

        output_data = self._model.get_tensor(output_details[0]["index"])
        action_idx = int(np.argmax(output_data))
        confidence = float(np.max(output_data))

        return {"action": str(action_idx), "confidence": confidence}
