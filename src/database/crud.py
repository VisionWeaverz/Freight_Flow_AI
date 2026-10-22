"""Data access helpers for shipments, schedules, and plans."""

from sqlalchemy.orm import Session
from src.database.models import ShipmentRecord, RecoveryPlanRecord, ScheduleSlotRecord


def get_all_shipments(db: Session):
    return db.query(ShipmentRecord).all()


def save_recovery_plan(db: Session, plan_record: RecoveryPlanRecord):
    db.add(plan_record)
    db.commit()
    db.refresh(plan_record)
    return plan_record


def mark_plan_approved(db: Session, plan_id: str):
    plan = db.query(RecoveryPlanRecord).filter(RecoveryPlanRecord.plan_id == plan_id).first()
    if plan:
        plan.is_approved = True
        db.commit()
    return plan
