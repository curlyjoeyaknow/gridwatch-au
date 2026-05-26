"""Row -> Reading rehydration for the file repositories.

The canonical implementation lives with the contracts (`contracts.readings`); this
module re-exports it so the repositories share one definition (ADR-003/004).
"""

from gridwatch.contracts.readings import reading_from_row

__all__ = ["reading_from_row"]
