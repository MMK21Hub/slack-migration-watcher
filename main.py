from logging import basicConfig, debug, error, info, warning
from sys import stderr
from time import sleep
from traceback import format_exc
from argparse import ArgumentParser
from prometheus_client import start_http_server, Gauge
from bs4 import BeautifulSoup
import requests

from api_client import AreWeThereYetAPIClient


ARE_WE_THERE_YET = "https://are-we-there-yet.hackclub.com/"


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=9070,
        help="the port to run the Prometheus exporter on",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        help="set the logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="how often to scrape data, in seconds",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=ARE_WE_THERE_YET,
        help="the base URL for the are-we-there-yet website",
    )
    args = parser.parse_args()
    basicConfig(level=args.log_level)

    start_http_server(args.port)
    print(f"Started metrics exporter: http://localhost:{args.port}/metrics", flush=True)

    has_had_success = False
    progress_gauge = Gauge(
        "slack_migration_progress_ratio",
        "Current slack migration progress (0.0 to 1.0)",
        unit="ratio",
    )

    api = AreWeThereYetAPIClient(args.url)

    while True:
        try:
            status = api.fetch_status()
            progress_percent = status.migration_data.percent_completed
            info("Current progress = %.2f%%", progress_percent)
            progress_gauge.set(progress_percent / 100.0)
            has_had_success = True
        except Exception as e:
            # Exit the program if the first fetch fails
            if not has_had_success:
                raise e
            error(f"Failed to fetch data: {format_exc()}")
        finally:
            sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
