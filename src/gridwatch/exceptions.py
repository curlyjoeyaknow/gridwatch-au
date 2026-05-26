"""Exception hierarchy — one base so callers can catch broadly or precisely.

The CLI catches `GridWatchError` per action so a failure degrades to a message
instead of a crash; lower layers raise the specific subclass.
"""


class GridWatchError(Exception):
    """Base for every error this system raises on purpose."""


class DataSourceError(GridWatchError):
    """A data source failed: network, non-200, malformed/partial payload, bad region."""


class ValidationError(GridWatchError):
    """Caller-supplied data is invalid (bad region code, value, date, interval)."""


class RegionNotFoundError(GridWatchError):
    """An operation referenced a region that is not loaded in the manager."""


class PersistenceError(GridWatchError):
    """Saving or loading a dataset failed (I/O error, corrupt file)."""
