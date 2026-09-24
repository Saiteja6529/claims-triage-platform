from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import asyncio
import json

from app.celery_worker import process_claim_async

app = FastAPI(
    title="Enterprise Claims Triage Platform - Production Engine",
    description="Real-time multi-agent claims automation platform with WebSockets and RAG."
)

class ClaimRequest(BaseModel):
    order_id: str
    claim_reason: str
    previous_claims_count: int = 0

@app.get("/")
def health_check():
    return {"status": "healthy", "mode": "production"}

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

# WebSockets Endpoint for Real-Time Live Status Pushing
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
        <h3 class="fw-bold text-white mb-4">Enterprise Claims Triage Live Console</h3>
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
                
                // Open real-time WebSocket connection
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