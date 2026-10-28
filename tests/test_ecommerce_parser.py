import unittest
from bs4 import BeautifulSoup
from tracker.parsers.ecommerce_parser import EcommerceParser
from tracker.mock_server.server import MOCK_PRODUCT_HTML, MOCK_CATALOG_HTML


class TestEcommerceParser(unittest.TestCase):
    def setUp(self):
        self.parser = EcommerceParser()

    def test_parse_single_product(self):
        product = self.parser.parse_single_product(
            MOCK_PRODUCT_HTML, page_url="http://test.com/product/1", site_name="TechStore"
        )
        self.assertIsNotNone(product)
        self.assertEqual(product.title, "Sony WH-1000XM5 Wireless Noise Canceling Headphones")
        self.assertEqual(product.price, 328.00)
        self.assertEqual(product.original_price, 399.99)
        self.assertEqual(product.currency, "USD")
        self.assertEqual(product.rating, 4.7)
        self.assertEqual(product.reviews_count, 8429)
        self.assertTrue(product.in_stock)
        self.assertIn(product.sku, ["B09XS7JWHH", "SONY-XM5-BLK"])

    def test_parse_catalog(self):
        items = self.parser.parse_listing_page(MOCK_CATALOG_HTML, base_url="http://test.com")
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].title, "Sony WH-1000XM5 Headphones")
        self.assertEqual(items[0].price, 328.00)
        self.assertEqual(items[1].title, "Apple MacBook Air M3 15-inch")
        self.assertEqual(items[1].price, 1199.00)


if __name__ == "__main__":
    unittest.main()
