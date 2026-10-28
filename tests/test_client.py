import unittest
import time
from tracker.client import HttpClient
from tracker.mock_server.server import MockServerThread


class TestHttpClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = MockServerThread(port=8912)
        cls.server.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_http_get_and_soup(self):
        client = HttpClient()
        soup = client.get_soup("http://127.0.0.1:8912/flights?from=JFK&to=LHR")
        cards = soup.select(".flight-card")
        self.assertGreater(len(cards), 0)
        client.close()

    def test_headers_and_user_agent(self):
        client = HttpClient()
        headers = client._get_random_headers()
        self.assertIn("User-Agent", headers)
        self.assertIn("Accept", headers)
        client.close()


if __name__ == "__main__":
    unittest.main()
