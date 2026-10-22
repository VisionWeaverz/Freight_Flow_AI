"""Seed script to populate SQLite with initial mock supply chain records."""

from datetime import datetime, timedelta
from src.database.connection import engine, Base, SessionLocal
from src.database.models import ShipmentRecord, ScheduleSlotRecord


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(ShipmentRecord).count() == 0:
        now = datetime.utcnow()
        sample_shipment = ShipmentRecord(
            shipment_id="SHP-IN-9081",
            origin="Jawaharlal Nehru Port (JNPT)",
            destination="Bhiwandi Central Fulfillment Hub",
            cargo_type="Electronics & Automotive Components",
            value_inr=4500000.0,
            planned_departure=now + timedelta(hours=2),
            planned_arrival=now + timedelta(hours=10),
            status="IN_TRANSIT"
        )
        db.add(sample_shipment)

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
            )
        ]
        db.add_all(sample_slots)
        db.commit()
        print("Database initialized with seed supply chain records.")
    else:
        print("Database already contains records.")
    db.close()


if __name__ == "__main__":
    init_db()
