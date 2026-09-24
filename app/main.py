import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.celery_worker import process_claim_async
from app.db import get_db, engine, Base
from app.models import ClaimRecord
from app.payment_tool import execute_stripe_refund

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Enterprise Claims Triage Platform - Production Engine",
    description="Real-time multi-agent claims automation platform with WebSockets, RAG, and Human-in-the-Loop audit controls."
)

class ClaimRequest(BaseModel):
    order_id: str
    claim_reason: str
    previous_claims_count: int = 0

@app.get("/")
def health_check():
    return {"status": "healthy", "mode": "production"}

# 1. Asynchronous Dispatch Endpoint
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

# 2. WebSockets Endpoint for Real-Time Status Streaming
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

# 3. Admin API: Query Flagged Audit Claims
@app.get("/api/v2/admin/pending-claims")
def get_pending_claims(db: Session = Depends(get_db)):
    return db.query(ClaimRecord).filter(ClaimRecord.status == "FLAGGED_FOR_AUDIT").all()

# 4. Admin API: Manually Resolve Flagged Claim
@app.post("/api/v2/admin/resolve-claim/{claim_id}")
def resolve_claim(claim_id: str, action: str, db: Session = Depends(get_db)):
    claim = db.query(ClaimRecord).filter(ClaimRecord.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim record not found")
    
    if action.upper() == "APPROVE":
        claim.status = "APPROVED"
        claim.final_decision = "MANUALLY_APPROVED_BY_ADMIN"
        
        # Execute refund on manual approval
        payment_res = execute_stripe_refund(
            order_id=claim.order_id,
            amount=49.99,
            customer_id=claim.customer_id
        )
        claim.payment_action = payment_res
    else:
        claim.status = "REJECTED"
        claim.final_decision = "MANUALLY_REJECTED_BY_ADMIN"
        claim.payment_action = {"executed": False, "reason": "Rejected by human auditor."}
        
    db.commit()
    return {"status": "SUCCESS", "claim_id": claim_id, "new_status": claim.status}

# 5. User Console UI Route
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Enterprise Claims Triage Live Console</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', system-ui, sans-serif; }
            .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }
            pre { background-color: #010409; color: #7ee787; border: 1px solid #30363d; padding: 15px; border-radius: 6px; }
            .btn-primary { background-color: #238636; border-color: #238636; }
            .btn-primary:hover { background-color: #2ea043; }
        </style>
    </head>
    <body class="container py-5">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h3 class="fw-bold text-white mb-0">Enterprise Claims Triage Live Console</h3>
            <a href="/admin" class="btn btn-outline-info btn-sm">Switch to Admin Workspace &rarr;</a>
        </div>
        <div class="row g-4">
            <div class="col-md-5">
                <div class="card p-4">
                    <h5 class="fw-bold text-white mb-3">Submit Asynchronous Claim</h5>
                    <form id="claimForm">
                        <div class="mb-3">
                            <label class="form-label text-secondary">Order ID</label>
                            <input type="text" id="orderId" class="form-control bg-dark text-white border-secondary" value="ORDER101" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label text-secondary">Claim Reason</label>
                            <input type="text" id="claimReason" class="form-control bg-dark text-white border-secondary" value="Damaged display panel" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label text-secondary">Previous Claims Count</label>
                            <input type="number" id="prevClaims" class="form-control bg-dark text-white border-secondary" value="0" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100 fw-semibold">Dispatch Claim Event</button>
                    </form>
                </div>
            </div>
            <div class="col-md-7">
                <div class="card p-4">
                    <h5 class="fw-bold text-white mb-3">WebSocket Event Stream</h5>
                    <div id="statusBadge" class="badge bg-secondary mb-2" style="width: fit-content;">IDLE</div>
                    <pre id="resultOutput">Submit a claim to establish real-time WebSocket connection...</pre>
                </div>
            </div>
        </div>
        <script>
            document.getElementById('claimForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const output = document.getElementById('resultOutput');
                const badge = document.getElementById('statusBadge');
                
                output.textContent = "Dispatching claim payload to API gateway...";
                badge.className = "badge bg-warning text-dark";
                badge.textContent = "DISPATCHING";

                const response = await fetch('/api/v2/triage-claim-async', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        order_id: document.getElementById('orderId').value,
                        claim_reason: document.getElementById('claimReason').value,
                        previous_claims_count: parseInt(document.getElementById('prevClaims').value)
                    })
                });
                
                const data = await response.json();
                const taskId = data.task_id;
                
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const ws = new WebSocket(`${protocol}//${window.location.host}/ws/task-status/${taskId}`);
                
                ws.onmessage = (event) => {
                    const statusData = JSON.parse(event.data);
                    output.textContent = JSON.stringify(statusData, null, 2);
                    badge.textContent = statusData.status;
                    
                    if (statusData.status === "SUCCESS") {
                        badge.className = "badge bg-success";
                        ws.close();
                    }
                };
            });
        </script>
    </body>
    </html>
    """

# 6. Admin Approval UI Route
@app.get("/admin", response_class=HTMLResponse)
async def serve_admin_console():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Claims Audit - Admin Workspace</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', system-ui, sans-serif; }
            .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }
            .table-dark { background-color: #161b22; color: #c9d1d9; }
        </style>
    </head>
    <body class="container py-5">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h3 class="fw-bold text-white mb-0">Human Auditor Queue (`FLAGGED_FOR_AUDIT`)</h3>
            <div>
                <a href="/dashboard" class="btn btn-outline-secondary btn-sm me-2">&larr; Live Console</a>
                <button onclick="loadPendingClaims()" class="btn btn-outline-info btn-sm">Refresh List</button>
            </div>
        </div>
        
        <div class="card p-3">
            <div class="table-responsive">
                <table class="table table-dark align-middle mb-0">
                    <thead>
                        <tr>
                            <th>Claim ID</th>
                            <th>Order ID</th>
                            <th>Customer ID</th>
                            <th>Reason</th>
                            <th>Risk Score</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="claimsTableBody">
                        <tr><td colspan="6" class="text-muted text-center py-4">Loading pending claims...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            async function loadPendingClaims() {
                const res = await fetch('/api/v2/admin/pending-claims');
                const claims = await res.json();
                const tbody = document.getElementById('claimsTableBody');
                
                if (!claims || claims.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-success py-4">No pending claims requiring human review.</td></tr>';
                    return;
                }
                
                tbody.innerHTML = claims.map(c => `
                    <tr>
                        <td><code>${c.id.substring(0, 8)}...</code></td>
                        <td>${c.order_id}</td>
                        <td>${c.customer_id}</td>
                        <td>${c.claim_reason}</td>
                        <td><span class="badge bg-danger">${c.risk_score}</span></td>
                        <td>
                            <button onclick="resolveClaim('${c.id}', 'APPROVE')" class="btn btn-sm btn-success me-2">Approve Refund</button>
                            <button onclick="resolveClaim('${c.id}', 'REJECT')" class="btn btn-sm btn-danger">Reject</button>
                        </td>
                    </tr>
                `).join('');
            }

            async function resolveClaim(claimId, action) {
                if(!confirm(`Are you sure you want to ${action} claim ${claimId}?`)) return;
                
                await fetch(`/api/v2/admin/resolve-claim/${claimId}?action=${action}`, { method: 'POST' });
                loadPendingClaims();
            }

            loadPendingClaims();
        </script>
    </body>
    </html>
    """