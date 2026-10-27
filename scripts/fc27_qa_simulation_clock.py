"""Isolated FC27 QA logical clock. Never used for production or user careers.

The 659-club simulation intentionally advances 12 market moments in an
audited 30-minute virtual interval. On expanded market workloads, evaluating
all eligible clubs can exceed 30 real minutes. The production market must
enforce real deadlines; the isolated QA must apply the saved due-time to
lower-level nested offer/agent guards that otherwise use wall-clock time.
"""
from contextlib import contextmanager
from unittest.mock import patch
import world_preseason_window as _preseason_clock


@contextmanager
def isolated_simulation_clock(moment):
    """Temporarily bind implicit deadline reads to a QA market moment."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("QA market moment must be timezone-aware")
    actual_utc=_preseason_clock._utc
    with patch.object(_preseason_clock,"_utc",
        side_effect=lambda explicit=None: actual_utc(
            moment if explicit is None else explicit)):
        yield
