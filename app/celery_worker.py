import time
from celery import Celery

from app.webhook_tool import send_human_review_alert
from app.agents.policy_agent import verify_eligibility
from app.agents.risk_agent import assess_risk
from app.payment_tool import execute_stripe_refund

celery_app = Celery(
    "claims_worker",
    broker="sqla+sqlite:///celerydb.sqlite",
    backend="db+sqlite:///results.sqlite"
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(name="process_claim_async", bind=True, max_retries=3)
def process_claim_async(self, order_id: str, claim_reason: str, previous_claims_count: int):
    try:
        time.sleep(1)
        
        # Agent 1: Policy Verification via Qdrant RAG
        policy_res = verify_eligibility(order_id, claim_reason)
        
        if not policy_res["found"]:
            return {
                "order_id": order_id,
                "status": "FAILED",
                "reason": policy_res["reason"]
            }
        
        # Agent 2: Fraud & Risk Assessment
        risk_res = assess_risk(
            customer_id=policy_res["customer_id"],
            claim_amount=policy_res["amount"],
            previous_claims_count=previous_claims_count
        )
        
        # Multi-Agent Workflow Decision Logic
        if not policy_res["is_eligible"]:
            decision = "CLAIM_REJECTED"
            status_code = "POLICY_EXPIRED"
            payment_action = {"executed": False, "reason": "Claim ineligible."}
        elif risk_res["requires_human_review"]:
            decision = "HUMAN_REVIEW_REQUIRED"
            status_code = "FLAGGED_FOR_AUDIT"
            
            # AUTOMATED SLACK ALERT TOOL EXECUTION
            alert_action = send_human_review_alert(
                order_id=order_id,
                customer_id=policy_res["customer_id"],
                risk_score=risk_res["risk_score"],
                flags=risk_res.get("flags", [])
            )
            payment_action = {
                "executed": False, 
                "reason": "Flagged for human audit.", 
                "slack_notification": alert_action
            }
        else:
            decision = "AUTOMATED_REFUND_APPROVED"
            status_code = "APPROVED"
            
            # AUTOMATED TOOL EXECUTION: Trigger Stripe Refund
            payment_action = execute_stripe_refund(
                order_id=order_id,
                amount=policy_res["amount"],
                customer_id=policy_res["customer_id"]
            )
            
        return {
            "order_id": order_id,
            "customer_id": policy_res["customer_id"],
            "final_decision": decision,
            "status_code": status_code,
            "payment_action": payment_action,
            "agent_outputs": {
                "policy_agent": policy_res,
                "risk_agent": risk_res
            }
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)