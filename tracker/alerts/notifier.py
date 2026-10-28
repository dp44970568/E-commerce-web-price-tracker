import logging
import requests
from typing import Dict, Any, List, Optional
from tracker.config import ALERT_WEBHOOK_URL

logger = logging.getLogger(__name__)


class Notifier:
    """
    Dispatches alerts when target price thresholds are met or drops occur.
    Supports local logging as well as webhook notifications (Discord, Slack, or generic HTTP POST).
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or ALERT_WEBHOOK_URL

    def send_webhook(self, title: str, message: str, payload_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Sends an HTTP POST notification to a configured webhook URL.
        Compatible with Discord, Slack, and generic webhooks.
        """
        if not self.webhook_url:
            return False

        payload = {
            "content": f"**{title}**\n{message}",
            "text": f"*{title}*\n{message}",
            "title": title,
            "message": message,
            "data": payload_data or {},
        }

        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=5)
            if resp.status_code in (200, 204):
                logger.info("Successfully dispatched webhook notification.")
                return True
            else:
                logger.warning(f"Webhook returned status code {resp.status_code}: {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"Failed to deliver webhook notification: {e}")
            return False

    def notify_alert(self, alert_data: Dict[str, Any]) -> str:
        """Format, log, and dispatch a triggered price threshold alert."""
        target_name = alert_data.get("target_name", "Item")
        current_price = alert_data.get("latest_price", 0.0)
        target_price = alert_data.get("target_price", 0.0)
        currency = alert_data.get("currency", "USD")
        item_type = alert_data.get("target_type", "item").upper()
        savings = max(0.0, target_price - current_price)

        msg = (
            f"[ALERT TRIGGERED] {item_type}: {target_name}\n"
            f"   Current Price: {currency} {current_price:.2f} <= Target: {currency} {target_price:.2f}!\n"
            f"   You save: {currency} {savings:.2f}"
        )
        logger.warning(msg)

        if self.webhook_url:
            self.send_webhook(
                title=f"Price Alert: {target_name}",
                message=msg,
                payload_data=alert_data,
            )

        return msg

    def notify_price_drop(
        self, item_name: str, old_price: float, new_price: float, currency: str = "USD"
    ) -> str:
        """Format, log, and dispatch notification of a price drop between scraping intervals."""
        drop_amount = old_price - new_price
        pct = (drop_amount / old_price) * 100 if old_price > 0 else 0.0
        msg = (
            f"[PRICE DROP DETECTED] {item_name}\n"
            f"   Old: {currency} {old_price:.2f} -> New: {currency} {new_price:.2f}\n"
            f"   Drop: -{currency} {drop_amount:.2f} (-{pct:.1f}%)"
        )
        logger.info(msg)

        if self.webhook_url:
            self.send_webhook(
                title=f"Price Drop Detected: {item_name}",
                message=msg,
                payload_data={
                    "item_name": item_name,
                    "old_price": old_price,
                    "new_price": new_price,
                    "drop_amount": drop_amount,
                    "percentage_drop": round(pct, 2),
                    "currency": currency,
                },
            )

        return msg
