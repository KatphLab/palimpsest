"""Tests for shared model validation primitives."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from models.common import SessionStatus, StrictBaseModel, UTCDateTime
from utils.time import utc_now


class ExampleModel(StrictBaseModel):
    """Simple model used to verify shared validation rules."""

    status: SessionStatus
    occurred_at: UTCDateTime


def test_strict_base_model_forbids_extra_fields() -> None:
    """Shared models must reject undeclared fields."""

    with pytest.raises(ValidationError):
        ExampleModel.model_validate(
            {
                "status": "created",
                "occurred_at": utc_now(),
                "unexpected": "value",
            }
        )


def test_utc_datetime_normalizes_to_utc() -> None:
    """Shared timestamp fields must round-trip as UTC values."""

    model = ExampleModel.model_validate(
        {
            "status": "running",
            "occurred_at": datetime(
                2026, 4, 6, 12, 0, tzinfo=timezone(timedelta(hours=2))
            ),
        }
    )

    assert model.status is SessionStatus.RUNNING
    assert model.occurred_at.tzinfo == timezone.utc
    assert model.occurred_at.hour == 10


def test_enum_field_rejects_invalid_value() -> None:
    """Shared enum fields must fail validation for invalid values."""

    with pytest.raises(ValidationError):
        ExampleModel.model_validate(
            {
                "status": "not-a-status",
                "occurred_at": utc_now(),
            }
        )
