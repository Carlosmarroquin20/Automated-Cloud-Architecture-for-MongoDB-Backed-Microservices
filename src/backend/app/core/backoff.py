"""Retry delay policy shared by every outbound dependency.

Delays follow a capped exponential ceiling with full jitter: each wait is drawn
uniformly from ``[0, ceiling]``. Processes restarted together, as in a rollout or
after a node failure, would otherwise retry in lockstep under a deterministic
schedule and reach the dependency as synchronized bursts.
"""

from __future__ import annotations

import random
from collections.abc import Iterator

# Upper bound on a single wait so sustained unavailability never stretches
# startup without limit.
MAX_BACKOFF_SECONDS = 10.0


def full_jitter(ceiling: float) -> float:
    # Jitter is a scheduling concern with no security property, so the standard
    # pseudo-random generator is adequate.
    return random.uniform(0.0, ceiling)  # noqa: S311


def backoff_delays(base: float, cap: float = MAX_BACKOFF_SECONDS) -> Iterator[float]:
    """Yield an unbounded sequence of jittered delays under a doubling ceiling."""
    ceiling = base
    while True:
        yield full_jitter(ceiling)
        ceiling = min(ceiling * 2, cap)
