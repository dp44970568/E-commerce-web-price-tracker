import unittest
from bs4 import BeautifulSoup
from tracker.parsers.flight_parser import FlightParser
from tracker.mock_server.flight_fixtures import generate_flight_search_html


class TestFlightParser(unittest.TestCase):
    def setUp(self):
        self.parser = FlightParser()

    def test_parse_mock_search_results(self):
        html = generate_flight_search_html(origin="JFK", destination="LHR", currency="USD")
        soup = BeautifulSoup(html, "lxml")
        flights = self.parser.parse(soup)

        self.assertGreaterEqual(len(flights), 4)

        # Verify attributes on first flight
        f1 = flights[0]
        self.assertTrue(len(f1.airline) > 0)
        self.assertTrue(len(f1.flight_number) > 0)
        self.assertEqual(f1.origin, "JFK")
        self.assertEqual(f1.destination, "LHR")
        self.assertEqual(f1.currency, "USD")
        self.assertGreater(f1.price, 0)
        self.assertIn(":", f1.departure_time)
        self.assertIn(":", f1.arrival_time)
        self.assertTrue(f1.duration != "N/A")

    def test_parse_custom_markup(self):
        sample_html = """
        <div class="flight-card">
            <span class="airline-name">Delta Air Lines</span>
            <span class="flight-no">DL 402</span>
            <span class="dep-time">08:00 AM</span>
            <span class="origin-code">BOS</span>
            <span class="arr-time">11:15 AM</span>
            <span class="dest-code">MIA</span>
            <span class="duration">3h 15m</span>
            <span class="stops">Nonstop</span>
            <span class="price">$285.50</span>
        </div>
        """
        flights = self.parser.parse(sample_html)
        self.assertEqual(len(flights), 1)
        flight = flights[0]
        self.assertEqual(flight.airline, "Delta Air Lines")
        self.assertEqual(flight.flight_number, "DL 402")
        self.assertEqual(flight.price, 285.50)
        self.assertEqual(flight.currency, "USD")
        self.assertEqual(flight.origin, "BOS")
        self.assertEqual(flight.destination, "MIA")
        self.assertEqual(flight.stops, 0)


if __name__ == "__main__":
    unittest.main()
