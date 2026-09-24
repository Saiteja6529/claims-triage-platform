import hmac
import hashlib
import json
import requests
import structlog

logger = structlog.get_logger()

def dispatch_outbound_webhook(target_url: str, secret_token: str, event_type: str, payload: dict):
    """
    Dispatches a signed HMAC-SHA256 Webhook payload to an external merchant system.
    """
    try:
        body = json.dumps({"event": event_type, "data": payload})
        signature = hmac.new(
            secret_token.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Claims-Signature": signature
        }

        response = requests.post(target_url, data=body, headers=headers, timeout=5)
        logger.info("webhook_dispatched", url=target_url, status_code=response.status_code)
        return {"success": response.ok, "status_code": response.status_code}
    except Exception as e:
        logger.error("webhook_failed", url=target_url, error=str(e))
        return {"success": False, "error": str(e)}