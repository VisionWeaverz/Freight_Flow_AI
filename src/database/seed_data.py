"""Seed script to populate SQLite with initial mock supply chain records and telemetry."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3
import random
from datetime import datetime, timedelta
from src.database.connection import engine, Base, SessionLocal
from src.database.models import ScheduleSlotRecord  # ShipmentRecord rows are seeded by generate_data.py
from src.common.config import BASE_DIR

DB_PATH = BASE_DIR / "data" / "freightflow.db"


def seed_telemetry_tables(db_file: str):
    """Initializes and seeds shipments, truck_bookings, and warehouse_slots for risk and cascade modeling."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shipments (
        shipment_id TEXT PRIMARY KEY,
        origin_port TEXT NOT NULL,
        destination_hub TEXT NOT NULL,
        historical_delay_rate REAL NOT NULL,
        port_congestion_index REAL NOT NULL,
        delay_hours REAL NOT NULL,
        cargo_value_inr REAL NOT NULL,
        is_delayed INTEGER NOT NULL,
        eta_port_berth TEXT NOT NULL,
        customer_promise_time TEXT NOT NULL,
        customer_name TEXT DEFAULT 'Enterprise Client',
        sla_penalty_per_hour_inr REAL DEFAULT 2500.0,
        created_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS truck_bookings (
        booking_id TEXT PRIMARY KEY,
        shipment_id TEXT NOT NULL,
        driver_name TEXT NOT NULL,
        truck_number TEXT NOT NULL,
        scheduled_pickup_time TEXT NOT NULL,
        max_driver_wait_hours_allowed REAL NOT NULL,
        driver_waiting_cost_per_hr REAL NOT NULL,
        transit_time_hours REAL NOT NULL,
        status TEXT DEFAULT 'CONFIRMED',
        FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warehouse_slots (
        slot_id TEXT PRIMARY KEY,
        shipment_id TEXT NOT NULL,
        warehouse_id TEXT NOT NULL,
        scheduled_slot_time TEXT NOT NULL,
        max_buffer_minutes REAL NOT NULL,
        missed_slot_penalty_inr REAL NOT NULL,
        overtime_cost_per_hr REAL NOT NULL,
        dock_bay TEXT DEFAULT 'BAY-3',
        status TEXT DEFAULT 'RESERVED',
        FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id)
    )
    """)

    # Seed SHP-1005 benchmark if missing
    cursor.execute("SELECT shipment_id FROM shipments WHERE shipment_id = 'SHP-1005'")
    if not cursor.fetchone():
        base_date = datetime(2026, 10, 23, 8, 0, 0)
        cursor.execute("""
            INSERT INTO shipments (
                shipment_id, origin_port, destination_hub, historical_delay_rate,
                port_congestion_index, delay_hours, cargo_value_inr, is_delayed,
                eta_port_berth, customer_promise_time, customer_name, sla_penalty_per_hour_inr, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "SHP-1005", "Nhava Sheva (JNPT)", "Bhiwandi Hub", 0.32,
            0.65, 0.0, 4500000.0, 0,
            base_date.isoformat(), (base_date + timedelta(hours=9)).isoformat(),
            "AutoParts Direct India", 3000.0, datetime.now().isoformat()
        ))

        cursor.execute("""
            INSERT INTO truck_bookings (
                booking_id, shipment_id, driver_name, truck_number,
                scheduled_pickup_time, max_driver_wait_hours_allowed,
                driver_waiting_cost_per_hr, transit_time_hours, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "TRK-1005", "SHP-1005", "Ramesh Yadav", "MH-04-AB-1005",
            (base_date + timedelta(hours=1)).isoformat(), 2.0, 500.0, 3.5, "CONFIRMED"
        ))

        cursor.execute("""
            INSERT INTO warehouse_slots (
                slot_id, shipment_id, warehouse_id,
                scheduled_slot_time, max_buffer_minutes,
                missed_slot_penalty_inr, overtime_cost_per_hr, dock_bay, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "SLOT-1005", "SHP-1005", "WHS-BHIWANDI-A",
            (base_date + timedelta(hours=5, minutes=30)).isoformat(), 45.0, 12500.0, 1800.0, "BAY-7", "RESERVED"
        ))

    # Populate 1,200 cohort records if table count is low
    cursor.execute("SELECT COUNT(*) FROM shipments")
    count = cursor.fetchone()[0]
    if count < 50:
        random.seed(42)
        ports = ["Nhava Sheva (JNPT)", "Mundra Port", "Chennai Port", "Pipavav Port", "Kolkata Port"]
        hubs = ["Bhiwandi Hub", "Gurugram Logistics Park", "Sriperumbudur Mega Hub", "Bengaluru Whitefield Hub", "Ahmedabad Ring Hub"]
        base_date = datetime(2026, 10, 23, 8, 0, 0)

        for i in range(1, 1200):
            shipment_id = f"SHP-{1000 + i}"
            if shipment_id == "SHP-1005":
                continue

            port = random.choice(ports)
            hub = random.choice(hubs)
            historical_delay_rate = round(random.betavariate(2, 5), 3)
            port_congestion = round(random.betavariate(3, 3), 3)
            cargo_value = round(random.uniform(250000.0, 12000000.0), 2)
            noise = random.gauss(0, 1.2)
            simulated_delay = max(0.0, (historical_delay_rate * 4.0) + (port_congestion * 5.0) + noise)
            delay_hours = round(simulated_delay, 2)
            disruption_probability = 1 / (1 + 2.71828 ** -(
                -3.5 + 4.5 * historical_delay_rate + 3.8 * port_congestion + 0.65 * delay_hours
            ))
            is_delayed = 1 if random.random() < disruption_probability else 0

            random_day_offset = random.randint(-30, 10)
            berth_time = base_date + timedelta(days=random_day_offset, hours=random.randint(0, 12))
            pickup_time = berth_time + timedelta(hours=random.uniform(1.0, 2.5))
            transit_time = round(random.uniform(2.5, 7.0), 1)
            slot_time = pickup_time + timedelta(hours=transit_time + random.uniform(0.5, 1.5))
            promise_time = slot_time + timedelta(hours=random.uniform(2.0, 5.0))

            cursor.execute("""
                INSERT OR IGNORE INTO shipments (
                    shipment_id, origin_port, destination_hub, historical_delay_rate,
                    port_congestion_index, delay_hours, cargo_value_inr, is_delayed,
                    eta_port_berth, customer_promise_time, customer_name, sla_penalty_per_hour_inr, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                shipment_id, port, hub, historical_delay_rate,
                port_congestion, delay_hours, cargo_value, is_delayed,
                berth_time.isoformat(), promise_time.isoformat(),
                f"Client-{1000+i}", random.choice([2000.0, 2500.0, 3000.0, 4000.0]),
                (berth_time - timedelta(days=5)).isoformat()
            ))

            cursor.execute("""
                INSERT OR IGNORE INTO truck_bookings (
                    booking_id, shipment_id, driver_name, truck_number,
                    scheduled_pickup_time, max_driver_wait_hours_allowed,
                    driver_waiting_cost_per_hr, transit_time_hours, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"TRK-{1000+i}", shipment_id, f"Driver-{i}", f"IND-{random.randint(10,99)}-{random.randint(1000,9999)}",
                pickup_time.isoformat(), random.choice([1.5, 2.0, 2.5]), random.choice([400.0, 500.0, 600.0]),
                transit_time, "CONFIRMED"
            ))

            cursor.execute("""
                INSERT OR IGNORE INTO warehouse_slots (
                    slot_id, shipment_id, warehouse_id,
                    scheduled_slot_time, max_buffer_minutes,
                    missed_slot_penalty_inr, overtime_cost_per_hr, dock_bay, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"SLOT-{1000+i}", shipment_id, f"WHS-{hub.split()[0].upper()}",
                slot_time.isoformat(), random.choice([30.0, 45.0, 60.0]), random.choice([10000.0, 12500.0, 15000.0]),
                random.choice([1500.0, 1800.0, 2000.0]), f"BAY-{random.randint(1,12)}", "RESERVED"
            ))

    conn.commit()
    conn.close()


def init_db():
    """Initializes all database tables.

    Execution order is important:
    1. generate_data.main() runs first — it creates the unified 'shipments' table
       (telemetry schema with both ORM-compatible and cascade/risk-engine columns)
       along with 'truck_bookings' and 'warehouse_slots'. It uses DROP+CREATE so
       the schema is always correct, and populates SHP-1005 plus 1,200 cohort rows.
    2. Base.metadata.create_all() runs second — it creates ORM-only tables
       ('shipment_records', 'schedule_slots', 'disruptions', 'recovery_plans').
       Since 'shipments' is now 'shipment_records' in the ORM, there is no
       table-name conflict.
    3. ORM seed data (ScheduleSlotRecord entries) is inserted if absent.
    """
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    import generate_data

    # Step 1: Build telemetry tables with the correct unified schema
    db_path_str = str(DB_PATH)
    os.makedirs(os.path.dirname(db_path_str), exist_ok=True)
    conn = generate_data.init_db(db_path_str)
    generate_data.populate_data(conn)
    conn.close()
    print(f"Telemetry tables generated at: {db_path_str}")

    # Step 2: Create ORM-only tables (shipment_records, schedule_slots, etc.)
    Base.metadata.create_all(bind=engine)

    # Step 3: Seed ORM schedule_slots if absent
    db = SessionLocal()
    try:
        if db.query(ScheduleSlotRecord).count() == 0:
            now = datetime.utcnow()
            sample_slots = [
                ScheduleSlotRecord(
                    slot_id="PORT-JNPT-B1",
                    entity_type="PORT",
                    entity_name="JNPT Berth 1",
                    start_time=now + timedelta(hours=2),
                    end_time=now + timedelta(hours=6),
                    capacity=100,
                    cost_inr=5000.0
                ),
                ScheduleSlotRecord(
                    slot_id="TRUCK-FLEET-T10",
                    entity_type="CARRIER",
                    entity_name="BlueDart Heavy Freight",
                    start_time=now + timedelta(hours=6),
                    end_time=now + timedelta(hours=10),
                    capacity=1,
                    cost_inr=3500.0
                ),
                ScheduleSlotRecord(
                    slot_id="WH-BHIWANDI-D3",
                    entity_type="WAREHOUSE",
                    entity_name="Bhiwandi Bay 3",
                    start_time=now + timedelta(hours=10),
                    end_time=now + timedelta(hours=14),
                    capacity=1,
                    cost_inr=2500.0
                ),
            ]
            db.add_all(sample_slots)
            db.commit()
            print("ORM schedule slot records seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
