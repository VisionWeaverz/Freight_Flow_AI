"""Training script for scikit-learn disruption risk model on synthetic and database telemetry."""

from __future__ import annotations
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3
import numpy as np
from typing import Tuple, Dict, Any, Optional
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score
import joblib

from src.risk_engine.feature_pipeline import FeaturePipeline

DEFAULT_DB_CANDIDATES = [
    "data/freightflow.db",
    "freightflow.db",
    os.path.join(os.path.dirname(__file__), "../../data/freightflow.db"),
    os.path.join(os.path.dirname(__file__), "../../freightflow.db"),
]

DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "../../data/synthetic/risk_model.joblib"
)


def resolve_db_path(explicit_path: Optional[str] = None) -> str:
    """Finds existing freightflow.db or returns default."""
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path
    for p in DEFAULT_DB_CANDIDATES:
        norm = os.path.normpath(p)
        if os.path.exists(norm):
            return norm
    return "data/freightflow.db"


def load_dataset(db_path: Optional[str] = None) -> Tuple[np.ndarray, np.ndarray]:
    """Loads shipment features and binary disruption labels from SQLite."""
    target_db = resolve_db_path(db_path)
    if not os.path.exists(target_db):
        raise FileNotFoundError(f"Database not found at '{target_db}'. Run generate_data.py first.")

    conn = sqlite3.connect(target_db)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT historical_delay_rate, port_congestion_index, delay_hours, cargo_value_inr, is_delayed
        FROM shipments
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        raise ValueError(f"Shipments table in '{target_db}' is empty.")

    data = np.array(rows, dtype=np.float64)
    pipeline = FeaturePipeline()
    X = pipeline.extract_features(data[:, :4])
    y = data[:, 4].astype(int)
    return X, y


def train_risk_model(
    db_path: Optional[str] = None,
    output_model_path: Optional[str] = None
) -> Tuple[GradientBoostingClassifier, Dict[str, Any]]:
    """Trains scikit-learn GradientBoostingClassifier and exports model weights."""
    target_output = output_model_path or DEFAULT_MODEL_PATH
    os.makedirs(os.path.dirname(os.path.abspath(target_output)), exist_ok=True)

    X, y = load_dataset(db_path)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = GradientBoostingClassifier(
        n_estimators=120,
        learning_rate=0.08,
        max_depth=4,
        random_state=42
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]

    acc = float(accuracy_score(y_test, y_pred))
    auc = float(roc_auc_score(y_test, y_proba))

    metrics = {
        "accuracy": acc,
        "roc_auc": auc,
        "feature_importances": dict(zip(FeaturePipeline.FEATURE_NAMES, [float(v) for v in clf.feature_importances_]))
    }

    joblib.dump(clf, target_output)
    print(f"Risk model exported successfully to: {target_output}")
    print(f"Accuracy: {acc:.4f} | ROC-AUC: {auc:.4f}")
    return clf, metrics


if __name__ == "__main__":
    train_risk_model()
