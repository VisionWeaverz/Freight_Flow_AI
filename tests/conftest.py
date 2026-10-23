"""
Pytest session fixtures for FreightFlow AI tests.

Ensures `data/freightflow.db` is initialised with the correct unified schema
and the SHP-1005 anchor shipment before any test that queries the database.

Design decisions:
- Uses generate_data.py (project root) directly — the single source of truth
  for the telemetry schema (shipments, truck_bookings, warehouse_slots).
- Session-scoped so the DB is created once per pytest run, not per test.
- autouse=True so cascade and risk-engine tests never need to import this
  fixture explicitly.
- Does NOT swallow errors: if DB creation fails the test session fails loudly.
"""

import os
import sys
from pathlib import Path
import pytest

# Ensure project root is on sys.path (mirrors what src/main.py does)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session", autouse=True)
def ensure_freightflow_db():
    """Creates data/freightflow.db with the unified telemetry schema.

    Calls generate_data.init_db() + generate_data.populate_data() which:
    - DROP + CREATE the telemetry tables (shipments, truck_bookings,
      warehouse_slots) with the correct merged column set.
    - Inserts the fixed SHP-1005 benchmark row required by cascade tests.
    - Inserts 1,200 synthetic cohort rows required by the risk model training.

    If the DB already exists with the correct data (idempotent check via
    generate_data internals), the populate step skips duplicates via
    INSERT OR IGNORE.  The DROP+CREATE in init_db() means schema is always
    guaranteed correct, so stale schemas from previous runs are not a risk.
    """
    import generate_data

    db_path = PROJECT_ROOT / "data" / "freightflow.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = generate_data.init_db(str(db_path))
    generate_data.populate_data(conn)
    conn.close()

    # Sanity-check that SHP-1005 is present before any test runs
    import sqlite3
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT shipment_id FROM shipments WHERE shipment_id = 'SHP-1005'"
        ).fetchone()
    if row is None:
        raise RuntimeError(
            "conftest: SHP-1005 was not found in data/freightflow.db after "
            "seeding. Check generate_data.populate_data()."
        )

    yield  # tests run here

    # No teardown: leave the DB intact so developers can inspect it locally.
    # The next pytest run will DROP+recreate tables via generate_data.init_db().
