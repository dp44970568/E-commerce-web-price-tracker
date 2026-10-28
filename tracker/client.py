import logging
import random
from typing import Optional, Dict, Any, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

from tracker.config import (
    USER_AGENTS,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
    BACKOFF_FACTOR,
    STATUS_FORCELIST,
)

logger = logging.getLogger(__name__)


class HttpClient:
    """
    Robust HTTP Client wrapping requests.Session with:
    - Automatic retries & exponential backoff
    - Randomized user agents to prevent simple bot blocking
    - Standard browser headers emulation
    - Direct integration with BeautifulSoup for HTML parsing
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        proxy: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        parser: str = "lxml",
    ):
        self.timeout = timeout
        self.proxy = proxy
        self.parser = parser
        self.session = requests.Session()

        # Mount robust retry adapter for both http and https
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=STATUS_FORCELIST,
            allowed_methods=["GET", "POST", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default base headers
        self.base_headers = dict(DEFAULT_HEADERS)
        if custom_headers:
            self.base_headers.update(custom_headers)

        if self.proxy:
            self.session.proxies = {"http": self.proxy, "https": self.proxy}

    def _get_random_headers(self) -> Dict[str, str]:
        headers = dict(self.base_headers)
        headers["User-Agent"] = random.choice(USER_AGENTS)
        return headers

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        """Execute a GET request with rotational headers and error handling."""
        req_headers = self._get_random_headers()
        if headers:
            req_headers.update(headers)

        req_timeout = timeout or self.timeout
        try:
            logger.debug(f"Fetching URL: {url} with timeout {req_timeout}s")
            response = self.session.get(
                url,
                params=params,
                headers=req_headers,
                timeout=req_timeout,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error occurred while fetching {url}: {e}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error occurred while fetching {url}: {e}")
            raise
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout occurred while fetching {url}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception for {url}: {e}")
            raise

    def get_soup(
        self,
        url_or_html: str,
        params: Optional[Dict[str, Any]] = None,
        is_html_content: bool = False,
    ) -> BeautifulSoup:
        """
        Fetches a URL and returns a parsed BeautifulSoup object.
        If is_html_content is True, parses the passed string directly.
        """
        if is_html_content:
            raw_html = url_or_html
        else:
            resp = self.get(url_or_html, params=params)
            # Set response encoding properly if detected by requests
            if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding or "utf-8"
            raw_html = resp.text

        try:
            return BeautifulSoup(raw_html, self.parser)
        except Exception:
            # Fallback to standard python html.parser if lxml parser isn't available
            return BeautifulSoup(raw_html, "html.parser")

    def close(self):
        """Close the underlying requests session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
