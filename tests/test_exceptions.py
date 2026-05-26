import pytest

from gridwatch.exceptions import (
    DataSourceError,
    GridWatchError,
    PersistenceError,
    RegionNotFoundError,
    ValidationError,
)


@pytest.mark.parametrize(
    "exc",
    [DataSourceError, ValidationError, RegionNotFoundError, PersistenceError],
)
def test_every_error_subclasses_the_base(exc):
    assert issubclass(exc, GridWatchError)


@pytest.mark.parametrize(
    "exc",
    [DataSourceError, ValidationError, RegionNotFoundError, PersistenceError],
)
def test_caught_by_base(exc):
    with pytest.raises(GridWatchError):
        raise exc("boom")
