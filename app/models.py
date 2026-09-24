import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.db import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    api_keys = relationship("TenantApiKey", back_populates="tenant")
    claims = relationship("ClaimRecord", back_populates="tenant")

class TenantApiKey(Base):
    __tablename__ = "tenant_api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    hashed_key = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)

    tenant = relationship("Tenant", back_populates="api_keys")

class ClaimRecord(Base):
    __tablename__ = "claim_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True)
    order_id = Column(String, index=True)
    customer_id = Column(String)
    claim_reason = Column(Text)
    status = Column(String)
    final_decision = Column(String)
    risk_score = Column(Float)
    is_eligible = Column(Boolean)
    payment_action = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="claims")



class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    target_url = Column(String, nullable=False)
    secret_token = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    tenant = relationship("Tenant")