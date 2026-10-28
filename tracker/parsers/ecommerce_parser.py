import re
import logging
from typing import List, Optional, Dict, Any, Union
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag

from tracker.models import ProductItem
from tracker.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)


class EcommerceParser(BaseParser):
    """
    BeautifulSoup HTML parser for e-commerce product pages and search result listings.
    Supports parsing both individual product pages and product catalogs.
    """

    PRODUCT_LIST_CONTAINERS = [
        ".product-card",
        ".product-item",
        ".s-result-item",
        ".product_pod",         # Books to Scrape standard
        ".catalog-item",
        "[data-component-type='s-search-result']",
        ".grid-item",
        "article.product",
        "li.product",
    ]

    def __init__(self, custom_selectors: Optional[Dict[str, str]] = None):
        self.selectors = custom_selectors or {}

    def parse_single_product(
        self, soup_or_html: Union[BeautifulSoup, str], page_url: str = "", site_name: str = ""
    ) -> Optional[ProductItem]:
        """Parses a dedicated product details page."""
        if isinstance(soup_or_html, str):
            soup = BeautifulSoup(soup_or_html, "lxml")
        else:
            soup = soup_or_html

        # 1. Product Title
        title = self._extract_single_title(soup)
        if not title:
            return None

        # 2. Price and Currency
        price, currency, original_price = self._extract_single_prices(soup)
        if price is None:
            return None

        # 3. Discount
        discount = None
        if original_price and original_price > price:
            discount = round(((original_price - price) / original_price) * 100, 1)

        # 4. Stock status
        in_stock = self._extract_stock_status(soup)

        # 5. Rating and reviews
        rating, reviews_count = self._extract_ratings_and_reviews(soup)

        # 6. SKU / Product ID
        sku = self._extract_sku(soup)

        return ProductItem(
            title=title,
            price=price,
            currency=currency,
            original_price=original_price,
            discount_percentage=discount,
            in_stock=in_stock,
            rating=rating,
            reviews_count=reviews_count,
            sku=sku,
            url=page_url,
            site_name=site_name,
        )

    def parse_listing_page(
        self, soup_or_html: Union[BeautifulSoup, str], base_url: str = "", site_name: str = ""
    ) -> List[ProductItem]:
        """Parses a multi-product catalog or search results page."""
        if isinstance(soup_or_html, str):
            soup = BeautifulSoup(soup_or_html, "lxml")
        else:
            soup = soup_or_html

        items: List[ProductItem] = []
        containers = self._find_listing_containers(soup)

        for container in containers:
            try:
                # Title
                title_node = container.select_one("h3 a, h2 a, .product-title, .title, .p-name")
                title = self.clean_text(title_node.get_text() if title_node else "")
                if not title and title_node and title_node.get("title"):
                    title = self.clean_text(title_node["title"])

                # URL
                prod_url = None
                if title_node and title_node.get("href"):
                    prod_url = urljoin(base_url, title_node["href"])

                # Price
                price_node = container.select_one(".price_color, .price, .product-price, .amount, [data-price]")
                price_text = price_node.get_text() if price_node else container.get_text()
                price, currency = self.extract_price_and_currency(price_text)

                if title and price is not None and price > 0:
                    items.append(
                        ProductItem(
                            title=title,
                            price=price,
                            currency=currency,
                            url=prod_url,
                            site_name=site_name,
                        )
                    )
            except Exception as e:
                logger.debug(f"Failed to parse product listing item: {e}")
                continue

        return items

    def _find_listing_containers(self, soup: BeautifulSoup) -> List[Tag]:
        if "container" in self.selectors:
            matched = soup.select(self.selectors["container"])
            if matched:
                return matched

        for sel in self.PRODUCT_LIST_CONTAINERS:
            matched = soup.select(sel)
            if matched:
                return matched

        return []

    def _extract_single_title(self, soup: BeautifulSoup) -> str:
        if "title" in self.selectors:
            t = self.safe_select_text(soup, self.selectors["title"])
            if t:
                return t

        title_selectors = [
            "#productTitle",
            "h1.product-title",
            "h1.entry-title",
            "h1.title",
            "div.product-main h1",
            "h1",
        ]
        for sel in title_selectors:
            val = self.safe_select_text(soup, sel)
            if val:
                return val
        return ""

    def _extract_single_prices(self, soup: BeautifulSoup) -> tuple[Optional[float], str, Optional[float]]:
        price = None
        currency = "USD"
        original_price = None

        if "price" in self.selectors:
            p_text = self.safe_select_text(soup, self.selectors["price"])
            price, currency = self.extract_price_and_currency(p_text)

        if price is None:
            price_selectors = [
                ".price_color",
                ".a-price .a-offscreen",
                "#priceblock_ourprice",
                "#priceblock_dealprice",
                ".product-price",
                ".current-price",
                "span.price",
            ]
            for sel in price_selectors:
                node = soup.select_one(sel)
                if node:
                    price, currency = self.extract_price_and_currency(node.get_text())
                    if price is not None:
                        break

        # Check for original / strike-through price
        orig_selectors = [
            ".a-text-price .a-offscreen",
            ".regular-price",
            ".was-price",
            ".original-price",
            "del .amount",
            "s.price",
        ]
        for sel in orig_selectors:
            node = soup.select_one(sel)
            if node:
                op, _ = self.extract_price_and_currency(node.get_text())
                if op and op > (price or 0):
                    original_price = op
                    break

        return price, currency, original_price

    def _extract_stock_status(self, soup: BeautifulSoup) -> bool:
        stock_text = self.safe_select_text(
            soup,
            "#availability, .stock, .in-stock, .availability, p.instock"
        ).lower()
        if not stock_text:
            return True
        if "out of stock" in stock_text or "unavailable" in stock_text or "sold out" in stock_text:
            return False
        return True

    def _extract_ratings_and_reviews(self, soup: BeautifulSoup) -> tuple[Optional[float], Optional[int]]:
        rating = None
        reviews = None

        # Rating
        rating_text = self.safe_select_text(soup, ".star-rating, .rating, [data-rating], .a-icon-alt")
        if rating_text:
            # Look for "4.5 out of 5" or "4.5"
            match = re.search(r"(\d+(?:\.\d+)?)\s*(?:out of|\/)?\s*5?", rating_text)
            if match:
                try:
                    rating = float(match.group(1))
                except ValueError:
                    pass

        # Reviews count
        reviews_text = self.safe_select_text(soup, "#acrCustomerReviewText, .reviews-count, .review-count")
        if reviews_text:
            match = re.search(r"([\d,]+)", reviews_text)
            if match:
                try:
                    reviews = int(match.group(1).replace(",", ""))
                except ValueError:
                    pass

        return rating, reviews

    def _extract_sku(self, soup: BeautifulSoup) -> Optional[str]:
        # Check standard meta tags or data attributes
        sku_node = soup.select_one("[data-asin], [itemprop='sku'], .sku")
        if sku_node:
            return sku_node.get("data-asin") or sku_node.get("content") or self.clean_text(sku_node.get_text())
        return None
