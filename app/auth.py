from fastapi import Security, HTTPException, status, Depends
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
import hashlib
from app.db import get_db
from app.models import TenantApiKey, Tenant

API_KEY_HEADER = APIKeyHeader(name="x-api-key", auto_error=False)

def get_current_tenant(api_key: str = Security(API_KEY_HEADER), db: Session = Depends(get_db)) -> Tenant:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing 'x-api-key' header."
        )
    
    hashed_input = hashlib.sha256(api_key.encode()).hexdigest()
    key_record = db.query(TenantApiKey).filter(
        TenantApiKey.hashed_key == hashed_input,
        TenantApiKey.is_active == True
    ).first()

    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API Key."
        )

    return key_record.tenant