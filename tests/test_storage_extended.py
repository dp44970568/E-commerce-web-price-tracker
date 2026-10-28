import unittest
import tempfile
import csv
from pathlib import Path
from tracker.storage.database import DatabaseManager
from tracker.models import FlightItem, ProductItem


class TestStorageExtended(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_extended.db"
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_alert_delete_and_toggle(self):
        aid = self.db.create_alert(
            target_id="FLIGHT_123",
            target_type="flight",
            target_name="Test Air TA 101",
            target_price=300.0,
            currency="USD",
        )
        self.assertIsInstance(aid, int)

        # Toggle active to False
        ok = self.db.toggle_alert(aid, active=False)
        self.assertTrue(ok)
        alerts = self.db.get_all_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["active"], 0)

        # Toggle back
        ok = self.db.toggle_alert(aid)
        self.assertTrue(ok)
        alerts = self.db.get_all_alerts()
        self.assertEqual(alerts[0]["active"], 1)

        # Delete alert
        deleted = self.db.delete_alert(aid)
        self.assertTrue(deleted)
        self.assertEqual(len(self.db.get_all_alerts()), 0)

    def test_trend_analytics(self):
        flight = FlightItem(
            airline="TrendAir",
            flight_number="TR 500",
            origin="JFK",
            destination="CDG",
            departure_time="09:00",
            arrival_time="21:00",
            price=600.0,
            currency="USD",
        )
        self.db.record_flight(flight)

        flight.price = 550.0
        self.db.record_flight(flight)

        flight.price = 500.0
        self.db.record_flight(flight)

        analytics = self.db.get_trend_analytics(flight.flight_identifier, target_type="flight")
        self.assertEqual(analytics["data_points"], 3)
        self.assertEqual(analytics["first_price"], 600.0)
        self.assertEqual(analytics["latest_price"], 500.0)
        self.assertEqual(analytics["lowest_price"], 500.0)
        self.assertEqual(analytics["highest_price"], 600.0)
        self.assertEqual(analytics["price_change"], -100.0)
        self.assertAlmostEqual(analytics["price_change_pct"], -16.67, places=1)
        self.assertEqual(analytics["drops_count"], 2)

    def test_csv_export(self):
        flight = FlightItem(
            airline="ExportAir",
            flight_number="EX 99",
            origin="LAX",
            destination="NRT",
            departure_time="12:00",
            arrival_time="16:00",
            price=750.0,
            currency="USD",
        )
        self.db.record_flight(flight)

        csv_file = Path(self.temp_dir.name) / "flights.csv"
        self.db.export_to_csv("flights", csv_file)

        self.assertTrue(csv_file.exists())
        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            self.assertGreaterEqual(len(reader), 2)  # Header + row
            headers = reader[0]
            self.assertIn("airline", headers)
            self.assertIn("latest_price", headers)


if __name__ == "__main__":
    unittest.main()
