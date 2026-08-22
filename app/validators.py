"""
validators.py
=============
Standalone input-validation helpers that can be imported by both the GUI
layer and by unit-tests without pulling in any Qt dependency.
"""

from __future__ import annotations


def validate_time_range(start_time: int, stop_time: int) -> tuple[bool, str]:
    """
    Check whether *start_time* and *stop_time* satisfy the task constraints.

    Constraints
    -----------
    * ``0 <= start_time``
    * ``start_time < stop_time``
    * ``stop_time < 5``

    Parameters
    ----------
    start_time : int
        Proposed simulation start time.
    stop_time : int
        Proposed simulation stop time.

    Returns
    -------
    tuple[bool, str]
        ``(True, "")`` when valid, or ``(False, reason)`` on the first
        violated constraint.

    Examples
    --------
    >>> validate_time_range(0, 3)
    (True, '')
    >>> validate_time_range(3, 3)
    (False, 'start_time (3) must be strictly less than stop_time (3).')
    """
    if start_time < 0:
        return False, f"start_time must be >= 0, got {start_time}."
    if start_time >= stop_time:
        return (
            False,
            f"start_time ({start_time}) must be strictly less than "
            f"stop_time ({stop_time}).",
        )
    if stop_time >= 5:
        return False, f"stop_time must be < 5, got {stop_time}."
    return True, ""
