import unittest
from tracker.parsers.base_parser import BaseParser


class TestBaseParser(unittest.TestCase):
    def test_extract_price_and_currency(self):
        cases = [
            ("$349.99", 349.99, "USD"),
            ("€240.50", 240.50, "EUR"),
            ("£ 120.00", 120.00, "GBP"),
            ("₹7,499", 7499.0, "INR"),
            ("1,250.75 USD", 1250.75, "USD"),
            ("EUR 59.90", 59.90, "EUR"),
            ("Free", None, "USD"),
            ("$1,500", 1500.0, "USD"),
        ]
        for text, expected_price, expected_currency in cases:
            p, c = BaseParser.extract_price_and_currency(text)
            self.assertEqual(p, expected_price, f"Failed for {text}")
            self.assertEqual(c, expected_currency, f"Failed currency for {text}")

    def test_extract_duration(self):
        self.assertEqual(BaseParser.extract_duration("7h 15m"), "7h 15m")
        self.assertEqual(BaseParser.extract_duration("11 hours 20 mins"), "11h 20m")
        self.assertEqual(BaseParser.extract_duration("45m"), "45m")
        self.assertEqual(BaseParser.extract_duration("3h"), "3h")

    def test_extract_stops(self):
        count, desc = BaseParser.extract_stops("Nonstop")
        self.assertEqual(count, 0)
        self.assertIn("Nonstop", desc)

        count, desc = BaseParser.extract_stops("1 stop via FRA")
        self.assertEqual(count, 1)

        count, desc = BaseParser.extract_stops("2 stops (ORD, DFW)")
        self.assertEqual(count, 2)

    def test_extract_airport_code(self):
        self.assertEqual(BaseParser.extract_airport_code("New York (JFK)"), "JFK")
        self.assertEqual(BaseParser.extract_airport_code("London LHR"), "LHR")
        self.assertIsNone(BaseParser.extract_airport_code("No airport here"))


if __name__ == "__main__":
    unittest.main()
