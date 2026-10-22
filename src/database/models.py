"""SQLAlchemy database models for shipments, slots, disruptions, and plans."""

from datetime import datetime

try:
    from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, JSON, ForeignKey
    from src.database.connection import Base
except ImportError:
    Column = String = Float = Integer = DateTime = Boolean = JSON = ForeignKey = None
    Base = object


class ShipmentRecord(Base):
    __tablename__ = "shipments"

    shipment_id = Column(String, primary_key=True, index=True) if Column else None
    origin = Column(String, nullable=False) if Column else None
    destination = Column(String, nullable=False) if Column else None
    cargo_type = Column(String) if Column else None
    value_inr = Column(Float, nullable=False) if Column else None
    planned_departure = Column(DateTime) if Column else None
    planned_arrival = Column(DateTime) if Column else None
    status = Column(String, default="SCHEDULED") if Column else None


class ScheduleSlotRecord(Base):
    __tablename__ = "schedule_slots"

    slot_id = Column(String, primary_key=True, index=True) if Column else None
    entity_type = Column(String) if Column else None  # PORT, CARRIER, WAREHOUSE
    entity_name = Column(String) if Column else None
    start_time = Column(DateTime) if Column else None
    end_time = Column(DateTime) if Column else None
    capacity = Column(Integer) if Column else None
    is_booked = Column(Boolean, default=False) if Column else None
    cost_inr = Column(Float) if Column else None


class DisruptionLogRecord(Base):
    __tablename__ = "disruptions"

    event_id = Column(String, primary_key=True, index=True) if Column else None
    event_type = Column(String) if Column else None
    source_entity = Column(String) if Column else None
    delay_hours = Column(Float) if Column else None
    severity = Column(Float) if Column else None
    created_at = Column(DateTime, default=datetime.utcnow) if Column else None
    description = Column(String) if Column else None


class RecoveryPlanRecord(Base):
    __tablename__ = "recovery_plans"

    plan_id = Column(String, primary_key=True, index=True) if Column else None
    disruption_id = Column(String) if Column else None
    plan_category = Column(String) if Column else None  # CHEAPEST, FASTEST, SAFEST
    carrier_slot_id = Column(String) if Column else None
    port_slot_id = Column(String) if Column else None
    warehouse_slot_id = Column(String) if Column else None
    total_cost_inr = Column(Float) if Column else None
    delay_hours = Column(Float) if Column else None
    reliability_score = Column(Float) if Column else None
    is_approved = Column(Boolean, default=False) if Column else None
    llm_explanation = Column(String) if Column else None
    created_at = Column(DateTime, default=datetime.utcnow) if Column else None
