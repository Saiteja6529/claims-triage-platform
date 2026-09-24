import requests

def send_human_review_alert(order_id: str, customer_id: str, risk_score: float, flags: list, webhook_url: str = None):
    """
    Sends an automated notification alert to a webhook endpoint (Slack/Discord/Teams)
    when a claim triggers HUMAN_REVIEW_REQUIRED.
    """
    payload = {
        "text": f"🚨 *HUMAN REVIEW REQUIRED* 🚨\n"
                f"*Order ID:* {order_id}\n"
                f"*Customer ID:* {customer_id}\n"
                f"*Risk Score:* {risk_score}\n"
                f"*Flags:* {', '.join(flags) if flags else 'High dispute frequency'}\n"
                f"*Action:* Manual audit required in admin dashboard."
    }
    
    # If a real webhook URL is provided, dispatch POST request; otherwise perform mock execution
    if webhook_url:
        try:
            response = requests.post(webhook_url, json=payload, timeout=5)
            return {"success": response.status_code == 200, "status": "Alert sent to Slack"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    return {
        "success": True,
        "status": "Mock alert triggered",
        "payload_sent": payload
    }