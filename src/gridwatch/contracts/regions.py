"""NEM region codes — the scope boundary.

Western Australia (SWIS) and the NT are not in the NEM and are out of scope.
"""

from gridwatch.exceptions import ValidationError

REGION_NAMES = {
    "NSW1": "New South Wales",
    "QLD1": "Queensland",
    "VIC1": "Victoria",
    "SA1": "South Australia",
    "TAS1": "Tasmania",
}

NEM_REGIONS = tuple(REGION_NAMES)


def is_valid_region(code: str) -> bool:
    return isinstance(code, str) and code.strip().upper() in REGION_NAMES


def validate_region(code: str) -> str:
    """Normalise and validate a region code, or raise ValidationError."""
    if not isinstance(code, str) or not code.strip():
        raise ValidationError("region code must be a non-empty string")
    normalised = code.strip().upper()
    if normalised not in REGION_NAMES:
        raise ValidationError(
            f"unknown region {code!r}; valid NEM regions are {', '.join(NEM_REGIONS)}"
        )
    return normalised


def region_name(code: str) -> str:
    return REGION_NAMES.get(validate_region(code), code)
