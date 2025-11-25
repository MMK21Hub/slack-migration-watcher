from logging import debug, warning
from typing import Generic, Literal, TypeVar
from bs4 import BeautifulSoup
from pydantic import BaseModel, field_validator
from enum import Enum
from datetime import datetime, timezone

import requests


class APIError(Exception):
    def __init__(self, error: str):
        super().__init__(f"API returned error: {error}")
        self.error = error


class MigrationState(str, Enum):
    not_started = "not_started"
    complete = "complete"
    paused = "paused"
    scheduled = "scheduled"
    in_progress = "in_progress"
    in_background = "in_background"


class MigrationStatus(BaseModel):
    migration: MigrationState
    users: MigrationState
    files: MigrationState
    dms: MigrationState
    mpdms: MigrationState


class MigrationDetails(BaseModel):
    date_scheduled: datetime
    date_finished: datetime
    date_started: datetime

    @field_validator("date_scheduled", "date_finished", "date_started", mode="before")
    def convert_epoch(cls, v):
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v, tz=timezone.utc)
        return v


class MigrationData(BaseModel):
    ok: Literal[True]
    migration_id: int
    status: MigrationStatus
    percent_completed: float  # 0.0 to 100.0
    migration_details: MigrationDetails


class MigrationDataError(BaseModel):
    ok: Literal[False]
    error: str


T = TypeVar("T", MigrationData, MigrationDataError)


class StatusResponse(BaseModel, Generic[T]):
    migration_data: T
    last_updated: datetime


class AreWeThereYetAPIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def scrape_progress(self) -> float:
        response = requests.get(self.base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, features="html.parser")
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
        debug(
            "Parsed progress: %f (value=%f, max=%f)", progress, value, max_value_float
        )
        return progress

    def fetch_status(self) -> StatusResponse[MigrationData]:
        response = requests.get(self.base_url + "/api/status")
        response.raise_for_status()
        status = StatusResponse.model_validate_json(response.text)
        match status.migration_data:
            case MigrationData():
                return status
            case MigrationDataError():
                raise APIError(status.migration_data.error)
            case _:
                # This should never happen
                raise TypeError("Unexpected type for migration_data")
