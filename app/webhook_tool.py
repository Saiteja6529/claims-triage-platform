import os
import requests

# Retrieve webhook URL safely from environment variables
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

def send_human_review_alert(order_id: str, customer_id: str, risk_score: float, flags: list, webhook_url: str = None):
    """
    Sends an automated notification alert to a Slack webhook endpoint
    when a claim triggers HUMAN_REVIEW_REQUIRED.
    """
    target_url = webhook_url or SLACK_WEBHOOK_URL
    
    payload = {
        "text": f"🚨 *HUMAN REVIEW REQUIRED* 🚨\n"
                f"*Order ID:* `{order_id}`\n"
                f"*Customer ID:* `{customer_id}`\n"
                f"*Risk Score:* `{risk_score}`\n"
                f"*Flags:* {', '.join(flags) if flags else 'High dispute frequency'}\n"
                f"*Action:* Manual audit required in admin dashboard."
    }
    
    if target_url:
        try:
            response = requests.post(target_url, json=payload, timeout=5)
            return {
                "success": response.status_code == 200,
                "status": "Live Slack alert dispatched",
                "http_status_code": response.status_code
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    return {
        "success": True,
        "status": "Mock alert triggered",
        "payload_sent": payload
    }