import unittest
from unittest.mock import patch, MagicMock
from tracker.alerts.notifier import Notifier


class TestNotifier(unittest.TestCase):
    def setUp(self):
        self.notifier = Notifier()

    def test_notify_alert_formatting(self):
        alert_data = {
            "target_name": "British Airways BA 178",
            "latest_price": 450.0,
            "target_price": 500.0,
            "currency": "USD",
            "target_type": "flight",
        }
        msg = self.notifier.notify_alert(alert_data)
        self.assertIn("ALERT TRIGGERED", msg)
        self.assertIn("British Airways BA 178", msg)
        self.assertIn("450.00", msg)
        self.assertIn("500.00", msg)
        self.assertIn("You save: USD 50.00", msg)

    def test_notify_price_drop_formatting(self):
        msg = self.notifier.notify_price_drop(
            item_name="Sony Headphones",
            old_price=399.0,
            new_price=349.0,
            currency="USD",
        )
        self.assertIn("PRICE DROP DETECTED", msg)
        self.assertIn("Sony Headphones", msg)
        self.assertIn("399.00", msg)
        self.assertIn("349.00", msg)
        self.assertIn("-USD 50.00", msg)

    @patch("requests.post")
    def test_webhook_dispatch(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        notifier_with_webhook = Notifier(webhook_url="https://hooks.example.com/test")
        res = notifier_with_webhook.send_webhook("Test Title", "Test Message", {"key": "val"})

        self.assertTrue(res)
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
