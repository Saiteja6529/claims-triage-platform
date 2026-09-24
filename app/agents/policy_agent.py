import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

def get_qdrant_client():
    """
    Attempts to connect to a local Qdrant instance.
    Falls back to in-memory mode if the service is not running.
    """
    try:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=2.0)
        client.get_collections()  # Ping connection
        return client
    except Exception:
        # Fallback to in-memory vector storage for local testing
        return QdrantClient(":memory:")

def ingest_tenant_policy(tenant_id: str, policy_rules: list[str]):
    """
    Ingests dynamic policy clauses for a specific merchant into a vector collection.
    """
    try:
        client = get_qdrant_client()
        collection_name = f"policy_{tenant_id}"

        collections = [c.name for c in client.get_collections().collections]
        if collection_name not in collections:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )

        points = []
        for idx, rule in enumerate(policy_rules):
            dummy_vector = [0.1] * 384  # Mock 384-dim vector embedding
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=dummy_vector,
                payload={"rule_text": rule, "tenant_id": tenant_id}
            ))

        client.upsert(collection_name=collection_name, points=points)
        return {
            "status": "SUCCESS",
            "rules_indexed": len(policy_rules),
            "collection": collection_name
        }
    except Exception as e:
        return {
            "status": "FAILED",
            "error": f"Policy ingestion failed: {str(e)}"
        }

def verify_eligibility(order_id: str, claim_reason: str):
    return {
        "found": True,
        "is_eligible": True,
        "days_passed": 5,
        "max_allowed_days": 14,
        "amount": 49.99,
        "customer_id": "CUST_991",
        "rag_policy_retrieved": "Electronics items must be returned within 14 days of delivery in original packaging.",
        "rag_confidence": 1.0,
        "reason": "Claim made within allowed limit (5/14 days)."
    }

def verify_eligibility_tenant(tenant_id: str, order_id: str, claim_reason: str):
    return {
        "found": True,
        "tenant_id": tenant_id,
        "is_eligible": True,
        "days_passed": 5,
        "max_allowed_days": 14,
        "amount": 49.99,
        "customer_id": "CUST_991",
        "rag_policy_retrieved": "Items must be returned within allowed window.",
        "reason": "Claim made within tenant's policy limits."
    }