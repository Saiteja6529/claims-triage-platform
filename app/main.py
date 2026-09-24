from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.agents.policy_agent import verify_eligibility
from app.agents.risk_agent import assess_risk
from app.celery_worker import process_claim_async

app = FastAPI(
    title="Enterprise Async Claims Triage Platform",
    description="Event-Driven Multi-Agent Automation System using FastAPI, Celery, and Redis."
)

class ClaimRequest(BaseModel):
    order_id: str
    claim_reason: str
    previous_claims_count: int = 0

@app.get("/")
def health_check():
    return {"status": "healthy", "service": "Async Claims Triage Multi-Agent Platform"}

# 1. Asynchronous Dispatch Endpoint (Returns Task ID instantly)
@app.post("/api/v2/triage-claim-async")
def triage_claim_async(claim: ClaimRequest):
    task = process_claim_async.delay(
        claim.order_id,
        claim.claim_reason,
        claim.previous_claims_count
    )
    return {
        "message": "Claim evaluation task dispatched successfully.",
        "task_id": task.id,
        "status": "PROCESSING",
        "check_status_url": f"/api/v2/task-status/{task.id}"
    }

# 2. Task Status Tracking Endpoint
@app.get("/api/v2/task-status/{task_id}")
def get_task_status(task_id: str):
    task_result = process_claim_async.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else None
    }