import time
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from tracker.storage.database import DatabaseManager
from tracker.scrapers.flight_scraper import FlightScraper
from tracker.scrapers.ecommerce_scraper import EcommerceScraper
from tracker.alerts.notifier import Notifier
from tracker.mock_server.flight_fixtures import generate_flight_search_html

logger = logging.getLogger(__name__)


class PriceMonitor:
    """
    Automated monitoring engine that periodically refreshes prices for
    tracked flights and e-commerce products, records price history,
    and dispatches drop notifications.
    """

    def __init__(
        self,
        db: Optional[DatabaseManager] = None,
        notifier: Optional[Notifier] = None,
        flight_urls: Optional[List[str]] = None,
        product_urls: Optional[List[str]] = None,
    ):
        self.db = db or DatabaseManager()
        self.notifier = notifier or Notifier()
        self.flight_urls: List[str] = flight_urls or []
        self.product_urls: List[str] = product_urls or []
        self._running = False

    def add_flight_url(self, url: str):
        if url not in self.flight_urls:
            self.flight_urls.append(url)

    def add_product_url(self, url: str):
        if url not in self.product_urls:
            self.product_urls.append(url)

    def load_targets_from_database(self):
        """
        Loads product and flight URLs that were previously tracked in the database.
        """
        products = self.db.get_tracked_products()
        for p in products:
            if p.get("url") and p["url"] not in self.product_urls:
                self.product_urls.append(p["url"])

        flights = self.db.get_tracked_flights()
        for f in flights:
            if f.get("booking_url") and f["booking_url"] not in self.flight_urls:
                self.flight_urls.append(f["booking_url"])

    def run_once(self) -> Dict[str, Any]:
        """
        Executes a single monitoring cycle across all configured flight and product URLs.
        Returns a summary dictionary of results and alerts.
        """
        logger.info(f"Starting monitoring cycle at {datetime.utcnow().isoformat()}")
        flights_scraped = 0
        products_scraped = 0
        triggered_alerts: List[Dict[str, Any]] = []

        # 1. Scrape configured flight URLs
        with FlightScraper(db=self.db) as f_scraper:
            for url in self.flight_urls:
                try:
                    res = f_scraper.scrape_url(url, track_in_db=True)
                    flights_scraped += len(res)
                except Exception as e:
                    logger.error(f"Error monitoring flight URL {url}: {e}")

        # 2. Scrape configured product URLs
        with EcommerceScraper(db=self.db) as e_scraper:
            for url in self.product_urls:
                try:
                    prod = e_scraper.scrape_product(url, track_in_db=True)
                    if prod:
                        products_scraped += 1
                except Exception as e:
                    logger.error(f"Error monitoring product URL {url}: {e}")

        # 3. Check for any threshold alerts
        triggered_alerts = self.db.check_triggered_alerts()
        for alert in triggered_alerts:
            self.notifier.notify_alert(alert)

        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "flights_scraped": flights_scraped,
            "products_scraped": products_scraped,
            "alerts_triggered_count": len(triggered_alerts),
            "triggered_alerts": triggered_alerts,
        }
        logger.info(f"Monitoring cycle finished: {flights_scraped} flights, {products_scraped} products checked.")
        return summary

    def run_loop(
        self,
        interval_seconds: int = 60,
        max_iterations: Optional[int] = None,
        callback: Optional[Callable[[int, Dict[str, Any]], None]] = None,
    ):
        """
        Continuously polls prices at the specified interval in seconds.
        """
        self._running = True
        iteration = 0
        logger.info(f"PriceMonitor started. Polling interval: {interval_seconds}s")

        try:
            while self._running:
                iteration += 1
                summary = self.run_once()
                if callback:
                    callback(iteration, summary)

                if max_iterations and iteration >= max_iterations:
                    logger.info(f"Reached max iterations ({max_iterations}). Stopping monitor.")
                    break

                for _ in range(interval_seconds):
                    if not self._running:
                        break
                    time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user.")
        finally:
            self._running = False

    def stop(self):
        """Signals the monitoring loop to stop."""
        self._running = False
