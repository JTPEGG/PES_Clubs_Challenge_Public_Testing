"""Pure season invariants for the PES 2.0 persistent-world prototype.

Independent of Flask/database; safe to test before integration.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Fixture:
    round_no: int
    home: str
    away: str


def validate_double_round_robin(clubs, fixtures):
    """Return errors; [] means a complete, balanced, valid double round robin.

    This validates the *entire league*, not only the user's team's matches.
    """
    errors = []
    clubs = list(clubs)
    expected = set(clubs)
    if len(expected) != len(clubs) or len(clubs) < 2 or len(clubs) % 2:
        return ["Club list must be unique and contain an even number >= 2"]
    expected_rounds = 2 * (len(clubs) - 1)
    by_round = {}
    ordered_pairs = Counter()
    for fixture in fixtures:
        if fixture.home not in expected or fixture.away not in expected:
            errors.append(f"Round {fixture.round_no}: unknown club")
            continue
        if fixture.home == fixture.away:
            errors.append(f"Round {fixture.round_no}: self fixture")
            continue
        if not (1 <= fixture.round_no <= expected_rounds):
            errors.append(f"Invalid round: {fixture.round_no}")
        by_round.setdefault(fixture.round_no, []).extend([fixture.home, fixture.away])
        ordered_pairs[(fixture.home, fixture.away)] += 1
    for round_no in range(1, expected_rounds + 1):
        appearances = Counter(by_round.get(round_no, []))
        if set(appearances) != expected or any(v != 1 for v in appearances.values()):
            errors.append(f"Round {round_no}: missing or duplicate clubs")
    for home in clubs:
        for away in clubs:
            if home != away and ordered_pairs[(home, away)] != 1:
                errors.append(f"Expected exactly one {home} home vs {away}")
    return errors


def first_allowed_registration_date(agreement_date, season_start_date, next_season_registration_date, affects_active_pes_league):
    """A deal agreed once the PES league is created cannot alter its squads.

    season_start_date is the League Mode creation/lock date, not necessarily
    the first real-world match date. Assumes all dates are date objects.
    """
    if not all(isinstance(d, date) for d in (agreement_date, season_start_date, next_season_registration_date)):
        raise TypeError("Dates must be datetime.date values")
    if next_season_registration_date <= season_start_date:
        raise ValueError("Next registration date must follow season lock")
    if affects_active_pes_league and agreement_date >= season_start_date:
        return max(agreement_date, next_season_registration_date)
    return agreement_date
