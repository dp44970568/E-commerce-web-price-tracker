import unittest
import tempfile
from pathlib import Path
from tracker.storage.database import DatabaseManager
from tracker.models import FlightItem, ProductItem


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_tracker.db"
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_record_flight_and_history(self):
        flight = FlightItem(
            airline="Test Air",
            flight_number="TA 100",
            origin="JFK",
            destination="LHR",
            departure_time="10:00",
            arrival_time="22:00",
            price=500.0,
            currency="USD",
        )

        # 1. Insert initial
        is_drop, diff = self.db.record_flight(flight)
        self.assertFalse(is_drop)

        # 2. Update with lower price
        flight.price = 450.0
        is_drop, diff = self.db.record_flight(flight)
        self.assertTrue(is_drop)
        self.assertEqual(diff, -50.0)

        # 3. Verify history has 2 records
        history = self.db.get_flight_history(flight.flight_identifier)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["price"], 500.0)
        self.assertEqual(history[1]["price"], 450.0)

        # 4. Check summary
        tracked = self.db.get_tracked_flights()
        self.assertEqual(len(tracked), 1)
        self.assertEqual(tracked[0]["lowest_price"], 450.0)
        self.assertEqual(tracked[0]["highest_price"], 500.0)

    def test_alert_trigger(self):
        flight = FlightItem(
            airline="SkyAir",
            flight_number="SA 200",
            origin="SFO",
            destination="TYO",
            departure_time="11:00",
            arrival_time="15:00",
            price=800.0,
            currency="USD",
        )
        self.db.record_flight(flight)

        # Create alert for <= 750
        self.db.create_alert(
            target_id=flight.flight_identifier,
            target_type="flight",
            target_name="SkyAir SA 200",
            target_price=750.0,
            currency="USD",
        )

        # Check triggered - should be empty initially
        triggered = self.db.check_triggered_alerts()
        self.assertEqual(len(triggered), 0)

        # Price drops to 720
        flight.price = 720.0
        self.db.record_flight(flight)

        # Check triggered - should now match!
        triggered = self.db.check_triggered_alerts()
        self.assertEqual(len(triggered), 1)
        self.assertEqual(triggered[0]["target_id"], flight.flight_identifier)
        self.assertEqual(triggered[0]["latest_price"], 720.0)


if __name__ == "__main__":
    unittest.main()
