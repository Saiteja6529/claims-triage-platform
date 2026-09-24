from sqlalchemy import Column, String, Float, Boolean, DateTime, JSON
from datetime import datetime
from app.db import Base

class ClaimRecord(Base):
    __tablename__ = "claims"

    id = Column(String, primary_key=True, index=True)  # Task / Claim ID
    order_id = Column(String, index=True)
    customer_id = Column(String, index=True)
    claim_reason = Column(String)
    status = Column(String)  # PROCESSING, APPROVED, REJECTED, FLAGGED_FOR_AUDIT
    final_decision = Column(String)
    risk_score = Column(Float)
    is_eligible = Column(Boolean)
    audit_notes = Column(String, nullable=True)
    payment_action = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)