import http.server
import socketserver
import threading
import urllib.parse
import json
import logging
from typing import Optional

from tracker.mock_server.flight_fixtures import generate_flight_search_html

logger = logging.getLogger(__name__)

MOCK_PRODUCT_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Sony WH-1000XM5 Wireless Headphones | TechStore</title>
</head>
<body>
    <div class="product-container">
        <h1 id="productTitle">Sony WH-1000XM5 Wireless Noise Canceling Headphones</h1>
        <div class="rating-box">
            <span class="star-rating">4.7 out of 5</span>
            <span id="acrCustomerReviewText">8,429 ratings</span>
        </div>
        <div class="pricing-box">
            <span class="regular-price was-price">$399.99</span>
            <span class="current-price price">$328.00</span>
        </div>
        <div id="availability" class="stock in-stock">
            In Stock. Ships in 24 hours.
        </div>
        <div class="product-details" data-asin="B09XS7JWHH">
            <span class="sku">SONY-XM5-BLK</span>
        </div>
    </div>
</body>
</html>
"""

MOCK_CATALOG_HTML = """<!DOCTYPE html>
<html>
<head><title>Best Selling Electronics | TechStore</title></head>
<body>
    <div class="catalog-list">
        <article class="product-card">
            <h3 class="product-title"><a href="/product/1">Sony WH-1000XM5 Headphones</a></h3>
            <span class="price">$328.00</span>
        </article>
        <article class="product-card">
            <h3 class="product-title"><a href="/product/2">Apple MacBook Air M3 15-inch</a></h3>
            <span class="price">$1,199.00</span>
        </article>
        <article class="product-card">
            <h3 class="product-title"><a href="/product/3">Kindle Paperwhite 16GB</a></h3>
            <span class="price">$149.99</span>
        </article>
    </div>
</body>
</html>
"""


class MockTravelHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler for mock flight search and e-commerce endpoints."""

    variance: float = 0.0
    product_variance: float = 0.0

    def get_product_html(self) -> str:
        current_p = max(50.0, 328.0 + MockTravelHandler.product_variance)
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Sony WH-1000XM5 Wireless Headphones | TechStore</title>
</head>
<body>
    <div class="product-container">
        <h1 id="productTitle">Sony WH-1000XM5 Wireless Noise Canceling Headphones</h1>
        <div class="rating-box">
            <span class="star-rating">4.7 out of 5</span>
            <span id="acrCustomerReviewText">8,429 ratings</span>
        </div>
        <div class="pricing-box">
            <span class="regular-price was-price">$399.99</span>
            <span class="current-price price">${current_p:.2f}</span>
        </div>
        <div id="availability" class="stock in-stock">
            In Stock. Ships in 24 hours.
        </div>
        <div class="product-details" data-asin="B09XS7JWHH">
            <span class="sku">SONY-XM5-BLK</span>
        </div>
    </div>
</body>
</html>
"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if parsed.path.startswith("/flights"):
            origin = query.get("from", ["JFK"])[0].upper()
            dest = query.get("to", ["LHR"])[0].upper()
            curr = query.get("currency", ["USD"])[0].upper()

            html = generate_flight_search_html(
                origin=origin,
                destination=dest,
                currency=curr,
                price_variance=MockTravelHandler.variance,
            )
            self._send_html(html)

        elif parsed.path.startswith("/product/"):
            self._send_html(self.get_product_html())

        elif parsed.path.startswith("/products") or parsed.path == "/":
            self._send_html(MOCK_CATALOG_HTML)

        elif parsed.path == "/trigger-discount":
            # Artificially lower flight prices by $60 to trigger alerts!
            MockTravelHandler.variance -= 60.0
            self._send_json({"status": "discount_applied", "variance": MockTravelHandler.variance})

        elif parsed.path == "/trigger-product-discount":
            # Artificially lower product price by $50 to trigger alerts!
            MockTravelHandler.product_variance -= 50.0
            self._send_json({"status": "product_discount_applied", "variance": MockTravelHandler.product_variance})

        elif parsed.path == "/reset-prices":
            MockTravelHandler.variance = 0.0
            MockTravelHandler.product_variance = 0.0
            self._send_json({"status": "prices_reset"})

        else:
            self.send_error(404, "Not Found")

    def _send_html(self, html: str):
        content = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data: dict):
        content = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        # Silence default standard err logging for cleaner test output
        logger.debug("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))


class MockServerThread:
    """Helper to run the mock server in a daemon thread for testing or CLI demo."""

    def __init__(self, port: int = 8765):
        self.port = port
        self.server: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self):
        handler = MockTravelHandler
        # Allow immediate reuse of port
        socketserver.TCPServer.allow_reuse_address = True
        self.server = socketserver.TCPServer(("127.0.0.1", self.port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"Mock flight & ecommerce server started at http://127.0.0.1:{self.port}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Mock server stopped.")
