from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import numpy as np

# Initialize local in-memory Qdrant instance
qdrant = QdrantClient(":memory:")
COLLECTION_NAME = "return_policies"

# Initialize vector collection
# Modern Qdrant collection initialization
if qdrant.collection_exists(COLLECTION_NAME):
    qdrant.delete_collection(COLLECTION_NAME)

qdrant.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=4, distance=Distance.COSINE),
)
# Seed vector collection with policy documents
# Note: Simple normalized 4D mock vectors for fast CPU execution
documents = [
    {
        "id": 1,
        "vector": [0.1, 0.8, 0.1, 0.0],
        "category": "Electronics",
        "policy_text": "Electronics items must be returned within 14 days of delivery in original packaging.",
        "max_days": 14
    },
    {
        "id": 2,
        "vector": [0.8, 0.1, 0.1, 0.0],
        "category": "Apparel",
        "policy_text": "Apparel and clothing items have a 30-day return window if unwashed and unworn.",
        "max_days": 30
    }
]

qdrant.upsert(
    collection_name=COLLECTION_NAME,
    points=[
        PointStruct(
            id=doc["id"],
            vector=doc["vector"],
            payload={"category": doc["category"], "text": doc["policy_text"], "max_days": doc["max_days"]}
        )
        for doc in documents
    ]
)

def search_policy_vector(category: str):
    """
    Simulates vector semantic search over indexed policy documents using Qdrant.
    """
    query_vector = [0.1, 0.8, 0.1, 0.0] if category == "Electronics" else [0.8, 0.1, 0.1, 0.0]
    
    search_result = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=1
    )
    
    if search_result.points:
        top_match = search_result.points[0].payload
        return {
            "retrieved_policy": top_match["text"],
            "max_allowed_days": top_match["max_days"],
            "confidence_score": round(search_result.points[0].score, 2)
        }
    return {
        "retrieved_policy": "Default standard 30-day policy applies.",
        "max_allowed_days": 30,
        "confidence_score": 0.50
    }