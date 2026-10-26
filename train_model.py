"""
Training Script — Generate Synthetic Data and Train ML Theft Detector.

Generates synthetic training data representing both normal tank operations
and theft events, then trains the Isolation Forest + Gradient Boosting
ensemble and saves it to ``models/theft_detector.joblib``.

Synthetic Data Generation Strategy
-----------------------------------

**Normal operation patterns (label=0):**

1. *Stable idle* — level barely changes, generator OFF, tiny random noise
   (rate_of_change ≈ 0).
2. *Generator consumption* — generator ON, slow steady drops
   (rate_of_change = −0.01 to −0.05 %/s, consistent).
3. *Pump refill* — level rising steadily
   (rate_of_change = +0.05 to +0.5 %/s, generator OFF).
4. *Small fluctuations* — sensor noise, temperature effects
   (rolling_std < 0.5).

**Theft patterns (label=1):**

1. *Siphoning* — generator OFF, rate_of_change = −0.1 to −0.5 %/s,
   high drop_magnitude, high drop_sharpness.
2. *Quick drain* — generator OFF, rate_of_change = −0.3 to −1.0 %/s,
   very high acceleration.
3. *Partial theft* — generator OFF, moderate rate_of_change = −0.08
   to −0.2 %/s.
"""

import numpy as np
import pandas as pd
import os
import sys

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so we can import ml_detector
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ml_detector import TheftDetector

# Feature vector column names (must match the order used in ml_detector)
FEATURE_NAMES: list[str] = [
    "rate_of_change",
    "rate_of_change_10s",
    "rolling_std",
    "drop_magnitude",
    "generator_state",
    "level_current",
    "acceleration",
    "drop_sharpness",
]


def generate_normal_samples(n: int = 3000) -> tuple[np.ndarray, np.ndarray]:
    """Generate *n* normal-operation feature vectors.

    Each sample is drawn from one of four plausible operating modes:
    idle, generator consumption, pump refill, or sensor noise.

    Parameters
    ----------
    n : int
        Number of samples to generate (default 3 000).

    Returns
    -------
    X : np.ndarray, shape (n, 8)
        Feature matrix.
    y : np.ndarray, shape (n,)
        Labels — all zeros (normal).
    """
    samples: list[list[float]] = []

    for _ in range(n):
        pattern = np.random.choice(
            ["idle", "consumption", "refill", "noise"],
            p=[0.35, 0.30, 0.15, 0.20],
        )

        if pattern == "idle":
            # Stable, generator OFF
            roc = np.random.normal(0, 0.005)
            roc_10 = roc + np.random.normal(0, 0.003)
            std = np.random.uniform(0, 0.3)
            drop_mag = np.random.uniform(0, 1.5)
            gen = 0.0
            level = np.random.uniform(20, 90)
            acc = np.random.normal(0, 0.002)
            sharpness = np.random.uniform(0.5, 1.5)

        elif pattern == "consumption":
            # Generator ON, steady drop
            roc = np.random.uniform(-0.05, -0.005)
            roc_10 = roc + np.random.normal(0, 0.005)
            std = np.random.uniform(0.1, 0.8)
            drop_mag = np.random.uniform(0.5, 5.0)
            gen = 1.0
            level = np.random.uniform(10, 85)
            acc = np.random.normal(0, 0.003)
            sharpness = np.random.uniform(0.7, 1.5)

        elif pattern == "refill":
            # Pump filling, level rising
            roc = np.random.uniform(0.05, 0.5)
            roc_10 = roc + np.random.normal(0, 0.01)
            std = np.random.uniform(0.2, 1.0)
            drop_mag = 0.0
            gen = 0.0
            level = np.random.uniform(15, 88)
            acc = np.random.normal(0, 0.005)
            sharpness = np.random.uniform(0.5, 1.2)

        else:  # noise
            roc = np.random.normal(0, 0.02)
            roc_10 = roc + np.random.normal(0, 0.01)
            std = np.random.uniform(0.1, 0.5)
            drop_mag = np.random.uniform(0, 2.0)
            gen = float(np.random.choice([0, 1]))
            level = np.random.uniform(10, 95)
            acc = np.random.normal(0, 0.005)
            sharpness = np.random.uniform(0.5, 2.0)

        samples.append([roc, roc_10, std, drop_mag, gen, level, acc, sharpness])

    return np.array(samples), np.zeros(n)


def generate_theft_samples(n: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """Generate *n* theft-event feature vectors.

    Samples span three severity levels — mild, moderate, and severe —
    each with distinct rate-of-change and drop-magnitude ranges.

    Parameters
    ----------
    n : int
        Number of samples to generate (default 500).

    Returns
    -------
    X : np.ndarray, shape (n, 8)
        Feature matrix.
    y : np.ndarray, shape (n,)
        Labels — all ones (theft).
    """
    samples: list[list[float]] = []

    for _ in range(n):
        severity = np.random.choice(
            ["mild", "moderate", "severe"], p=[0.2, 0.5, 0.3]
        )

        if severity == "mild":
            roc = np.random.uniform(-0.15, -0.08)
            roc_10 = roc * np.random.uniform(1.0, 1.5)
            std = np.random.uniform(0.5, 2.0)
            drop_mag = np.random.uniform(3.0, 8.0)
            sharpness = np.random.uniform(1.5, 3.0)
        elif severity == "moderate":
            roc = np.random.uniform(-0.35, -0.12)
            roc_10 = roc * np.random.uniform(1.2, 2.0)
            std = np.random.uniform(1.0, 4.0)
            drop_mag = np.random.uniform(5.0, 15.0)
            sharpness = np.random.uniform(2.0, 5.0)
        else:  # severe
            roc = np.random.uniform(-0.8, -0.3)
            roc_10 = roc * np.random.uniform(1.5, 3.0)
            std = np.random.uniform(2.0, 6.0)
            drop_mag = np.random.uniform(10.0, 30.0)
            sharpness = np.random.uniform(3.0, 8.0)

        gen = 0.0  # generator always OFF during theft
        level = np.random.uniform(20, 80)
        acc = np.random.uniform(-0.05, -0.005)

        samples.append([roc, roc_10, std, drop_mag, gen, level, acc, sharpness])

    return np.array(samples), np.ones(n)


# ───────────────────────────────────────────────────────────────────────────
# Main entry-point
# ───────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Generate synthetic data, train the theft-detection model, and evaluate."""
    print("=" * 60)
    print("Diesel Tank Theft Detector — Model Training")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Generate data
    # ------------------------------------------------------------------
    print("\n📊 Generating synthetic training data...")
    X_normal, y_normal = generate_normal_samples(3000)
    X_theft, y_theft = generate_theft_samples(500)

    X = np.vstack([X_normal, X_theft])
    y = np.concatenate([y_normal, y_theft])

    # Shuffle
    indices = np.random.permutation(len(y))
    X, y = X[indices], y[indices]

    print(f"  Normal samples: {len(y_normal)}")
    print(f"  Theft samples:  {len(y_theft)}")
    print(f"  Total:          {len(y)}")

    # ------------------------------------------------------------------
    # 2. Train / test split
    # ------------------------------------------------------------------
    from sklearn.model_selection import train_test_split  # noqa: E402

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # ------------------------------------------------------------------
    # 3. Train the detector
    # ------------------------------------------------------------------
    print("\n🤖 Training ML models...")
    detector = TheftDetector()
    detector.train(X_train, y_train)
    print("  ✅ Models trained and saved!")

    # ------------------------------------------------------------------
    # 4. Evaluate on the held-out test set
    # ------------------------------------------------------------------
    print("\n📈 Evaluation on test set:")
    from sklearn.metrics import classification_report, confusion_matrix  # noqa: E402

    # Predict using the trained classifier directly
    X_test_scaled = detector.scaler.transform(X_test)
    y_pred = detector.classifier.predict(X_test_scaled)

    print(
        classification_report(y_test, y_pred, target_names=["Normal", "Theft"])
    )
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    # ------------------------------------------------------------------
    # 5. Feature importance
    # ------------------------------------------------------------------
    print("\n🔍 Feature Importance:")
    importance = detector.get_feature_importance()
    for feat, imp in sorted(importance.items(), key=lambda x: -x[1]):
        bar = "█" * int(imp * 50)
        print(f"  {feat:25s} {imp:.4f} {bar}")

    print(f"\n✅ Model saved to: {detector.model_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
