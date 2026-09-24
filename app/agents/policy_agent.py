from app.database.mock_db import get_order
from app.rag_service import search_policy_vector

def verify_eligibility(order_id: str, claim_reason: str):
    order = get_order(order_id)
    if not order:
        return {
            "found": False,
            "is_eligible": False,
            "reason": f"Order ID {order_id} not found in system.",
            "amount": 0.0,
            "customer_id": None
        }
    
    # Perform RAG Vector Search over Qdrant Policy Index
    rag_result = search_policy_vector(order["category"])
    
    days_passed = order["days_ago"]
    max_allowed = rag_result["max_allowed_days"]
    
    if days_passed <= max_allowed:
        return {
            "found": True,
            "is_eligible": True,
            "days_passed": days_passed,
            "max_allowed_days": max_allowed,
            "amount": order["amount"],
            "customer_id": order["customer_id"],
            "rag_policy_retrieved": rag_result["retrieved_policy"],
            "rag_confidence": rag_result["confidence_score"],
            "reason": f"Claim made within allowed limit ({days_passed}/{max_allowed} days)."
        }
    else:
        return {
            "found": True,
            "is_eligible": False,
            "days_passed": days_passed,
            "max_allowed_days": max_allowed,
            "amount": order["amount"],
            "customer_id": order["customer_id"],
            "rag_policy_retrieved": rag_result["retrieved_policy"],
            "rag_confidence": rag_result["confidence_score"],
            "reason": f"Claim window expired ({days_passed} days passed, max allowed is {max_allowed} days)."
        }