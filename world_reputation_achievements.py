"""Temporary sporting-opportunity bonuses for sourced season achievements.

All scores are deliberate gameplay assumptions, NOT UEFA eligibility rules,
financial forecasts, or evidence of real-world trophies.

Bonuses attach to the NEXT season only and must never be added every year.
Actual eligibility is explicitly sourced, not inferred from finishing third,
winning a cup, or a particular federation's allocation rules.
"""

MODEL_VERSION = "rep-season-opportunities-v1"
DOMESTIC_CUPS = {
    "none": 0,
    "fa_cup": 3,
    "league_cup": 2,
}
EUROPEAN_ACCESS = {
    "none": 0,
    "champions_league": 5,
    "europa_league": 3,
    "conference_league": 2,
}
EUROPEAN_TROPHIES = {
    "none": 0,
    "champions_league": 4,
    "europa_league": 3,
    "conference_league": 2,
}
TOTAL_BONUS_CAP = 8


def calculate_opportunity_bonuses(*,domestic_cup="none",continental_competition="none",
                                  continental_trophy="none",legacy_cup_won=False):
    """Return a fully auditable one-season award, not an accumulating statistic.

    legacy_cup_won preserves the existing untyped cup_won=True semantics at +1
    rather than falsely asserting that it was an FA Cup or League Cup victory.
    Newly documented honours should specify the exact competition instead.
    """
    if domestic_cup not in DOMESTIC_CUPS:
        raise ValueError("Domestic cup must be none, fa_cup or league_cup")
    if continental_competition not in EUROPEAN_ACCESS:
        raise ValueError("Continental qualification must be an explicitly recognised competition")
    if continental_trophy not in EUROPEAN_TROPHIES:
        raise ValueError("Continental trophy must be an explicitly recognised competition")
    if type(legacy_cup_won) is not bool:
        raise ValueError("Legacy generic cup winner flag must be a boolean")
    if legacy_cup_won and domestic_cup != "none":
        raise ValueError("Legacy cup win and named domestic cup cannot both be claimed")
    cup_bonus=1 if legacy_cup_won else DOMESTIC_CUPS[domestic_cup]
    access_bonus=EUROPEAN_ACCESS[continental_competition]
    trophy_bonus=EUROPEAN_TROPHIES[continental_trophy]
    raw=cup_bonus+access_bonus+trophy_bonus
    total=min(TOTAL_BONUS_CAP,raw)
    return {
        "domestic_cup":domestic_cup,
        "continental_competition":continental_competition,
        "continental_trophy":continental_trophy,
        "cup_bonus":cup_bonus,
        "continental_bonus":access_bonus,
        "continental_trophy_bonus":trophy_bonus,
        "raw_bonus":raw,
        "temporary_bonus":total,
        "overlap_cap":raw-total,
        "bonus_cap":TOTAL_BONUS_CAP,
        "has_domestic_cup":bool(legacy_cup_won or domestic_cup!="none"),
    }
