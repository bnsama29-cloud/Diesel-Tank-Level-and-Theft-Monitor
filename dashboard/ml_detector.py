"""
ml_detector.py — ML-based Theft Anomaly Detector for Diesel Tank Monitor
=========================================================================

Replaces the rigid "5 % drop in 1 minute" rule with an ML ensemble that
combines an **Isolation Forest** (unsupervised anomaly detection) with a
**Gradient Boosting Classifier** (supervised theft/normal classification).

The detector analyses a sliding window of tank-level readings together with
contextual features (generator state, rate-of-change acceleration, drop
sharpness, etc.) and returns a confidence-scored ``AnomalyResult``.

Workflow
--------
1.  ``FeatureExtractor.extract()`` converts raw ``(datetime, level_pct)``
    history into an 8-dimensional feature vector.
2.  ``TheftDetector.predict()`` feeds the vector through both models and
    produces an ensemble confidence score.
3.  If no trained model is available on disk the detector transparently
    falls back to an enhanced rule-based heuristic so that the system is
    never left unprotected.

Typical usage::

    from ml_detector import TheftDetector, AnomalyResult

    detector = TheftDetector()
    result: AnomalyResult = detector.predict(level_history, generator_on=False)
    if result.is_theft:
        print(result.explanation)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AnomalyResult:
    """Container for a single theft-detection prediction.

    Attributes
    ----------
    is_theft : bool
        ``True`` when the ensemble judges the current pattern as theft.
    confidence : float
        Combined ensemble confidence in the range **[0.0, 1.0]**.
    anomaly_score : float
        Raw Isolation Forest anomaly score (higher → more anomalous).
    explanation : str
        Human-readable summary of the detection decision.
    features_used : dict
        The exact feature vector that was fed to the models, useful for
        debugging and audit logging.
    """

    is_theft: bool
    confidence: float          # 0.0 – 1.0
    anomaly_score: float       # raw isolation-forest score
    explanation: str
    features_used: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

class FeatureExtractor:
    """Extracts an 8-dimensional ML feature vector from a window of
    tank-level readings.

    Parameters
    ----------
    window_size : int
        Number of most-recent readings to consider.  At ~1 Hz sampling
        this corresponds to *window_size* seconds (default 60).
    """

    def __init__(self, window_size: int = 60) -> None:
        self.window_size: int = window_size

    # ---- public API -------------------------------------------------------

    def extract(
        self,
        level_history: List[Tuple[datetime, float]],
        generator_on: bool,
        current_time: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Extract features from *level_history*.

        Parameters
        ----------
        level_history :
            List of ``(datetime, level_pct)`` tuples ordered oldest →
            newest.
        generator_on :
            Whether the diesel generator is currently running.
        current_time :
            Optional explicit timestamp (ignored internally but kept for
            API symmetry with callers that track wall-clock time).

        Returns
        -------
        dict
            Eight named features consumed by :class:`TheftDetector`:

            * **rate_of_change** – level Δ per second over the last ~30 s
              (negative means dropping).
            * **rate_of_change_10s** – level Δ per second over the last
              ~10 s.
            * **rolling_std** – standard deviation of level over the
              recent sub-window.
            * **drop_magnitude** – maximum peak-to-current drop in the
              window.
            * **generator_state** – ``1.0`` if ON, ``0.0`` if OFF.
            * **level_current** – current tank level percentage.
            * **acceleration** – second derivative of level (change in
              rate-of-change).
            * **drop_sharpness** – ratio of the 10 s rate to the 30 s
              rate; theft events tend to produce sharper (higher) ratios.
        """
        # Need at least 3 readings to compute meaningful derivatives.
        if len(level_history) < 3:
            return self._default_features(generator_on, level_history)

        # Trim to the most recent *window_size* readings.
        window: List[Tuple[datetime, float]] = (
            level_history[-self.window_size:]
            if len(level_history) >= self.window_size
            else level_history
        )

        levels: List[float] = [lvl for _, lvl in window]
        # Elapsed seconds relative to start of window.
        times: List[float] = [
            (t - window[0][0]).total_seconds() for t, _ in window
        ]

        current_level: float = levels[-1]

        # -- Rate of change over ~30 s --------------------------------------
        idx_30: int = max(0, len(levels) - 30)
        dt_30: float = times[-1] - times[idx_30]
        roc_30: float = (
            (levels[-1] - levels[idx_30]) / dt_30 if dt_30 > 0 else 0.0
        )

        # -- Rate of change over ~10 s --------------------------------------
        idx_10: int = max(0, len(levels) - 10)
        dt_10: float = times[-1] - times[idx_10]
        roc_10: float = (
            (levels[-1] - levels[idx_10]) / dt_10 if dt_10 > 0 else 0.0
        )

        # -- Rolling standard deviation (last 30 readings, min 5) -----------
        rolling_std: float = (
            float(np.std(levels[-30:])) if len(levels) >= 5 else 0.0
        )

        # -- Drop magnitude (peak → current in window) ----------------------
        peak: float = max(levels)
        drop_magnitude: float = peak - current_level

        # -- Acceleration (Δ rate-of-change) ---------------------------------
        idx_mid: int = max(0, len(levels) - 20)
        dt_mid: float = times[idx_mid] - times[idx_30]
        if idx_mid > idx_30 and dt_mid > 0:
            roc_prev: float = (levels[idx_mid] - levels[idx_30]) / dt_mid
            acceleration: float = roc_10 - roc_prev
        else:
            acceleration = 0.0

        # -- Drop sharpness (10 s / 30 s ratio) -----------------------------
        drop_sharpness: float = abs(roc_10) / (abs(roc_30) + 1e-6)

        return {
            "rate_of_change": roc_30,
            "rate_of_change_10s": roc_10,
            "rolling_std": rolling_std,
            "drop_magnitude": drop_magnitude,
            "generator_state": 1.0 if generator_on else 0.0,
            "level_current": current_level,
            "acceleration": acceleration,
            "drop_sharpness": drop_sharpness,
        }

    # ---- helpers -----------------------------------------------------------

    def _default_features(
        self,
        generator_on: bool,
        level_history: List[Tuple[datetime, float]],
    ) -> Dict[str, float]:
        """Return zeroed features when insufficient data is available."""
        current: float = level_history[-1][1] if level_history else 50.0
        return {
            "rate_of_change": 0.0,
            "rate_of_change_10s": 0.0,
            "rolling_std": 0.0,
            "drop_magnitude": 0.0,
            "generator_state": 1.0 if generator_on else 0.0,
            "level_current": current,
            "acceleration": 0.0,
            "drop_sharpness": 0.0,
        }


# ---------------------------------------------------------------------------
# Ensemble theft detector
# ---------------------------------------------------------------------------

class TheftDetector:
    """Ensemble ML theft detector combining Isolation Forest with Gradient
    Boosting.

    On construction the detector tries to load a previously-saved model
    bundle from *model_path*.  If none is found, :meth:`predict` falls
    back to an enhanced rule-based heuristic until :meth:`train` is
    called.

    Parameters
    ----------
    model_path : str or None
        Path to a ``.joblib`` file containing a saved model bundle.
        Defaults to ``<this_dir>/models/theft_detector.joblib``.
    """

    # Canonical feature ordering used by the models.
    FEATURE_NAMES: List[str] = [
        "rate_of_change",
        "rate_of_change_10s",
        "rolling_std",
        "drop_magnitude",
        "generator_state",
        "level_current",
        "acceleration",
        "drop_sharpness",
    ]

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path: str = model_path or os.path.join(
            os.path.dirname(__file__), "models", "theft_detector.joblib"
        )
        self.isolation_forest: Optional[IsolationForest] = None
        self.classifier: Optional[GradientBoostingClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_extractor: FeatureExtractor = FeatureExtractor()
        self._is_trained: bool = False

        # Attempt to restore a previously-saved model.
        self._load_model()

    # ---- persistence -------------------------------------------------------

    def _load_model(self) -> None:
        """Try to load a pre-trained model bundle from disk."""
        try:
            if os.path.exists(self.model_path):
                bundle: Dict[str, Any] = joblib.load(self.model_path)
                self.isolation_forest = bundle["isolation_forest"]
                self.classifier = bundle["classifier"]
                self.scaler = bundle["scaler"]
                self._is_trained = True
        except Exception as exc:  # noqa: BLE001
            print(f"Could not load model: {exc}. Using rule-based fallback.")
            self._is_trained = False

    def _save_model(self) -> None:
        """Persist the trained model bundle to *self.model_path*."""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        bundle: Dict[str, Any] = {
            "isolation_forest": self.isolation_forest,
            "classifier": self.classifier,
            "scaler": self.scaler,
        }
        joblib.dump(bundle, self.model_path)

    # ---- training ----------------------------------------------------------

    def train(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train both ensemble components and save the resulting model.

        Parameters
        ----------
        X : np.ndarray, shape ``(n_samples, 8)``
            Feature matrix whose columns correspond to
            :attr:`FEATURE_NAMES`.
        y : np.ndarray, shape ``(n_samples,)``
            Binary labels — ``1`` for theft, ``0`` for normal operation.
        """
        # -- Standardise features --------------------------------------------
        self.scaler = StandardScaler()
        X_scaled: np.ndarray = self.scaler.fit_transform(X)

        # -- Isolation Forest (unsupervised) ---------------------------------
        self.isolation_forest = IsolationForest(
            n_estimators=200,
            contamination=0.05,
            random_state=42,
        )
        self.isolation_forest.fit(X_scaled)

        # -- Gradient Boosting Classifier (supervised) -----------------------
        self.classifier = GradientBoostingClassifier(
            n_estimators=150,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
        )
        self.classifier.fit(X_scaled, y)

        self._is_trained = True
        self._save_model()

    # ---- inference ---------------------------------------------------------

    def predict(
        self,
        level_history: List[Tuple[datetime, float]],
        generator_on: bool,
        current_time: Optional[datetime] = None,
    ) -> AnomalyResult:
        """Run theft detection on the current tank state.

        Parameters
        ----------
        level_history :
            Chronological ``(datetime, level_pct)`` readings.
        generator_on :
            Whether the generator is currently running.
        current_time :
            Optional wall-clock override (forwarded to
            :class:`FeatureExtractor`).

        Returns
        -------
        AnomalyResult
            Detection result with confidence score and explanation.
        """
        features: Dict[str, float] = self.feature_extractor.extract(
            level_history, generator_on, current_time
        )

        # Fall back to rules when no ML model is available.
        if not self._is_trained:
            return self._rule_based_fallback(features)

        # Build feature row in canonical order.
        X: np.ndarray = np.array(
            [[features[f] for f in self.FEATURE_NAMES]]
        )
        X_scaled: np.ndarray = self.scaler.transform(X)  # type: ignore[union-attr]

        # -- Isolation Forest anomaly score ----------------------------------
        # sklearn returns negative scores; negate so higher = more anomalous.
        anomaly_score: float = float(
            -self.isolation_forest.score_samples(X_scaled)[0]  # type: ignore[union-attr]
        )

        # -- Gradient Boosting theft probability -----------------------------
        theft_proba: float = float(
            self.classifier.predict_proba(X_scaled)[0][1]  # type: ignore[union-attr]
        )

        # -- Ensemble combination -------------------------------------------
        # Normalise IF score into [0, 1] and blend 40/60 with GB probability.
        if_confidence: float = min(1.0, max(0.0, (anomaly_score - 0.4) / 0.3))
        combined_confidence: float = 0.4 * if_confidence + 0.6 * theft_proba

        # Only flag theft when generator is OFF (no legitimate consumption).
        is_theft: bool = (
            combined_confidence > 0.5 and features["generator_state"] == 0.0
        )

        # Human-readable explanation.
        explanation: str = (
            self._generate_explanation(features, combined_confidence)
            if is_theft
            else "Normal operation"
        )

        return AnomalyResult(
            is_theft=is_theft,
            confidence=round(combined_confidence, 3),
            anomaly_score=round(anomaly_score, 3),
            explanation=explanation,
            features_used=features,
        )

    # ---- fallback / explanation helpers ------------------------------------

    def _rule_based_fallback(self, features: Dict[str, float]) -> AnomalyResult:
        """Enhanced rule-based heuristic used when no ML model is trained.

        Criteria:
        * Generator is OFF.
        * Rate of change < −0.08 %/s  (~5 %/min drop).
        * Drop magnitude > 3 %.
        """
        is_theft: bool = (
            features["generator_state"] == 0.0
            and features["rate_of_change"] < -0.08
            and features["drop_magnitude"] > 3.0
        )

        confidence: float = 0.0
        if is_theft:
            confidence = min(1.0, abs(features["rate_of_change"]) / 0.2)

        return AnomalyResult(
            is_theft=is_theft,
            confidence=round(confidence, 3),
            anomaly_score=0.0,
            explanation=(
                "THEFT SUSPECTED (rule-based)"
                if is_theft
                else "Normal (rule-based fallback)"
            ),
            features_used=features,
        )

    def _generate_explanation(
        self,
        features: Dict[str, float],
        confidence: float,
    ) -> str:
        """Build a human-readable theft explanation string."""
        parts: List[str] = [
            f"\u26a0\ufe0f THEFT SUSPECTED (confidence: {confidence:.0%})"
        ]

        roc: float = features["rate_of_change"]
        parts.append(f"Level dropping at {abs(roc) * 60:.1f}%/min")
        parts.append(f"Drop magnitude: {features['drop_magnitude']:.1f}%")

        if features["drop_sharpness"] > 2.0:
            parts.append("Unusually sharp drop detected")

        parts.append(
            "Generator is OFF \u2014 no legitimate consumption expected"
        )

        return " | ".join(parts)

    # ---- introspection -----------------------------------------------------

    @property
    def is_trained(self) -> bool:
        """``True`` when an ML model is loaded and ready for inference."""
        return self._is_trained

    def get_feature_importance(self) -> Dict[str, float]:
        """Return per-feature importances from the Gradient Boosting model.

        Returns
        -------
        dict
            Mapping of feature name → importance (sums to ~1.0).
            Empty dict if the model has not been trained.
        """
        if not self._is_trained or self.classifier is None:
            return {}
        importances: np.ndarray = self.classifier.feature_importances_
        return dict(
            zip(
                self.FEATURE_NAMES,
                [round(float(v), 4) for v in importances],
            )
        )
