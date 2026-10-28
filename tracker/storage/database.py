import sqlite3
import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union
from contextlib import contextmanager

from tracker.config import DEFAULT_DB_PATH
from tracker.models import FlightItem, ProductItem, PriceAlert

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    SQLite-based price tracking storage engine.
    Maintains historical price points, item metadata, and threshold alerts.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._init_db()

    @contextmanager
    def _connection(self):
        """Context manager that ensures transaction commit and connection closure."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Create necessary tables if they do not exist."""
        with self._connection() as conn:
            cursor = conn.cursor()

            # 1. Flights table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flights (
                    identifier TEXT PRIMARY KEY,
                    airline TEXT NOT NULL,
                    flight_number TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_time TEXT,
                    arrival_time TEXT,
                    duration TEXT,
                    stops INTEGER DEFAULT 0,
                    stop_details TEXT,
                    cabin_class TEXT,
                    latest_price REAL NOT NULL,
                    currency TEXT NOT NULL,
                    booking_url TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Flight price history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flight_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flight_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    currency TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (flight_id) REFERENCES flights (identifier)
                )
            """)

            # 3. Products table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    identifier TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    sku TEXT,
                    site_name TEXT,
                    url TEXT,
                    latest_price REAL NOT NULL,
                    original_price REAL,
                    currency TEXT NOT NULL,
                    in_stock BOOLEAN DEFAULT 1,
                    rating REAL,
                    reviews_count INTEGER,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 4. Product price history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    currency TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products (identifier)
                )
            """)

            # 5. Price alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id TEXT NOT NULL,
                    target_type TEXT NOT NULL, -- 'flight' or 'product'
                    target_name TEXT NOT NULL,
                    target_price REAL NOT NULL,
                    currency TEXT NOT NULL,
                    active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    # --- Flight Operations ---

    def record_flight(self, flight: FlightItem) -> Tuple[bool, Optional[float]]:
        """
        Inserts or updates flight record and adds an entry to flight_price_history.
        Returns: (is_price_drop, price_diff)
        """
        is_drop = False
        price_diff = None

        with self._connection() as conn:
            cursor = conn.cursor()
            fid = flight.flight_identifier

            # Check existing flight
            cursor.execute("SELECT latest_price FROM flights WHERE identifier = ?", (fid,))
            row = cursor.fetchone()

            if row:
                old_price = row["latest_price"]
                price_diff = flight.price - old_price
                if flight.price < old_price:
                    is_drop = True

                cursor.execute("""
                    UPDATE flights SET
                        airline = ?, flight_number = ?, origin = ?, destination = ?,
                        departure_time = ?, arrival_time = ?, duration = ?, stops = ?,
                        stop_details = ?, cabin_class = ?, latest_price = ?, currency = ?,
                        booking_url = ?, last_updated = ?
                    WHERE identifier = ?
                """, (
                    flight.airline, flight.flight_number, flight.origin, flight.destination,
                    flight.departure_time, flight.arrival_time, flight.duration, flight.stops,
                    flight.stop_details, flight.cabin_class, flight.price, flight.currency,
                    flight.booking_url, datetime.utcnow(), fid
                ))
            else:
                cursor.execute("""
                    INSERT INTO flights (
                        identifier, airline, flight_number, origin, destination,
                        departure_time, arrival_time, duration, stops, stop_details,
                        cabin_class, latest_price, currency, booking_url, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fid, flight.airline, flight.flight_number, flight.origin, flight.destination,
                    flight.departure_time, flight.arrival_time, flight.duration, flight.stops,
                    flight.stop_details, flight.cabin_class, flight.price, flight.currency,
                    flight.booking_url, datetime.utcnow()
                ))

            # Record history point
            cursor.execute("""
                INSERT INTO flight_price_history (flight_id, price, currency, timestamp)
                VALUES (?, ?, ?, ?)
            """, (fid, flight.price, flight.currency, datetime.utcnow()))

        return is_drop, price_diff

    def get_tracked_flights(self) -> List[Dict[str, Any]]:
        """Retrieve all currently tracked flights with summary statistics."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT f.*,
                       MIN(h.price) AS lowest_price,
                       MAX(h.price) AS highest_price,
                       ROUND(AVG(h.price), 2) AS average_price,
                       COUNT(h.id) AS data_points
                FROM flights f
                LEFT JOIN flight_price_history h ON f.identifier = h.flight_id
                GROUP BY f.identifier
                ORDER BY f.last_updated DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_flight_history(self, flight_id: str) -> List[Dict[str, Any]]:
        """Retrieve historical price records for a specific flight."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT price, currency, timestamp
                FROM flight_price_history
                WHERE flight_id = ?
                ORDER BY timestamp ASC
            """, (flight_id,))
            return [dict(row) for row in cursor.fetchall()]

    # --- Product Operations ---

    def record_product(self, product: ProductItem) -> Tuple[bool, Optional[float]]:
        """
        Inserts or updates product record and logs history point.
        Returns: (is_price_drop, price_diff)
        """
        is_drop = False
        price_diff = None

        with self._connection() as conn:
            cursor = conn.cursor()
            pid = product.product_identifier

            cursor.execute("SELECT latest_price FROM products WHERE identifier = ?", (pid,))
            row = cursor.fetchone()

            if row:
                old_price = row["latest_price"]
                price_diff = product.price - old_price
                if product.price < old_price:
                    is_drop = True

                cursor.execute("""
                    UPDATE products SET
                        title = ?, sku = ?, site_name = ?, url = ?, latest_price = ?,
                        original_price = ?, currency = ?, in_stock = ?, rating = ?,
                        reviews_count = ?, last_updated = ?
                    WHERE identifier = ?
                """, (
                    product.title, product.sku, product.site_name, product.url,
                    product.price, product.original_price, product.currency,
                    product.in_stock, product.rating, product.reviews_count,
                    datetime.utcnow(), pid
                ))
            else:
                cursor.execute("""
                    INSERT INTO products (
                        identifier, title, sku, site_name, url, latest_price,
                        original_price, currency, in_stock, rating, reviews_count, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pid, product.title, product.sku, product.site_name, product.url,
                    product.price, product.original_price, product.currency,
                    product.in_stock, product.rating, product.reviews_count, datetime.utcnow()
                ))

            # Record history
            cursor.execute("""
                INSERT INTO product_price_history (product_id, price, currency, timestamp)
                VALUES (?, ?, ?, ?)
            """, (pid, product.price, product.currency, datetime.utcnow()))

        return is_drop, price_diff

    def get_tracked_products(self) -> List[Dict[str, Any]]:
        """Retrieve all currently tracked products with price stats."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*,
                       MIN(h.price) AS lowest_price,
                       MAX(h.price) AS highest_price,
                       ROUND(AVG(h.price), 2) AS average_price,
                       COUNT(h.id) AS data_points
                FROM products p
                LEFT JOIN product_price_history h ON p.identifier = h.product_id
                GROUP BY p.identifier
                ORDER BY p.last_updated DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_product_history(self, product_id: str) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT price, currency, timestamp
                FROM product_price_history
                WHERE product_id = ?
                ORDER BY timestamp ASC
            """, (product_id,))
            return [dict(row) for row in cursor.fetchall()]

    # --- Alerts Operations ---

    def create_alert(
        self, target_id: str, target_type: str, target_name: str, target_price: float, currency: str = "USD"
    ) -> int:
        """Create a target price drop alert."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO price_alerts (target_id, target_type, target_name, target_price, currency, active)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (target_id, target_type, target_name, target_price, currency))
            return cursor.lastrowid

    def check_triggered_alerts(self) -> List[Dict[str, Any]]:
        """
        Check for any active alerts whose current price is at or below the target threshold.
        """
        triggered = []
        with self._connection() as conn:
            cursor = conn.cursor()

            # Check flight alerts
            cursor.execute("""
                SELECT a.id, a.target_id, a.target_name, a.target_price, a.currency,
                       f.latest_price, 'flight' AS target_type
                FROM price_alerts a
                JOIN flights f ON a.target_id = f.identifier
                WHERE a.active = 1 AND f.latest_price <= a.target_price
            """)
            for row in cursor.fetchall():
                triggered.append(dict(row))

            # Check product alerts
            cursor.execute("""
                SELECT a.id, a.target_id, a.target_name, a.target_price, a.currency,
                       p.latest_price, 'product' AS target_type
                FROM price_alerts a
                JOIN products p ON a.target_id = p.identifier
                WHERE a.active = 1 AND p.latest_price <= a.target_price
            """)
            for row in cursor.fetchall():
                triggered.append(dict(row))

        return triggered

    def get_all_alerts(self) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM price_alerts ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def delete_alert(self, alert_id: int) -> bool:
        """Deletes a price alert by ID. Returns True if an alert was deleted."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM price_alerts WHERE id = ?", (alert_id,))
            return cursor.rowcount > 0

    def toggle_alert(self, alert_id: int, active: Optional[bool] = None) -> bool:
        """Toggles or sets the active state of an alert. Returns True if updated."""
        with self._connection() as conn:
            cursor = conn.cursor()
            if active is not None:
                cursor.execute("UPDATE price_alerts SET active = ? WHERE id = ?", (1 if active else 0, alert_id))
            else:
                cursor.execute(
                    "UPDATE price_alerts SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END WHERE id = ?",
                    (alert_id,),
                )
            return cursor.rowcount > 0

    def delete_flight(self, flight_id: str) -> bool:
        """Removes a flight and all its associated price history points and alerts."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM flight_price_history WHERE flight_id = ?", (flight_id,))
            cursor.execute("DELETE FROM price_alerts WHERE target_id = ? AND target_type = 'flight'", (flight_id,))
            cursor.execute("DELETE FROM flights WHERE identifier = ?", (flight_id,))
            return cursor.rowcount > 0

    def delete_product(self, product_id: str) -> bool:
        """Removes a product and all its associated price history points and alerts."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM product_price_history WHERE product_id = ?", (product_id,))
            cursor.execute("DELETE FROM price_alerts WHERE target_id = ? AND target_type = 'product'", (product_id,))
            cursor.execute("DELETE FROM products WHERE identifier = ?", (product_id,))
            return cursor.rowcount > 0

    def get_trend_analytics(self, target_id: str, target_type: str = "flight") -> Dict[str, Any]:
        """
        Calculates price volatility, overall change %, and drop count for a tracked item.
        """
        if target_type == "flight":
            history = self.get_flight_history(target_id)
        else:
            history = self.get_product_history(target_id)

        if not history:
            return {
                "target_id": target_id,
                "data_points": 0,
                "first_price": None,
                "latest_price": None,
                "lowest_price": None,
                "highest_price": None,
                "price_change": 0.0,
                "price_change_pct": 0.0,
                "drops_count": 0,
            }

        prices = [h["price"] for h in history]
        first_price = prices[0]
        latest_price = prices[-1]
        lowest_price = min(prices)
        highest_price = max(prices)
        change = latest_price - first_price
        change_pct = round((change / first_price) * 100, 2) if first_price > 0 else 0.0

        drops_count = 0
        for i in range(1, len(prices)):
            if prices[i] < prices[i - 1]:
                drops_count += 1

        return {
            "target_id": target_id,
            "data_points": len(prices),
            "first_price": first_price,
            "latest_price": latest_price,
            "lowest_price": lowest_price,
            "highest_price": highest_price,
            "price_change": round(change, 2),
            "price_change_pct": change_pct,
            "drops_count": drops_count,
        }

    def export_to_csv(self, data_type: str, output_path: Union[str, Path], item_id: Optional[str] = None) -> str:
        """
        Exports table or history records to a CSV file.
        data_type can be: 'flights', 'products', 'flight_history', 'product_history', or 'alerts'.
        """
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connection() as conn:
            cursor = conn.cursor()
            if data_type == "flights":
                cursor.execute("SELECT * FROM flights ORDER BY last_updated DESC")
            elif data_type == "products":
                cursor.execute("SELECT * FROM products ORDER BY last_updated DESC")
            elif data_type == "alerts":
                cursor.execute("SELECT * FROM price_alerts ORDER BY created_at DESC")
            elif data_type == "flight_history":
                if item_id:
                    cursor.execute(
                        "SELECT * FROM flight_price_history WHERE flight_id = ? ORDER BY timestamp ASC",
                        (item_id,),
                    )
                else:
                    cursor.execute("SELECT * FROM flight_price_history ORDER BY timestamp ASC")
            elif data_type == "product_history":
                if item_id:
                    cursor.execute(
                        "SELECT * FROM product_price_history WHERE product_id = ? ORDER BY timestamp ASC",
                        (item_id,),
                    )
                else:
                    cursor.execute("SELECT * FROM product_price_history ORDER BY timestamp ASC")
            else:
                raise ValueError(f"Unknown data_type '{data_type}'. Expected flights, products, alerts, flight_history, or product_history.")

            rows = cursor.fetchall()
            if not rows:
                with open(out_path, mode="w", newline="", encoding="utf-8") as f:
                    pass
                return str(out_path)

            headers = [d[0] for d in cursor.description]
            with open(out_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow([row[h] for h in headers])

        return str(out_path)
