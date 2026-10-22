"""Tests for database tables, models, and CRUD operations."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.connection import Base
from src.database.models import ShipmentRecord, RecoveryPlanRecord
from src.database.crud import save_recovery_plan, mark_plan_approved

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_database_crud():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    plan = RecoveryPlanRecord(
        plan_id="TEST-PLAN-01",
        disruption_id="EVT-01",
        plan_category="CHEAPEST",
        carrier_slot_id="SLOT-1",
        port_slot_id="PORT-1",
        warehouse_slot_id="WH-1",
        total_cost_inr=5000.0,
        delay_hours=1.5,
        reliability_score=0.9
    )
    saved = save_recovery_plan(db, plan)
    assert saved.plan_id == "TEST-PLAN-01"

    approved = mark_plan_approved(db, "TEST-PLAN-01")
    assert approved.is_approved is True
    db.close()
