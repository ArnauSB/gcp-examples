import os
import sys
import time
import socket
import logging
import argparse
from typing import List
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed

import requests
from prometheus_client import Counter  # type: ignore
from prometheus_client import Histogram  # type: ignore
from prometheus_client import start_http_server  # type: ignore

REQ_DURATION = Histogram(
    name="app_loadgen_request_duration",
    documentation="Duration of requests sent to the endpoint URL",
    labelnames=["service", "schema"],
)
REQ_COUNT = Counter(
    name="app_loadgen_request_count",
    documentation="Count of requests by response code",
    labelnames=["service", "schema", "code"],
)
DEFAULT_REQUEST_RATE_RPS = 10.0
MAX_CONCURRENT_WORKERS = 2
LOGGER_NAME = "loadgen"

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(LOGGER_NAME)

def fetch(url: str, freq: float) -> None:
    """
    Do a GET request to the URL and register metrics.
    """
    start = time.time()
    
    try:
        parsed_url = urlparse(url)
        schema = parsed_url.scheme
        service = parsed_url.netloc.split(":")[0].split(".")[0] 
        if not service:
            service = "unknown_host"
    except Exception as e:
        logger.warning("Could not parse URL: %s. Using default labels. Error: %s", url, e)
        service = "malformed_url"
        schema = "unknown"

    try:
        # pylint: disable=C0103
        r = requests.get(url, allow_redirects=True, timeout=3, verify=True) 
        REQ_COUNT.labels(service, schema, r.status_code).inc()
    except (requests.exceptions.RequestException, socket.timeout) as e: 
        REQ_COUNT.labels(service, schema, "502").inc()
        logger.error(
            "The target is unreachable or timed out (%s): %s", url, e)
        
    end = time.time()
    REQ_DURATION.labels(service, schema).observe(end - start)
    
    time.sleep(freq)

def load_urls(urls_file_path: str) -> List[str]:
    """Load URLs from file"""
    try:
        with open(urls_file_path, "r") as txt_file:
            urls: List[str] = [line.strip() for line in txt_file if line.strip()]
        
        if not urls:
            logger.warning("URL list read from file is empty.")
            sys.exit(0)
        return urls
            
    except FileNotFoundError:
        logger.error("URL file not found at %s. Exiting.", urls_file_path)
        sys.exit(1)
    except Exception as e:
        logger.error("Error reading URL file: %s. Exiting.", e)
        sys.exit(1)

def parse_args() -> argparse.Namespace:
    """Configure and parse args"""
    parser = argparse.ArgumentParser(
        description="A concurrent load generator that exposes Prometheus metrics."
    )
    parser.add_argument(
        '-r', '--rate', 
        type=float, 
        default=DEFAULT_REQUEST_RATE_RPS,
        help=f"Target request rate in Requests Per Second (RPS). Default: {DEFAULT_REQUEST_RATE_RPS}"
    )
    parser.add_argument(
        '-w', '--workers', 
        type=int, 
        default=MAX_CONCURRENT_WORKERS,
        help=f"Maximum number of concurrent worker threads. Default: {MAX_CONCURRENT_WORKERS}"
    )
    return parser.parse_args()

def main() -> None:
    # 1. Parse args and configure
    args = parse_args()
    logger.setLevel(logging.INFO)
    
    # 2. Get file with the URLs and configure env var
    urls_file_path = os.getenv('URLS_LIST')
    if not urls_file_path:
        logger.error("URLS_LIST environment variable not set. Exiting.")
        sys.exit(1)
    
    URLS = load_urls(urls_file_path)

    # 3. Concurrency and rate
    request_rate_rps = args.rate
    max_workers = args.workers
    
    # Wait frequence between requests by thread
    freq: float = 1 / request_rate_rps 

    # 4. Start metrics server
    metrics_port = 9090
    start_http_server(metrics_port)
    logger.info("Prometheus metrics server started on port %d.", metrics_port)
    logger.info("Starting concurrent load generation for %d URLs:", len(URLS))
    logger.info("Target Rate (RPS): %.2f | Concurrent Workers: %d", request_rate_rps, max_workers)
    
    # 5. Load generator
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while True:
            futures = []
            
            for url in URLS:
                futures.append(executor.submit(fetch, url, freq))
            
            for future in as_completed(futures, timeout=None):
                try:
                    future.result() 
                except Exception as exc:
                    logger.warning("Task generated an exception: %s", exc)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Load generator stopped by user (KeyboardInterrupt).")
        sys.exit(0)
    except Exception as e:
        logger.critical("An unhandled exception occurred: %s", e, exc_info=True)
        sys.exit(1)
