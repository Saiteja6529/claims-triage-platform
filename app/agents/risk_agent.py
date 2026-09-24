from app.telemetry import trace_agent_execution

@trace_agent_execution("fraud_risk_agent")
def assess_risk(customer_id: str, claim_amount: float, previous_claims_count: int):
    # Fraud Risk Scoring Heuristics
    risk_score = 0.10
    flags = []
    
    if previous_claims_count >= 3:
        risk_score += 0.50
        flags.append("High claim frequency detected")
        
    if claim_amount >= 150.0:
        risk_score += 0.30
        flags.append("High monetary value claim")
        
    risk_level = "HIGH" if risk_score >= 0.50 else "LOW"
    requires_human_review = risk_level == "HIGH"
    
    return {
        "risk_score": round(risk_score, 2),
        "risk_level": risk_level,
        "requires_human_review": requires_human_review,
        "flags": flags
    }