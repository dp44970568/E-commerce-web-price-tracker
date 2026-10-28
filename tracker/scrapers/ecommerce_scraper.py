import logging
from typing import List, Optional, Dict, Any

from tracker.client import HttpClient
from tracker.parsers.ecommerce_parser import EcommerceParser
from tracker.models import ProductItem
from tracker.storage.database import DatabaseManager
from tracker.alerts.notifier import Notifier

logger = logging.getLogger(__name__)


class EcommerceScraper:
    """
    Coordinates e-commerce product extraction pipeline:
    - HTTP requests with session persistence & retries
    - BeautifulSoup HTML parsing
    - Historical price recording and alert notifications
    """

    def __init__(
        self,
        client: Optional[HttpClient] = None,
        parser: Optional[EcommerceParser] = None,
        db: Optional[DatabaseManager] = None,
    ):
        self.client = client or HttpClient()
        self.parser = parser or EcommerceParser()
        self.db = db or DatabaseManager()
        self.notifier = Notifier()

    def scrape_product(
        self, url: str, site_name: str = "WebStore", track_in_db: bool = True
    ) -> Optional[ProductItem]:
        """Fetch and parse an individual product page."""
        logger.info(f"Scraping product from: {url}")
        soup = self.client.get_soup(url)
        product = self.parser.parse_single_product(soup, page_url=url, site_name=site_name)

        if product and track_in_db:
            is_drop, price_diff = self.db.record_product(product)
            if is_drop and price_diff:
                self.notifier.notify_price_drop(
                    item_name=product.title,
                    old_price=product.price - price_diff,
                    new_price=product.price,
                    currency=product.currency,
                )

            # Check threshold alerts
            triggered = self.db.check_triggered_alerts()
            for alert in triggered:
                self.notifier.notify_alert(alert)

        return product

    def scrape_catalog(
        self, url: str, site_name: str = "WebStore", track_in_db: bool = True
    ) -> List[ProductItem]:
        """Fetch and parse a catalog/listing page."""
        logger.info(f"Scraping catalog from: {url}")
        soup = self.client.get_soup(url)
        items = self.parser.parse_listing_page(soup, base_url=url, site_name=site_name)

        if track_in_db and items:
            for item in items:
                self.db.record_product(item)

        return items

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
