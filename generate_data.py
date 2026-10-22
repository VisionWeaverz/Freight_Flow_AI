"""Data generation script for FreightFlow AI.

Creates and populates `freightflow.db` SQLite database with:
- `shipments`: Historical and active shipment telemetry for risk modeling
- `truck_bookings`: Truck assignments and driver detention SLA contracts
- `warehouse_slots`: Dock appointment slots, SLA buffer limits, and penalty schedules

Generates test fixture 'SHP-1005' along with a diverse cohort of shipments.
"""

import sqlite3
import random
from datetime import datetime, timedelta
import os

DB_FILENAME = "freightflow.db"


def init_db(db_path: str = DB_FILENAME):
    """Initializes the database schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Drop existing tables to ensure clean slate
    cursor.execute("DROP TABLE IF EXISTS warehouse_slots")
    cursor.execute("DROP TABLE IF EXISTS truck_bookings")
    cursor.execute("DROP TABLE IF EXISTS shipments")

    # 1. Shipments Table
    cursor.execute("""
    CREATE TABLE shipments (
        shipment_id TEXT PRIMARY KEY,
        origin TEXT,
        destination TEXT,
        origin_port TEXT NOT NULL,
        destination_hub TEXT NOT NULL,
        cargo_type TEXT DEFAULT 'General Freight',
        value_inr REAL,
        cargo_value_inr REAL NOT NULL,
        planned_departure TEXT,
        planned_arrival TEXT,
        status TEXT DEFAULT 'SCHEDULED',
        historical_delay_rate REAL NOT NULL,
        port_congestion_index REAL NOT NULL,
        delay_hours REAL NOT NULL,
        is_delayed INTEGER NOT NULL,
        eta_port_berth TEXT NOT NULL,
        customer_promise_time TEXT NOT NULL,
        customer_name TEXT DEFAULT 'Enterprise Client',
        sla_penalty_per_hour_inr REAL DEFAULT 2500.0,
        created_at TEXT NOT NULL
    )
    """)

    # 2. Truck Bookings Table
    cursor.execute("""
    CREATE TABLE truck_bookings (
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

    # 3. Warehouse Slots Table
    cursor.execute("""
    CREATE TABLE warehouse_slots (
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

    conn.commit()
    return conn


def populate_data(conn: sqlite3.Connection, num_records: int = 1200):
    """Populates realistic synthetic data for ML training and graph analytics."""
    cursor = conn.cursor()
    random.seed(42)

    ports = ["Nhava Sheva (JNPT)", "Mundra Port", "Chennai Port", "Pipavav Port", "Kolkata Port"]
    hubs = ["Bhiwandi Hub", "Gurugram Logistics Park", "Sriperumbudur Mega Hub", "Bengaluru Whitefield Hub", "Ahmedabad Ring Hub"]

    base_date = datetime(2026, 10, 23, 8, 0, 0)

    # 1. Insert fixed anchor shipment: SHP-1005 (Mandatory for Unit Tests)
    shp_1005_berth = base_date
    shp_1005_pickup = base_date + timedelta(hours=1)       # 09:00:00
    transit_1005 = 3.5                                     # 3.5 hrs transit
    shp_1005_slot = base_date + timedelta(hours=5, minutes=30)  # 13:30:00
    shp_1005_promise = base_date + timedelta(hours=9)      # 17:00:00

    cursor.execute("""
        INSERT INTO shipments (
            shipment_id, origin, destination, origin_port, destination_hub,
            cargo_type, value_inr, cargo_value_inr, planned_departure, planned_arrival,
            status, historical_delay_rate, port_congestion_index, delay_hours,
            is_delayed, eta_port_berth, customer_promise_time, customer_name,
            sla_penalty_per_hour_inr, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "SHP-1005", "Nhava Sheva (JNPT)", "Bhiwandi Hub", "Nhava Sheva (JNPT)", "Bhiwandi Hub",
        "Electronics & Auto Components", 4500000.0, 4500000.0, shp_1005_berth.isoformat(),
        shp_1005_promise.isoformat(), "IN_TRANSIT", 0.32, 0.65, 0.0, 0,
        shp_1005_berth.isoformat(), shp_1005_promise.isoformat(),
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
        shp_1005_pickup.isoformat(), 2.0, 500.0, transit_1005, "CONFIRMED"
    ))

    cursor.execute("""
        INSERT INTO warehouse_slots (
            slot_id, shipment_id, warehouse_id,
            scheduled_slot_time, max_buffer_minutes,
            missed_slot_penalty_inr, overtime_cost_per_hr, dock_bay, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "SLOT-1005", "SHP-1005", "WHS-BHIWANDI-A",
        shp_1005_slot.isoformat(), 45.0, 12500.0, 1800.0, "BAY-7", "RESERVED"
    ))

    # 2. Insert cohort of training and test shipments
    for i in range(1, num_records + 1):
        shipment_id = f"SHP-{1000 + i}"
        if shipment_id == "SHP-1005":
            continue

        port = random.choice(ports)
        hub = random.choice(hubs)

        # Realistic feature relationships
        historical_delay_rate = round(random.betavariate(2, 5), 3)  # centered around ~0.28
        port_congestion = round(random.betavariate(3, 3), 3)        # centered around ~0.50
        cargo_value = round(random.uniform(250000.0, 12000000.0), 2)

        # Synthesize baseline delay hours with realistic physical drivers
        noise = random.gauss(0, 1.2)
        simulated_delay = max(0.0, (historical_delay_rate * 4.0) + (port_congestion * 5.0) + noise)
        delay_hours = round(simulated_delay, 2)

        # High severity disruption label logic
        # Disruption triggers when delay > 2.5 hrs OR combination of high congestion and rate
        disruption_probability = 1 / (1 + 2.71828 ** -(
            -3.5 + 4.5 * historical_delay_rate + 3.8 * port_congestion + 0.65 * delay_hours
        ))
        is_delayed = 1 if random.random() < disruption_probability else 0

        # Timeline logic
        random_day_offset = random.randint(-30, 10)
        berth_time = base_date + timedelta(days=random_day_offset, hours=random.randint(0, 12))
        pickup_time = berth_time + timedelta(hours=random.uniform(1.0, 2.5))
        transit_time = round(random.uniform(2.5, 7.0), 1)
        slot_time = pickup_time + timedelta(hours=transit_time + random.uniform(0.5, 1.5))
        promise_time = slot_time + timedelta(hours=random.uniform(2.0, 5.0))

        driver_wait_allowed = random.choice([1.5, 2.0, 2.5, 3.0])
        driver_rate = random.choice([400.0, 500.0, 600.0, 750.0])
        buffer_min = random.choice([30.0, 45.0, 60.0])
        missed_penalty = random.choice([8000.0, 10000.0, 12500.0, 15000.0, 20000.0])
        overtime_rate = random.choice([1200.0, 1500.0, 1800.0, 2200.0])

        cursor.execute("""
            INSERT INTO shipments (
                shipment_id, origin, destination, origin_port, destination_hub,
                cargo_type, value_inr, cargo_value_inr, planned_departure, planned_arrival,
                status, historical_delay_rate, port_congestion_index, delay_hours,
                is_delayed, eta_port_berth, customer_promise_time, customer_name,
                sla_penalty_per_hour_inr, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            shipment_id, port, hub, port, hub,
            "General Freight", cargo_value, cargo_value, berth_time.isoformat(),
            promise_time.isoformat(), "SCHEDULED", historical_delay_rate,
            port_congestion, delay_hours, is_delayed,
            berth_time.isoformat(), promise_time.isoformat(),
            f"Client-{1000+i}", random.choice([2000.0, 2500.0, 3000.0, 4000.0]),
            (berth_time - timedelta(days=5)).isoformat()
        ))

        cursor.execute("""
            INSERT INTO truck_bookings (
                booking_id, shipment_id, driver_name, truck_number,
                scheduled_pickup_time, max_driver_wait_hours_allowed,
                driver_waiting_cost_per_hr, transit_time_hours, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"TRK-{1000+i}", shipment_id, f"Driver-{i}", f"IND-{random.randint(10,99)}-{random.randint(1000,9999)}",
            pickup_time.isoformat(), driver_wait_allowed, driver_rate, transit_time, "CONFIRMED"
        ))

        cursor.execute("""
            INSERT INTO warehouse_slots (
                slot_id, shipment_id, warehouse_id,
                scheduled_slot_time, max_buffer_minutes,
                missed_slot_penalty_inr, overtime_cost_per_hr, dock_bay, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"SLOT-{1000+i}", shipment_id, f"WHS-{hub.split()[0].upper()}",
            slot_time.isoformat(), buffer_min, missed_penalty, overtime_rate, f"BAY-{random.randint(1,12)}", "RESERVED"
        ))

    conn.commit()
    print(f"Successfully populated {num_records} shipments, truck bookings, and warehouse slots into {DB_FILENAME}.")


def main():
    db_path = os.path.join(os.path.dirname(__file__), DB_FILENAME)
    print(f"Initializing database at: {db_path}")
    conn = init_db(db_path)
    populate_data(conn)
    conn.close()
    print("Database generation completed successfully.")


if __name__ == "__main__":
    main()
