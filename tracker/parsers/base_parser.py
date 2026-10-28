import re
from typing import Optional, Tuple
from bs4 import BeautifulSoup, Tag

CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "¥": "JPY",
    "A$": "AUD",
    "C$": "CAD",
}


class BaseParser:
    """Base parser providing utility routines for robust HTML extraction and price parsing."""

    @staticmethod
    def clean_text(raw_text: Optional[str]) -> str:
        """Strip HTML artifacts, non-breaking spaces, and redundant whitespace."""
        if not raw_text:
            return ""
        # Replace non-breaking spaces and other odd whitespaces
        cleaned = re.sub(r"[\xa0\u200b\s]+", " ", str(raw_text))
        return cleaned.strip()

    @classmethod
    def extract_price_and_currency(
        cls, text: Optional[str], default_currency: str = "USD"
    ) -> Tuple[Optional[float], str]:
        """
        Extract numerical price and detect currency from strings like:
        "$349.99", "EUR 240,50", "₹7,499", "£ 120.00", "450.00 USD"
        """
        if not text:
            return None, default_currency

        cleaned = cls.clean_text(text)
        detected_currency = default_currency

        # 1. Detect currency by symbol or ISO word
        for symbol, curr_code in CURRENCY_SYMBOLS.items():
            if symbol in cleaned:
                detected_currency = curr_code
                break
        else:
            iso_match = re.search(r"\b(USD|EUR|GBP|INR|CAD|AUD|JPY)\b", cleaned, re.IGNORECASE)
            if iso_match:
                detected_currency = iso_match.group(1).upper()

        # 2. Extract price digits with decimal/comma logic
        # Matches patterns like 1,234.56 or 1.234,56 or 1234 or 12.34
        # Remove currency words/symbols
        cleaned_no_sym = re.sub(r"[^\d.,]", "", cleaned)
        if not cleaned_no_sym:
            return None, detected_currency

        # Determine if comma or period is the decimal separator
        # Case A: "1,250.50" -> standard US/UK format
        if "," in cleaned_no_sym and "." in cleaned_no_sym:
            if cleaned_no_sym.rfind(".") > cleaned_no_sym.rfind(","):
                # comma is thousands, period is decimal
                cleaned_no_sym = cleaned_no_sym.replace(",", "")
            else:
                # period is thousands, comma is decimal (European format)
                cleaned_no_sym = cleaned_no_sym.replace(".", "").replace(",", ".")
        elif "," in cleaned_no_sym:
            # Check if comma represents decimal e.g. "24,99" or thousands e.g. "7,499"
            parts = cleaned_no_sym.split(",")
            if len(parts) == 2 and len(parts[1]) == 2:
                # Likely decimal "24,99"
                cleaned_no_sym = cleaned_no_sym.replace(",", ".")
            else:
                cleaned_no_sym = cleaned_no_sym.replace(",", "")

        try:
            val = float(cleaned_no_sym)
            return round(val, 2), detected_currency
        except ValueError:
            return None, detected_currency

    @classmethod
    def extract_duration(cls, text: Optional[str]) -> str:
        """Extract duration string like '7h 15m' or '2h' or '45m'."""
        if not text:
            return "N/A"
        cleaned = cls.clean_text(text)
        match = re.search(r"(\d+\s*h(?:ours?)?)?\s*(\d+\s*m(?:in(?:utes?)?)?)?", cleaned, re.IGNORECASE)
        if match and (match.group(1) or match.group(2)):
            h = match.group(1) or ""
            m = match.group(2) or ""
            # Standardize to "Xh Ym"
            h_clean = re.sub(r"[^\d]", "", h)
            m_clean = re.sub(r"[^\d]", "", m)
            res = []
            if h_clean:
                res.append(f"{h_clean}h")
            if m_clean:
                res.append(f"{m_clean}m")
            return " ".join(res) if res else cleaned
        return cleaned

    @classmethod
    def extract_stops(cls, text: Optional[str]) -> Tuple[int, str]:
        """
        Extract number of stops and descriptor.
        Returns: (stops_count, descriptor_string)
        e.g., "Nonstop" -> (0, "Nonstop")
        "1 stop via FRA" -> (1, "1 stop via FRA")
        """
        if not text:
            return 0, "Nonstop"
        cleaned = cls.clean_text(text)
        if re.search(r"\b(non-?stop|direct)\b", cleaned, re.IGNORECASE):
            return 0, "Nonstop"

        stop_match = re.search(r"(\d+)\s*stop", cleaned, re.IGNORECASE)
        if stop_match:
            count = int(stop_match.group(1))
            return count, cleaned

        return 0, cleaned

    @classmethod
    def extract_airport_code(cls, text: Optional[str]) -> Optional[str]:
        """Extract 3-letter IATA code, e.g. 'JFK' from 'New York (JFK)'."""
        if not text:
            return None
        match = re.search(r"\b([A-Z]{3})\b", text)
        return match.group(1) if match else None

    @classmethod
    def safe_select_text(cls, element: Tag, selector: str, default: str = "") -> str:
        """Safely find an element by CSS selector and extract stripped text."""
        node = element.select_one(selector)
        return cls.clean_text(node.get_text()) if node else default
