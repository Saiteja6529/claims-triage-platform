from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from app.agents.policy_agent import verify_eligibility
from app.agents.risk_agent import assess_risk
from app.celery_worker import process_claim_async

app = FastAPI(
    title="Enterprise Async Claims Triage Platform",
    description="Event-Driven Multi-Agent Automation System using FastAPI, Celery, and Qdrant Vector RAG."
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

# 3. Interactive Web Dashboard Endpoint
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Claims Triage Operations Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            .card { border-radius: 12px; border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
            .badge-status { font-size: 0.9rem; padding: 6px 12px; }
            pre { background-color: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; max-height: 420px; }
        </style>
    </head>
    <body class="container py-5">
        <h2 class="fw-bold mb-4">Enterprise Claims Triage Live Dashboard</h2>
        
        <div class="row g-4">
            <!-- Submit Claim Form -->
            <div class="col-md-5">
                <div class="card p-4">
                    <h5 class="fw-bold mb-3">Submit Asynchronous Claim</h5>
                    <form id="claimForm">
                        <div class="mb-3">
                            <label class="form-label fw-semibold">Order ID</label>
                            <input type="text" id="orderId" class="form-control" value="ORDER101" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-semibold">Claim Reason</label>
                            <input type="text" id="claimReason" class="form-control" value="Damaged display panel" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-semibold">Previous Claims Count</label>
                            <input type="number" id="prevClaims" class="form-control" value="0" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100 fw-semibold">Dispatch Claim Event</button>
                    </form>
                </div>
            </div>

            <!-- Live Status & Execution Results -->
            <div class="col-md-7">
                <div class="card p-4">
                    <h5 class="fw-bold mb-3">Task Real-Time Monitor</h5>
                    <div id="statusContainer" class="mb-3" style="display:none;">
                        <span id="taskBadge" class="badge badge-status bg-warning text-dark">PROCESSING</span>
                        <small class="text-muted ms-2" id="taskIdDisplay"></small>
                    </div>
                    <pre id="resultOutput">Submit a claim request to observe live agent execution logs...</pre>
                </div>
            </div>
        </div>

        <script>
            document.getElementById('claimForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const output = document.getElementById('resultOutput');
                const container = document.getElementById('statusContainer');
                const badge = document.getElementById('taskBadge');
                const taskIdDisplay = document.getElementById('taskIdDisplay');

                output.textContent = "Dispatching event to Celery worker queue...";
                container.style.display = "block";
                badge.className = "badge badge-status bg-warning text-dark";
                badge.textContent = "DISPATCHING";

                try {
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
                    taskIdDisplay.textContent = `Task ID: ${taskId}`;
                    
                    // Poll for task status
                    const interval = setInterval(async () => {
                        const statusRes = await fetch(`/api/v2/task-status/${taskId}`);
                        const statusData = await statusRes.json();
                        
                        output.textContent = JSON.stringify(statusData, null, 2);
                        
                        if (statusData.status === "SUCCESS") {
                            clearInterval(interval);
                            badge.className = "badge badge-status bg-success";
                            badge.textContent = "SUCCESS";
                        }
                    }, 1000);

                } catch (err) {
                    output.textContent = "Error dispatching task: " + err;
                    badge.className = "badge badge-status bg-danger";
                    badge.textContent = "ERROR";
                }
            });
        </script>
    </body>
    </html>
    """