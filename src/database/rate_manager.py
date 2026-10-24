"""Rate Card Manager for FreightFlow AI.

Manages pricing tariffs and penalty schedules:
- Truck driver waiting/detention rate (INR/hr)
- Customer contractual SLA late delivery fine (INR/hr)
- Warehouse missed appointment slot penalty (INR flat)
- Warehouse emergency overtime labor rate (INR/hr)

Supports uploading custom CSV rate cards, updating SQLite records, and restoring synthetic defaults.
"""

from __future__ import annotations
import csv
import io
import os
import sqlite3
from typing import Dict, Any, Optional, Tuple, List

DEFAULT_DB_CANDIDATES = [
    "data/freightflow.db",
    "freightflow.db",
    os.path.join(os.path.dirname(__file__), "../../data/freightflow.db"),
    os.path.join(os.path.dirname(__file__), "../../freightflow.db"),
]

SYNTHETIC_BASELINE_RATES: Dict[str, float] = {
    "driver_waiting_cost_per_hr": 500.0,
    "sla_penalty_per_hour_inr": 3000.0,
    "missed_slot_penalty_inr": 12500.0,
    "overtime_cost_per_hr": 1800.0,
}

RATE_FIELD_METADATA = {
    "driver_waiting_cost_per_hr": {
        "label": "Truck Driver Waiting Rate",
        "unit": "₹ / hour",
        "description": "Detention fee charged when a driver is held up at berth or en route.",
        "default": 500.0,
    },
    "sla_penalty_per_hour_inr": {
        "label": "Customer Late SLA Penalty",
        "unit": "₹ / hour",
        "description": "Contractual fine owed to customer for every hour past promise delivery time.",
        "default": 3000.0,
    },
    "missed_slot_penalty_inr": {
        "label": "Warehouse Missed Slot Fine",
        "unit": "₹ flat fee",
        "description": "Forfeited dock bay intake appointment fee due to arrival past buffer.",
        "default": 12500.0,
    },
    "overtime_cost_per_hr": {
        "label": "Warehouse Overtime Labor Rate",
        "unit": "₹ / hour",
        "description": "After-hours intake crew wage required to clear off-schedule freight.",
        "default": 1800.0,
    },
}

FIELD_ALIASES: Dict[str, str] = {
    # Driver wait rate aliases
    "driver_waiting_cost_per_hr": "driver_waiting_cost_per_hr",
    "driver_wait_cost_per_hr": "driver_waiting_cost_per_hr",
    "driver_rate_per_hr": "driver_waiting_cost_per_hr",
    "driver_rate": "driver_waiting_cost_per_hr",
    "driver_waiting_rate": "driver_waiting_cost_per_hr",
    "driver_detention_rate": "driver_waiting_cost_per_hr",
    "driver_waiting_cost": "driver_waiting_cost_per_hr",
    
    # SLA penalty aliases
    "sla_penalty_per_hour_inr": "sla_penalty_per_hour_inr",
    "sla_penalty_per_hr": "sla_penalty_per_hour_inr",
    "sla_penalty_rate_per_hr": "sla_penalty_per_hour_inr",
    "customer_sla_penalty": "sla_penalty_per_hour_inr",
    "customer_sla_fine": "sla_penalty_per_hour_inr",
    "sla_penalty": "sla_penalty_per_hour_inr",
    "sla_fine": "sla_penalty_per_hour_inr",
    "late_delivery_fine_per_hr": "sla_penalty_per_hour_inr",

    # Missed slot penalty aliases
    "missed_slot_penalty_inr": "missed_slot_penalty_inr",
    "missed_slot_penalty": "missed_slot_penalty_inr",
    "dock_missed_penalty": "missed_slot_penalty_inr",
    "warehouse_slot_fine": "missed_slot_penalty_inr",
    "missed_slot_fine": "missed_slot_penalty_inr",
    "dock_appointment_penalty": "missed_slot_penalty_inr",

    # Warehouse overtime rate aliases
    "overtime_cost_per_hr": "overtime_cost_per_hr",
    "overtime_rate_per_hr": "overtime_cost_per_hr",
    "warehouse_overtime_rate": "overtime_cost_per_hr",
    "overtime_cost": "overtime_cost_per_hr",
    "overtime_labor_rate": "overtime_cost_per_hr",
    "whs_overtime_per_hr": "overtime_cost_per_hr",
}


def resolve_db_path(explicit_path: Optional[str] = None) -> str:
    """Finds existing freightflow.db or defaults to candidate."""
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path
    for p in DEFAULT_DB_CANDIDATES:
        norm = os.path.normpath(p)
        if os.path.exists(norm):
            return norm
    return "data/freightflow.db"


def get_active_pricing(
    shipment_id: str = "SHP-1005",
    db_path: Optional[str] = None
) -> Dict[str, float]:
    """Retrieves active contractual prices and penalties from SQLite for a shipment."""
    target_db = resolve_db_path(db_path)
    if not os.path.exists(target_db):
        return dict(SYNTHETIC_BASELINE_RATES)

    rates = dict(SYNTHETIC_BASELINE_RATES)
    conn = sqlite3.connect(target_db)
    cursor = conn.cursor()

    try:
        # 1. Customer SLA penalty from shipments
        cursor.execute(
            "SELECT sla_penalty_per_hour_inr FROM shipments WHERE shipment_id = ?",
            (shipment_id,)
        )
        row = cursor.fetchone()
        if row and row[0] is not None:
            rates["sla_penalty_per_hour_inr"] = float(row[0])

        # 2. Driver waiting rate from truck_bookings
        cursor.execute(
            "SELECT driver_waiting_cost_per_hr FROM truck_bookings WHERE shipment_id = ?",
            (shipment_id,)
        )
        row = cursor.fetchone()
        if row and row[0] is not None:
            rates["driver_waiting_cost_per_hr"] = float(row[0])

        # 3. Warehouse penalties from warehouse_slots
        cursor.execute(
            "SELECT missed_slot_penalty_inr, overtime_cost_per_hr FROM warehouse_slots WHERE shipment_id = ?",
            (shipment_id,)
        )
        row = cursor.fetchone()
        if row:
            if row[0] is not None:
                rates["missed_slot_penalty_inr"] = float(row[0])
            if row[1] is not None:
                rates["overtime_cost_per_hr"] = float(row[1])
    except Exception:
        pass
    finally:
        conn.close()

    return rates


def is_custom_pricing_active(
    shipment_id: str = "SHP-1005",
    db_path: Optional[str] = None
) -> bool:
    """Checks whether the database currently contains non-default rates."""
    active = get_active_pricing(shipment_id=shipment_id, db_path=db_path)
    for key, baseline_val in SYNTHETIC_BASELINE_RATES.items():
        if abs(active.get(key, baseline_val) - baseline_val) > 0.01:
            return True
    return False


def parse_pricing_csv(csv_text: str) -> Tuple[bool, str, Dict[str, float]]:
    """Parses and validates CSV text containing price tariffs.

    Supports both:
    1. Key-Value format (rate_name, rate_inr, [unit, description])
    2. Columnar format (header contains rate field names or aliases)

    Returns:
        (success: bool, message: str, parsed_rates: Dict[str, float])
    """
    if not csv_text or not csv_text.strip():
        return False, "CSV content is empty.", {}

    cleaned = csv_text.strip()
    reader = csv.reader(io.StringIO(cleaned))
    rows = [r for r in reader if r and any(cell.strip() for cell in r)]

    if not rows:
        return False, "No valid data rows found in CSV.", {}

    header = [c.strip().lower() for c in rows[0]]
    parsed_rates: Dict[str, float] = {}

    # Check if format is Key-Value (typically 2 to 4 columns, e.g. name, value)
    is_key_value = any(k in header[0] for k in ["rate", "parameter", "name", "field", "metric"]) and len(header) >= 2

    if is_key_value:
        for idx, row in enumerate(rows[1:], start=2):
            if len(row) < 2:
                continue
            raw_key = row[0].strip().lower().replace(" ", "_").replace("-", "_")
            raw_val = row[1].strip().replace("₹", "").replace(",", "").replace("$", "")
            
            canonical_key = FIELD_ALIASES.get(raw_key)
            if not canonical_key:
                continue

            try:
                val = float(raw_val)
                if val < 0:
                    return False, f"Line {idx}: Rate '{raw_key}' cannot be negative ({val}).", {}
                parsed_rates[canonical_key] = round(val, 2)
            except ValueError:
                return False, f"Line {idx}: Invalid numeric value '{raw_val}' for '{raw_key}'.", {}
    else:
        # Check Columnar format
        matched_cols: Dict[int, str] = {}
        for c_idx, col_name in enumerate(header):
            clean_col = col_name.strip().lower().replace(" ", "_").replace("-", "_")
            canonical = FIELD_ALIASES.get(clean_col)
            if canonical:
                matched_cols[c_idx] = canonical

        if not matched_cols:
            # Fallback: check if the first row was already data without header
            for row in rows:
                if len(row) >= 2:
                    raw_k = row[0].strip().lower().replace(" ", "_")
                    can = FIELD_ALIASES.get(raw_k)
                    if can:
                        try:
                            val = float(row[1].strip().replace("₹", "").replace(",", ""))
                            if val >= 0:
                                parsed_rates[can] = round(val, 2)
                        except ValueError:
                            pass

        if not parsed_rates and matched_cols:
            # Parse data row (taking the first matching valid data row)
            for r_idx, row in enumerate(rows[1:], start=2):
                for c_idx, canonical_key in matched_cols.items():
                    if c_idx < len(row):
                        raw_val = row[c_idx].strip().replace("₹", "").replace(",", "").replace("$", "")
                        if raw_val:
                            try:
                                val = float(raw_val)
                                if val < 0:
                                    return False, f"Line {r_idx}: Rate '{canonical_key}' cannot be negative.", {}
                                parsed_rates[canonical_key] = round(val, 2)
                            except ValueError:
                                return False, f"Line {r_idx}: Invalid numeric value '{raw_val}'.", {}
                if parsed_rates:
                    break

    if not parsed_rates:
        return (
            False,
            "Could not detect recognized price columns. Please use names like "
            "'driver_waiting_cost_per_hr', 'sla_penalty_per_hour_inr', "
            "'missed_slot_penalty_inr', or 'overtime_cost_per_hr'.",
            {}
        )

    return True, f"Successfully parsed {len(parsed_rates)} pricing rates.", parsed_rates


def apply_pricing_to_db(
    rates: Dict[str, float],
    shipment_id: Optional[str] = None,
    apply_to_all: bool = True,
    db_path: Optional[str] = None
) -> Tuple[bool, str]:
    """Updates SQLite records with custom rates."""
    target_db = resolve_db_path(db_path)
    if not os.path.exists(target_db):
        return False, f"Database not found at '{target_db}'."

    conn = sqlite3.connect(target_db)
    cursor = conn.cursor()

    try:
        # Update shipments (SLA Penalty)
        if "sla_penalty_per_hour_inr" in rates:
            sla_val = rates["sla_penalty_per_hour_inr"]
            if apply_to_all or shipment_id is None:
                cursor.execute(
                    "UPDATE shipments SET sla_penalty_per_hour_inr = ?",
                    (sla_val,)
                )
            else:
                cursor.execute(
                    "UPDATE shipments SET sla_penalty_per_hour_inr = ? WHERE shipment_id = ?",
                    (sla_val, shipment_id)
                )

        # Update truck_bookings (Driver Wait Rate)
        if "driver_waiting_cost_per_hr" in rates:
            drv_val = rates["driver_waiting_cost_per_hr"]
            if apply_to_all or shipment_id is None:
                cursor.execute(
                    "UPDATE truck_bookings SET driver_waiting_cost_per_hr = ?",
                    (drv_val,)
                )
            else:
                cursor.execute(
                    "UPDATE truck_bookings SET driver_waiting_cost_per_hr = ? WHERE shipment_id = ?",
                    (drv_val, shipment_id)
                )

        # Update warehouse_slots (Missed Slot Fine & Overtime Rate)
        whs_updates = []
        whs_params = []
        if "missed_slot_penalty_inr" in rates:
            whs_updates.append("missed_slot_penalty_inr = ?")
            whs_params.append(rates["missed_slot_penalty_inr"])
        if "overtime_cost_per_hr" in rates:
            whs_updates.append("overtime_cost_per_hr = ?")
            whs_params.append(rates["overtime_cost_per_hr"])

        if whs_updates:
            set_clause = ", ".join(whs_updates)
            if apply_to_all or shipment_id is None:
                cursor.execute(f"UPDATE warehouse_slots SET {set_clause}", tuple(whs_params))
            else:
                whs_params.append(shipment_id)
                cursor.execute(f"UPDATE warehouse_slots SET {set_clause} WHERE shipment_id = ?", tuple(whs_params))

        conn.commit()
        return True, "Database pricing rates successfully updated."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to update database pricing: {str(e)}"
    finally:
        conn.close()


def reset_pricing_to_synthetic(
    shipment_id: Optional[str] = None,
    reset_all: bool = True,
    db_path: Optional[str] = None
) -> Tuple[bool, str]:
    """Restores database rates back to synthetic baseline benchmark defaults."""
    return apply_pricing_to_db(
        SYNTHETIC_BASELINE_RATES,
        shipment_id=shipment_id,
        apply_to_all=reset_all,
        db_path=db_path
    )


def get_sample_csv_template(format_type: str = "key_value") -> str:
    """Returns downloadable CSV template string."""
    if format_type == "columnar":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "shipment_id",
            "driver_waiting_cost_per_hr",
            "sla_penalty_per_hour_inr",
            "missed_slot_penalty_inr",
            "overtime_cost_per_hr"
        ])
        writer.writerow(["SHP-1005", 750.0, 5000.0, 18000.0, 2400.0])
        writer.writerow(["DEFAULT", 600.0, 4000.0, 15000.0, 2000.0])
        return output.getvalue()

    # Default Key-Value format
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["rate_name", "rate_inr", "unit", "description"])
    writer.writerow([
        "driver_waiting_cost_per_hr",
        750.0,
        "₹/hr",
        "Truck driver detention waiting rate per hour"
    ])
    writer.writerow([
        "sla_penalty_per_hour_inr",
        5000.0,
        "₹/hr",
        "Customer late delivery contractual penalty per hour"
    ])
    writer.writerow([
        "missed_slot_penalty_inr",
        18000.0,
        "₹ flat fee",
        "Warehouse forfeited dock intake appointment fee"
    ])
    writer.writerow([
        "overtime_cost_per_hr",
        2400.0,
        "₹/hr",
        "Warehouse emergency overtime labor crew rate per hour"
    ])
    return output.getvalue()
