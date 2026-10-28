import logging
from typing import List, Optional, Tuple, Dict, Any

from tracker.client import HttpClient
from tracker.parsers.flight_parser import FlightParser
from tracker.models import FlightItem
from tracker.storage.database import DatabaseManager
from tracker.alerts.notifier import Notifier

logger = logging.getLogger(__name__)


class FlightScraper:
    """
    Coordinates flight extraction pipeline:
    1. HTTP retrieval using requests.Session with retries & user-agent rotation
    2. HTML parsing using BeautifulSoup (handling itineraries, airlines, times, prices)
    3. Storing price points in database
    4. Evaluating price drop triggers and threshold alerts
    """

    def __init__(
        self,
        client: Optional[HttpClient] = None,
        parser: Optional[FlightParser] = None,
        db: Optional[DatabaseManager] = None,
    ):
        self.client = client or HttpClient()
        self.parser = parser or FlightParser()
        self.db = db or DatabaseManager()
        self.notifier = Notifier()

    def scrape_url(self, url: str, track_in_db: bool = True) -> List[FlightItem]:
        """Fetch URL with requests, parse flight data with BeautifulSoup, and optionally track."""
        logger.info(f"Scraping flights from URL: {url}")
        soup = self.client.get_soup(url)
        flights = self.parser.parse(soup, base_url=url)

        if track_in_db and flights:
            for flight in flights:
                is_drop, price_diff = self.db.record_flight(flight)
                if is_drop and price_diff:
                    self.notifier.notify_price_drop(
                        item_name=f"{flight.airline} {flight.flight_number} ({flight.origin}->{flight.destination})",
                        old_price=flight.price - price_diff,
                        new_price=flight.price,
                        currency=flight.currency,
                    )

            # Check if any threshold alerts were reached
            triggered_alerts = self.db.check_triggered_alerts()
            for alert in triggered_alerts:
                self.notifier.notify_alert(alert)

        return flights

    def scrape_html_string(self, html_content: str, base_url: str = "", track_in_db: bool = True) -> List[FlightItem]:
        """Directly parse HTML content string (useful for offline files and mock fixtures)."""
        soup = self.client.get_soup(html_content, is_html_content=True)
        flights = self.parser.parse(soup, base_url=base_url)

        if track_in_db and flights:
            for flight in flights:
                self.db.record_flight(flight)

        return flights

    def check_alerts(self) -> List[Dict[str, Any]]:
        """Evaluate active price alerts against current database flight prices."""
        triggered = self.db.check_triggered_alerts()
        for alert in triggered:
            self.notifier.notify_alert(alert)
        return triggered

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
