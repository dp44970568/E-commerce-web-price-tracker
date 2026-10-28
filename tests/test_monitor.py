import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from tracker.storage.database import DatabaseManager
from tracker.monitor import PriceMonitor
from tracker.models import FlightItem, ProductItem


class TestPriceMonitor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_monitor.db"
        self.db = DatabaseManager(db_path=self.db_path)
        self.monitor = PriceMonitor(db=self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_urls_and_load(self):
        self.monitor.add_flight_url("http://example.com/flight")
        self.monitor.add_product_url("http://example.com/product/1")

        self.assertIn("http://example.com/flight", self.monitor.flight_urls)
        self.assertIn("http://example.com/product/1", self.monitor.product_urls)

    @patch("tracker.scrapers.flight_scraper.FlightScraper.scrape_url")
    @patch("tracker.scrapers.ecommerce_scraper.EcommerceScraper.scrape_product")
    def test_run_once(self, mock_scrape_prod, mock_scrape_flight):
        flight = FlightItem(
            airline="TestAir",
            flight_number="TA 1",
            origin="JFK",
            destination="LHR",
            departure_time="08:00",
            arrival_time="20:00",
            price=400.0,
        )
        product = ProductItem(
            title="Test Gadget",
            price=99.99,
        )
        mock_scrape_flight.return_value = [flight]
        mock_scrape_prod.return_value = product

        self.monitor.add_flight_url("http://example.com/flights")
        self.monitor.add_product_url("http://example.com/product/1")

        summary = self.monitor.run_once()

        self.assertEqual(summary["flights_scraped"], 1)
        self.assertEqual(summary["products_scraped"], 1)
        self.assertIn("timestamp", summary)


if __name__ == "__main__":
    unittest.main()
