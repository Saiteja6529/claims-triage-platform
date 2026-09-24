import time
from celery import Celery
from dotenv import load_dotenv

load_dotenv()  # Automatically loads variables from .env into os.environ

from app.webhook_tool import send_human_review_alert
from app.agents.policy_agent import verify_eligibility
from app.agents.risk_agent import assess_risk
from app.payment_tool import execute_stripe_refund
from app.db import SessionLocal
from app.models import ClaimRecord, WebhookConfig
from app.webhook_engine import dispatch_outbound_webhook

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

@celery_app.task(bind=True, name="process_claim_async")
def process_claim_async(self, order_id: str, claim_reason: str, previous_claims_count: int = 0, tenant_id: str = None):
    try:
        # Agent 1: Policy Verification
        policy_res = verify_eligibility(order_id, claim_reason)

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
            
        # PERSIST TO DATABASE FOR ADMIN AUDIT TRAIL
        _save_to_db(
            task_id=self.request.id,
            order_id=order_id,
            customer_id=policy_res["customer_id"],
            claim_reason=claim_reason,
            status=status_code,
            final_decision=decision,
            risk_score=risk_res["risk_score"],
            is_eligible=policy_res["is_eligible"],
            payment_action=payment_action,
            tenant_id=tenant_id
        )

        result = {
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

        # DISPATCH OUTBOUND WEBHOOK TO MERCHANT SYSTEM
        if tenant_id:
            db = SessionLocal()
            try:
                webhook = db.query(WebhookConfig).filter(
                    WebhookConfig.tenant_id == tenant_id,
                    WebhookConfig.is_active == True
                ).first()
                
                if webhook:
                    event_type = f"CLAIM.{status_code}"
                    dispatch_outbound_webhook(
                        target_url=webhook.target_url,
                        secret_token=webhook.secret_token,
                        event_type=event_type,
                        payload=result
                    )
            except Exception as w_err:
                print(f"Webhook dispatch error: {w_err}")
            finally:
                db.close()

        return result

    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)

def _save_to_db(task_id: str, order_id: str, customer_id: str, claim_reason: str, 
                status: str, final_decision: str, risk_score: float, is_eligible: bool, 
                payment_action: dict, tenant_id: str = None):
    """Helper function to log claim execution history into database."""
    db = SessionLocal()
    try:
        record = ClaimRecord(
            id=task_id,
            tenant_id=tenant_id,
            order_id=order_id,
            customer_id=customer_id,
            claim_reason=claim_reason,
            status=status,
            final_decision=final_decision,
            risk_score=risk_score,
            is_eligible=is_eligible,
            payment_action=payment_action
        )
        db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Database logging error: {e}")
    finally:
        db.close()