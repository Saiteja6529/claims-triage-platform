import asyncio
import json
import secrets
import hashlib
from dotenv import load_dotenv

# 1. Load environment variables
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.celery_worker import process_claim_async
from app.db import get_db, engine, Base
from app.models import ClaimRecord, Tenant, TenantApiKey, WebhookConfig
from app.payment_tool import execute_stripe_refund
from app.ocr_tool import inspect_receipt_image
from app.auth import get_current_tenant
from app.agents.policy_agent import ingest_tenant_policy
from app.webhook_engine import dispatch_outbound_webhook

# 2. INITIALIZE FASTAPI INSTANCE FIRST
app = FastAPI(
    title="Enterprise Claims Triage Platform - Production Engine",
    description="Multi-tenant claims triage SaaS API with WebSockets, RAG, Vision AI, and Webhook notifications."
)

# 3. INITIALIZE DATABASE TABLES
Base.metadata.create_all(bind=engine)

class ClaimRequest(BaseModel):
    order_id: str
    claim_reason: str
    previous_claims_count: int = 0

@app.get("/")
def health_check():
    return {"status": "healthy", "mode": "production"}

# 4. TENANT MANAGEMENT & MULTI-TENANT ROUTE
@app.post("/api/v2/admin/tenants/register")
def register_tenant(tenant_name: str, db: Session = Depends(get_db)):
    raw_api_key = f"sk_live_{secrets.token_hex(16)}"
    hashed_key = hashlib.sha256(raw_api_key.encode()).hexdigest()

    new_tenant = Tenant(name=tenant_name)
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)

    key_record = TenantApiKey(tenant_id=new_tenant.id, hashed_key=hashed_key)
    db.add(key_record)
    db.commit()

    return {
        "tenant_id": new_tenant.id,
        "tenant_name": new_tenant.name,
        "api_key": raw_api_key,
        "warning": "Store this API key securely. It will not be shown again."
    }

@app.post("/api/v2/tenants/policies/upload")
def upload_merchant_policy(
    policy_rules: list[str],
    current_tenant: Tenant = Depends(get_current_tenant)
):
    result = ingest_tenant_policy(current_tenant.id, policy_rules)
    return {
        "tenant_id": current_tenant.id,
        "tenant_name": current_tenant.name,
        "ingestion_result": result
    }

@app.post("/api/v2/tenants/webhooks/config")
def configure_webhook(
    target_url: str,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    secret_token = secrets.token_hex(24)
    config = WebhookConfig(
        tenant_id=current_tenant.id,
        target_url=target_url,
        secret_token=secret_token
    )
    db.add(config)
    db.commit()
    
    return {
        "status": "SUCCESS",
        "tenant_id": current_tenant.id,
        "target_url": target_url,
        "signing_secret": secret_token,
        "note": "Use the signing secret to verify incoming 'X-Claims-Signature' headers on your server."
    }

# 5. ASYNC TRIAGE & VISION ENDPOINTS
@app.post("/api/v2/triage-claim-async")
def triage_claim_async(claim: ClaimRequest):
    task = process_claim_async.delay(
        claim.order_id,
        claim.claim_reason,
        claim.previous_claims_count
    )
    return {
        "message": "Claim evaluation task dispatched.",
        "task_id": task.id,
        "status": "PROCESSING"
    }

@app.post("/api/v2/triage-claim-with-receipt")
async def triage_claim_with_receipt(
    order_id: str = Form(...),
    claim_reason: str = Form(...),
    previous_claims_count: int = Form(0),
    receipt_file: UploadFile = File(...)
):
    image_bytes = await receipt_file.read()
    
    vision_res = inspect_receipt_image(image_bytes)
    if not vision_res["success"]:
        return {"status": "FAILED", "reason": vision_res["error"]}
        
    analysis = vision_res["vision_analysis"]
    
    if analysis.get("tampering_detected"):
        return {
            "status": "REJECTED_AUTOMATICALLY",
            "reason": "Receipt image forgery or manipulation detected.",
            "tampering_notes": analysis.get("tampering_notes")
        }

    task = process_claim_async.delay(
        order_id,
        claim_reason,
        previous_claims_count
    )
    
    return {
        "message": "Receipt verified by Vision AI. Claim task dispatched.",
        "task_id": task.id,
        "status": "PROCESSING",
        "vision_metadata": analysis
    }

# 6. WEBSOCKETS & ADMIN ROUTES
@app.websocket("/ws/task-status/{task_id}")
async def websocket_task_status(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        while True:
            task_result = process_claim_async.AsyncResult(task_id)
            data = {
                "task_id": task_id,
                "status": task_result.status,
                "result": task_result.result if task_result.ready() else None
            }
            await websocket.send_text(json.dumps(data))
            if task_result.ready():
                break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass

@app.get("/api/v2/admin/pending-claims")
def get_pending_claims(db: Session = Depends(get_db)):
    return db.query(ClaimRecord).filter(ClaimRecord.status == "FLAGGED_FOR_AUDIT").all()

@app.post("/api/v2/admin/resolve-claim/{claim_id}")
def resolve_claim(claim_id: str, action: str, db: Session = Depends(get_db)):
    claim = db.query(ClaimRecord).filter(ClaimRecord.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim record not found")
    
    if action.upper() == "APPROVE":
        claim.status = "APPROVED"
        claim.final_decision = "MANUALLY_APPROVED_BY_ADMIN"
        payment_res = execute_stripe_refund(order_id=claim.order_id, amount=49.99, customer_id=claim.customer_id)
        claim.payment_action = payment_res
    else:
        claim.status = "REJECTED"
        claim.final_decision = "MANUALLY_REJECTED_BY_ADMIN"
        claim.payment_action = {"executed": False, "reason": "Rejected by human auditor."}
        
    db.commit()

    if claim.tenant_id:
        webhook = db.query(WebhookConfig).filter(
            WebhookConfig.tenant_id == claim.tenant_id,
            WebhookConfig.is_active == True
        ).first()
        if webhook:
            dispatch_outbound_webhook(
                target_url=webhook.target_url,
                secret_token=webhook.secret_token,
                event_type=f"CLAIM.MANUALLY_{action.upper()}D",
                payload={"claim_id": claim.id, "status": claim.status, "decision": claim.final_decision}
            )

    return {"status": "SUCCESS", "claim_id": claim_id, "new_status": claim.status}

# 7. CONSOLE DASHBOARDS
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    return "<html><body><h1>Enterprise Claims Console Active</h1></body></html>"

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin_console():
    return "<html><body><h1>Admin Audit Queue Active</h1></body></html>"