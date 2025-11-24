from logging import basicConfig, debug, error, info, warning
from sys import stderr
from time import sleep
from traceback import format_exc
from argparse import ArgumentParser
from prometheus_client import start_http_server, Gauge
from bs4 import BeautifulSoup
import requests


ARE_WE_THERE_YET = "https://are-we-there-yet.hackclub.com/"


def fetch_progress(url: str) -> float:
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text)
    debug("Fetched page: %s", response.text.replace("\n", " "))
    progress_bar = soup.select_one("progress#progress")
    if not progress_bar:
        progress_bar = soup.select_one("progress")
        if not progress_bar:
            raise ValueError("No progress element present on page")
        warning(
            "Strict progressbar selector did not match; successfully fell back to generic element type selector"
        )
    value_str = progress_bar.get("value")
    if value_str is None:
        raise ValueError("Progress element has no value attribute")
    if not isinstance(value_str, str):
        raise ValueError(f"Unexpected type for progress value: {type(value_str)}")
    try:
        value = float(value_str)
    except ValueError as e:
        raise ValueError("Progress element value is not a number") from e
    max_value = progress_bar.get("max") or "1"
    if not isinstance(max_value, str):
        raise ValueError(f"Unexpected type for progress max: {type(max_value)}")
    try:
        max_value_float = float(max_value)
    except ValueError as e:
        raise ValueError("Progress element max is not a number") from e
    if max_value_float == 0:
        raise ValueError("Progress element max is zero")

    progress = value / max_value_float
    debug("Parsed progress: %f (value=%f, max=%f)", progress, value, max_value_float)
    return progress


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
        help="the are-we-there-yet URL to scrape data from",
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

    while True:
        try:
            current_progress = fetch_progress(args.url)
            info("Current progress = %.2f%%", current_progress * 100)
            progress_gauge.set(current_progress)
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
