from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class FlightItem:
    """Represents an extracted flight itinerary and pricing offer."""
    airline: str
    flight_number: str
    origin: str                     # e.g., "JFK" or "New York"
    destination: str                # e.g., "LHR" or "London"
    departure_time: str             # e.g., "08:30" or "08:30 AM"
    arrival_time: str               # e.g., "20:45" or "08:45 PM"
    price: float                    # Clean numeric price
    currency: str = "USD"           # ISO code (USD, EUR, GBP, INR, etc.)
    duration: str = "N/A"           # e.g., "7h 15m"
    stops: int = 0                  # 0 = nonstop, 1 = 1 stop, etc.
    stop_details: str = "Nonstop"   # e.g., "1 stop (CDG - 1h 45m)"
    cabin_class: str = "Economy"    # Economy, Premium, Business, First
    booking_url: Optional[str] = None
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def flight_identifier(self) -> str:
        """Unique compound ID for tracking this exact route & flight over time."""
        clean_num = self.flight_number.replace(" ", "").upper()
        return f"{self.airline}_{clean_num}_{self.origin}_{self.destination}".replace(" ", "_")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flight_identifier": self.flight_identifier,
            "airline": self.airline,
            "flight_number": self.flight_number,
            "origin": self.origin,
            "destination": self.destination,
            "departure_time": self.departure_time,
            "arrival_time": self.arrival_time,
            "duration": self.duration,
            "stops": self.stops,
            "stop_details": self.stop_details,
            "cabin_class": self.cabin_class,
            "price": self.price,
            "currency": self.currency,
            "booking_url": self.booking_url,
            "extracted_at": self.extracted_at.isoformat(),
        }


@dataclass
class ProductItem:
    """Represents an extracted e-commerce product and pricing offer."""
    title: str
    price: float
    currency: str = "USD"
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    in_stock: bool = True
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    sku: Optional[str] = None
    url: Optional[str] = None
    site_name: Optional[str] = None
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def product_identifier(self) -> str:
        if self.sku:
            return f"{self.site_name or 'store'}_{self.sku}"
        import hashlib
        h = hashlib.md5((self.title + (self.url or "")).encode()).hexdigest()[:10]
        return f"PROD_{h}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_identifier": self.product_identifier,
            "title": self.title,
            "price": self.price,
            "currency": self.currency,
            "original_price": self.original_price,
            "discount_percentage": self.discount_percentage,
            "in_stock": self.in_stock,
            "rating": self.rating,
            "reviews_count": self.reviews_count,
            "sku": self.sku,
            "url": self.url,
            "site_name": self.site_name,
            "extracted_at": self.extracted_at.isoformat(),
        }


@dataclass
class PriceAlert:
    """Represents a threshold alert condition."""
    target_id: str
    target_type: str            # 'flight' or 'product'
    target_name: str
    target_price: float
    currency: str
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
