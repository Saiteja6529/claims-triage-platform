import pytest
from app.agents.policy_agent import verify_eligibility
from app.agents.risk_agent import assess_risk
from app.rag_service import search_policy_vector

def test_policy_agent_valid_order():
    """Test Policy Agent with an eligible order within return window."""
    result = verify_eligibility("ORDER101", "Damaged product")
    assert result["found"] is True
    assert result["is_eligible"] is True
    assert result["days_passed"] <= result["max_allowed_days"]

def test_policy_agent_expired_order():
    """Test Policy Agent with an order exceeding return window."""
    result = verify_eligibility("ORDER102", "Late return")
    assert result["found"] is True
    assert result["is_eligible"] is False

def test_policy_agent_invalid_order():
    """Test Policy Agent handling non-existent orders gracefully."""
    result = verify_eligibility("NON_EXISTENT_ORDER", "Damaged")
    assert result["found"] is False
    assert result["is_eligible"] is False

def test_risk_agent_low_risk():
    """Test Risk Agent scoring for low monetary, low frequency claims."""
    risk = assess_risk("CUST_991", claim_amount=49.99, previous_claims_count=0)
    assert risk["risk_level"] == "LOW"
    assert risk["requires_human_review"] is False

def test_risk_agent_high_risk_frequency():
    """Test Risk Agent flagging accounts with high dispute frequency."""
    risk = assess_risk("CUST_991", claim_amount=49.99, previous_claims_count=4)
    assert risk["risk_level"] == "HIGH"
    assert risk["requires_human_review"] is True

def test_rag_vector_search():
    """Test Qdrant RAG semantic vector lookup."""
    rag_res = search_policy_vector("Electronics")
    assert "Electronics" in rag_res["retrieved_policy"] or rag_res["confidence_score"] > 0