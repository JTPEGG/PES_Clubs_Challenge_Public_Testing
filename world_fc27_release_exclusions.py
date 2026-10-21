"""Remove excluded source clubs from a *derived* FC27 game database.

The original 22-edition FIFA/FC source archive is deliberately not modified.
This is run only on the final disposable SQLite copy after all source checks.
"""
from __future__ import annotations

from world_competition_exclusions import excluded_source_league


def sanitize_fc27_active_release(db, *, expected_exclusions=None):
    original = db.execute(
        "SELECT club_key, original_source_league FROM edition_club_competitions "
        "WHERE edition=2027"
    ).fetchall()
    blocked = [key for key, label in original if excluded_source_league(label)]
    if expected_exclusions is not None and len(blocked) != expected_exclusions:
        raise ValueError("Original FC27 exclusion count changed; do not silently drop clubs")
    if len(blocked) != len(set(blocked)):
        raise ValueError("Duplicate original club identity in exclusion set")
    if not blocked:
        return 0

    # Delete first from any tables with edition/club_key before deleting the
    # parent originals. Avoid touching similarly named clubs or other editions.
    tables = [row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )]
    for name in tables:
        if name == "edition_club_competitions":
            continue
        escaped = name.replace('"', '""')
        cols = {row[1] for row in db.execute(f'PRAGMA table_info("{escaped}")')}
        if {"edition", "club_key"}.issubset(cols):
            db.executemany(
                f'DELETE FROM "{escaped}" WHERE edition=2027 AND club_key=?',
                [(key,) for key in blocked],
            )

    db.executemany(
        "DELETE FROM edition_club_competitions WHERE edition=2027 AND club_key=?",
        [(key,) for key in blocked],
    )
    if "source_league_groups" in tables:
        for key, label in list(db.execute(
            "SELECT league_key, source_label FROM source_league_groups WHERE edition=2027"
        )):
            if excluded_source_league(label):
                db.execute(
                    "DELETE FROM source_league_groups WHERE edition=2027 AND league_key=?",
                    (key,),
                )
    if "edition_readiness" in tables:
        db.execute(
            "UPDATE edition_readiness SET total_clubs=total_clubs-?, "
            "clubs_unresolved=MAX(0, clubs_unresolved-?) WHERE edition=2027",
            (len(blocked), len(blocked)),
        )

    remainder = db.execute(
        "SELECT original_source_league FROM edition_club_competitions WHERE edition=2027"
    )
    if any(excluded_source_league(row[0]) for row in remainder):
        raise ValueError("Excluded division still present in active original club table")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Sanitizing the derived game release would break foreign keys")
    return len(blocked)
