"""
E-Commerce & Flight Web Price Tracker
Tech stack: Python, BeautifulSoup, Requests, SQLite
"""

from tracker.client import HttpClient
from tracker.parsers.flight_parser import FlightParser
from tracker.parsers.ecommerce_parser import EcommerceParser
from tracker.scrapers.flight_scraper import FlightScraper
from tracker.scrapers.ecommerce_scraper import EcommerceScraper
from tracker.storage.database import DatabaseManager
from tracker.alerts.notifier import Notifier
from tracker.monitor import PriceMonitor
from tracker.models import FlightItem, ProductItem, PriceAlert

__version__ = "1.1.0"
__all__ = [
    "HttpClient",
    "FlightParser",
    "EcommerceParser",
    "FlightScraper",
    "EcommerceScraper",
    "DatabaseManager",
    "Notifier",
    "PriceMonitor",
    "FlightItem",
    "ProductItem",
    "PriceAlert",
]
