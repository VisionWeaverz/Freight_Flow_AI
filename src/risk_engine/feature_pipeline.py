"""Feature engineering pipeline for freight disruption prediction."""

from __future__ import annotations
from typing import Dict, Any, List, Union
import numpy as np
try:
    import pandas as pd
except ImportError:
    pd = None


class FeaturePipeline:
    """Prepares raw shipment and simulated signal data into feature matrices."""

    FEATURE_NAMES = [
        "historical_delay_rate",
        "port_congestion_index",
        "delay_hours",
        "cargo_value_inr"
    ]

    def __init__(self):
        pass

    def extract_features(self, raw_data: Union[Dict[str, Any], List[Dict[str, Any]], np.ndarray]) -> np.ndarray:
        """Transform raw shipment attributes into model-ready numerical feature matrix (N, 4).

        Features:
        0: historical_delay_rate (float)
        1: port_congestion_index (float)
        2: delay_hours (float)
        3: cargo_value_inr (float)
        """
        if isinstance(raw_data, np.ndarray):
            if raw_data.ndim == 1:
                return raw_data.reshape(1, -1)[:, :4]
            return raw_data[:, :4]

        if isinstance(raw_data, dict):
            raw_data = [raw_data]

        features_list = []
        for item in raw_data:
            h_rate = float(item.get("historical_delay_rate", 0.25))
            cong = float(item.get("port_congestion_index", item.get("congestion", 0.50)))
            del_hrs = float(item.get("delay_hours", item.get("new_delay_hours", 0.0)))
            c_val = float(item.get("cargo_value_inr", item.get("value_inr", 2500000.0)))
            features_list.append([h_rate, cong, del_hrs, c_val])

        return np.array(features_list, dtype=np.float64)
