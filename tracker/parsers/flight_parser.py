import re
import logging
from typing import List, Optional, Dict, Any, Union
from bs4 import BeautifulSoup, Tag

from tracker.models import FlightItem
from tracker.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)


class FlightParser(BaseParser):
    """
    Robust BeautifulSoup HTML parser for flight search results and booking pages.
    Provides multi-strategy extraction:
    1. Standard selector rules (for common travel web templates).
    2. Attribute-based extraction (data-* attributes, aria-labels).
    3. Structural regex heuristics (tolerates dynamic/obfuscated CSS classes).
    """

    # Common container selectors used in travel and flight portals
    CONTAINER_SELECTORS = [
        ".flight-card",
        ".flight-item",
        ".itinerary-card",
        ".flight-result",
        ".flight-row",
        ".trip-option",
        "[data-testid*='flight-card']",
        "[data-component*='flight']",
        ".result-item",
        "article.flight",
        "li.flight-result",
    ]

    def __init__(self, custom_selectors: Optional[Dict[str, str]] = None):
        """
        Optional custom CSS selectors dictionary:
        {
            'container': '.my-flight-card',
            'airline': '.airline-title',
            'flight_number': '.flight-no',
            'origin': '.origin-code',
            'destination': '.dest-code',
            'departure_time': '.dep-time',
            'arrival_time': '.arr-time',
            'duration': '.total-duration',
            'stops': '.stops-badge',
            'price': '.price-amount',
            'cabin_class': '.cabin-badge',
            'booking_link': 'a.book-now'
        }
        """
        self.selectors = custom_selectors or {}

    def parse(self, soup_or_html: Union[BeautifulSoup, str], base_url: str = "") -> List[FlightItem]:
        """Parse HTML and extract all flight itineraries found."""
        if isinstance(soup_or_html, str):
            soup = BeautifulSoup(soup_or_html, "lxml")
        else:
            soup = soup_or_html

        flight_items: List[FlightItem] = []

        # 1. Identify flight result containers
        containers = self._find_flight_containers(soup)
        logger.debug(f"Found {len(containers)} potential flight containers.")

        for container in containers:
            try:
                flight = self._parse_single_flight(container, base_url)
                if flight and flight.price > 0:
                    flight_items.append(flight)
            except Exception as e:
                logger.debug(f"Error parsing single flight container: {e}", exc_info=True)
                continue

        # 2. Fallback: If no containers matched, attempt tabular / semantic regex scan
        if not flight_items:
            flight_items = self._fallback_semantic_scan(soup, base_url)

        return flight_items

    def _find_flight_containers(self, soup: BeautifulSoup) -> List[Tag]:
        """Find list of flight card elements using selector priority."""
        if "container" in self.selectors:
            matched = soup.select(self.selectors["container"])
            if matched:
                return matched

        for sel in self.CONTAINER_SELECTORS:
            matched = soup.select(sel)
            if matched:
                return matched

        # Look for table rows with flight indicators
        rows = soup.select("table.flights tbody tr, table.flight-list tr")
        if rows:
            return rows

        # Fallback: find any element that has both a price and a time
        candidates = []
        for div in soup.find_all(["div", "section", "article"]):
            # Avoid top-level parent containers
            text = div.get_text()
            if any(sym in text for sym in ["$", "€", "£", "₹"]) and re.search(r"\b\d{1,2}:\d{2}\b", text):
                # Ensure it's a leaf card, not the whole page
                sub_cards = div.find_all(["div", "section", "article"], recursive=False)
                if not any(
                    any(sym in sc.get_text() for sym in ["$", "€", "£", "₹"])
                    for sc in sub_cards
                ):
                    candidates.append(div)
        return candidates[:50]  # limit to prevent excessive checks

    def _parse_single_flight(self, card: Tag, base_url: str = "") -> Optional[FlightItem]:
        """Extract all flight fields from a single card/row."""

        # --- 1. Price & Currency ---
        price_val, currency = self._extract_card_price(card)
        if price_val is None or price_val <= 0:
            return None

        # --- 2. Airline ---
        airline = self._extract_airline(card)

        # --- 3. Flight Number ---
        flight_number = self._extract_flight_number(card, airline)

        # --- 4. Times & Airports (Origin / Destination) ---
        dep_time, arr_time, origin, dest = self._extract_route_and_times(card)

        # --- 5. Duration ---
        duration = self._extract_duration(card)

        # --- 6. Stops & Layover info ---
        stops_count, stop_details = self._extract_stops_info(card)

        # --- 7. Cabin Class ---
        cabin = self._extract_cabin_class(card)

        # --- 8. Booking URL ---
        booking_url = self._extract_booking_url(card, base_url)

        return FlightItem(
            airline=airline,
            flight_number=flight_number,
            origin=origin,
            destination=dest,
            departure_time=dep_time,
            arrival_time=arr_time,
            price=price_val,
            currency=currency,
            duration=duration,
            stops=stops_count,
            stop_details=stop_details,
            cabin_class=cabin,
            booking_url=booking_url,
        )

    def _extract_card_price(self, card: Tag) -> tuple[Optional[float], str]:
        # Custom selector check
        if "price" in self.selectors:
            p_text = self.safe_select_text(card, self.selectors["price"])
            p, c = self.extract_price_and_currency(p_text)
            if p:
                return p, c

        # Common price classes / data attributes
        price_selectors = [
            ".price", ".flight-price", ".amount", ".fare-price",
            "[data-price]", "[data-testid*='price']", ".total-price", ".price-tag"
        ]
        for sel in price_selectors:
            node = card.select_one(sel)
            if node:
                # Check data-price attribute first
                if node.get("data-price"):
                    p, c = self.extract_price_and_currency(node["data-price"])
                    if p:
                        return p, c
                p, c = self.extract_price_and_currency(node.get_text())
                if p:
                    return p, c

        # Fallback: scan all text in card for price
        return self.extract_price_and_currency(card.get_text())

    def _extract_airline(self, card: Tag) -> str:
        if "airline" in self.selectors:
            val = self.safe_select_text(card, self.selectors["airline"])
            if val:
                return val

        airline_selectors = [
            ".airline", ".airline-name", ".carrier-name", ".airline-title",
            "[data-test*='airline']", ".airline-info span", ".flight-carrier"
        ]
        for sel in airline_selectors:
            val = self.safe_select_text(card, sel)
            if val:
                return val

        # Check airline image alt or title attribute
        img = card.select_one("img.airline-logo, img[alt*='Air'], img[alt*='Airlines'], img[alt*='Flight']")
        if img and img.get("alt"):
            return self.clean_text(img["alt"])

        return "Unknown Airline"

    def _extract_flight_number(self, card: Tag, airline: str = "") -> str:
        if "flight_number" in self.selectors:
            val = self.safe_select_text(card, self.selectors["flight_number"])
            if val:
                return val

        fn_selectors = [
            ".flight-number", ".flight-no", ".flight-code", "[data-test*='flight-number']"
        ]
        for sel in fn_selectors:
            val = self.safe_select_text(card, sel)
            if val:
                return val

        # Regex search for IATA airline code + digits, e.g. "DL 1234", "AA-492", "EK 202"
        text = card.get_text()
        match = re.search(r"\b([A-Z0-9]{2}\s*[-]?\s*\d{2,4})\b", text)
        if match:
            return self.clean_text(match.group(1))

        # Generate a placeholder identifier if flight number is unlisted
        return f"{airline[:3].upper() or 'FL'}-TBD"

    def _extract_route_and_times(self, card: Tag) -> tuple[str, str, str, str]:
        """Extract departure time, arrival time, origin airport, and destination airport."""
        dep_time = "N/A"
        arr_time = "N/A"
        origin = "ORIGIN"
        dest = "DEST"

        # Explicit selectors
        if "departure_time" in self.selectors:
            dep_time = self.safe_select_text(card, self.selectors["departure_time"], "N/A")
        if "arrival_time" in self.selectors:
            arr_time = self.safe_select_text(card, self.selectors["arrival_time"], "N/A")
        if "origin" in self.selectors:
            origin = self.safe_select_text(card, self.selectors["origin"], "ORIGIN")
        if "destination" in self.selectors:
            dest = self.safe_select_text(card, self.selectors["destination"], "DEST")

        # Class based search if not already found
        if dep_time == "N/A":
            dep_node = card.select_one(".departure-time, .dep-time, [data-test*='departure-time'], .time-dep")
            if dep_node:
                dep_time = self.clean_text(dep_node.get_text())

        if arr_time == "N/A":
            arr_node = card.select_one(".arrival-time, .arr-time, [data-test*='arrival-time'], .time-arr")
            if arr_node:
                arr_time = self.clean_text(arr_node.get_text())

        if origin == "ORIGIN":
            orig_node = card.select_one(".origin, .departure-airport, .from-code, .origin-code")
            if orig_node:
                code = self.extract_airport_code(orig_node.get_text())
                origin = code or self.clean_text(orig_node.get_text())

        if dest == "DEST":
            dest_node = card.select_one(".destination, .arrival-airport, .to-code, .destination-code")
            if dest_node:
                code = self.extract_airport_code(dest_node.get_text())
                dest = code or self.clean_text(dest_node.get_text())

        # Regex heuristic fallback if still missing
        if dep_time == "N/A" or arr_time == "N/A":
            times = re.findall(r"\b(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)\b", card.get_text())
            if len(times) >= 2:
                dep_time = times[0]
                arr_time = times[1]
            elif len(times) == 1:
                dep_time = times[0]

        if origin == "ORIGIN" or dest == "DEST":
            # Find uppercase 3-letter codes that look like airport codes
            codes = re.findall(r"\b([A-Z]{3})\b", card.get_text())
            # Filter out non-airport tokens like USD, EUR, GBP, PM, AM
            airport_candidates = [
                c for c in codes if c not in ["USD", "EUR", "GBP", "INR", "CAD", "AUD", "NON", "ALL", "NEW"]
            ]
            if len(airport_candidates) >= 2:
                if origin == "ORIGIN":
                    origin = airport_candidates[0]
                if dest == "DEST":
                    dest = airport_candidates[1]

        return dep_time, arr_time, origin, dest

    def _extract_duration(self, card: Tag) -> str:
        if "duration" in self.selectors:
            val = self.safe_select_text(card, self.selectors["duration"])
            if val:
                return self.extract_duration(val)

        dur_selectors = [".duration", ".flight-duration", ".flight-time", "[data-test*='duration']"]
        for sel in dur_selectors:
            val = self.safe_select_text(card, sel)
            if val:
                return self.extract_duration(val)

        # Regex search for duration pattern "Xh Ym"
        match = re.search(r"\b(\d+\s*h(?:ours?)?\s*\d*\s*m?(?:in)?)\b", card.get_text(), re.IGNORECASE)
        if match:
            return self.extract_duration(match.group(1))

        return "N/A"

    def _extract_stops_info(self, card: Tag) -> tuple[int, str]:
        if "stops" in self.selectors:
            val = self.safe_select_text(card, self.selectors["stops"])
            if val:
                return self.extract_stops(val)

        stops_selectors = [".stops", ".flight-stops", ".stops-info", ".stop-count", "[data-test*='stop']"]
        for sel in stops_selectors:
            val = self.safe_select_text(card, sel)
            if val:
                return self.extract_stops(val)

        return self.extract_stops(card.get_text())

    def _extract_cabin_class(self, card: Tag) -> str:
        if "cabin_class" in self.selectors:
            val = self.safe_select_text(card, self.selectors["cabin_class"])
            if val:
                return val

        text = card.get_text()
        for cabin in ["First Class", "Business", "Premium Economy", "Economy"]:
            if re.search(r"\b" + re.escape(cabin) + r"\b", text, re.IGNORECASE):
                return cabin

        return "Economy"

    def _extract_booking_url(self, card: Tag, base_url: str = "") -> Optional[str]:
        if "booking_link" in self.selectors:
            link = card.select_one(self.selectors["booking_link"])
            if link and link.get("href"):
                href = link["href"]
                return self._resolve_url(href, base_url)

        # Look for any button or link
        link = card.select_one("a[href*='book'], a[href*='flight'], a.btn-select, a.select-flight, a.book-button")
        if not link:
            link = card.select_one("a[href]")

        if link and link.get("href"):
            return self._resolve_url(link["href"], base_url)

        return None

    @staticmethod
    def _resolve_url(href: str, base_url: str) -> str:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if base_url:
            from urllib.parse import urljoin
            return urljoin(base_url, href)
        return href

    def _fallback_semantic_scan(self, soup: BeautifulSoup, base_url: str = "") -> List[FlightItem]:
        """Secondary fallback that scans structured tables or rows if no cards were detected."""
        results: List[FlightItem] = []
        rows = soup.find_all("tr")
        for row in rows:
            text = row.get_text()
            if any(sym in text for sym in ["$", "€", "£", "₹"]) and re.search(r"\b\d{1,2}:\d{2}\b", text):
                flight = self._parse_single_flight(row, base_url)
                if flight and flight.price > 0:
                    results.append(flight)
        return results
