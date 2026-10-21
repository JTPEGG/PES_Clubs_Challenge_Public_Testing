"""FC27-only approval of source-as-provided membership in 33 domestic divisions.

Club identity, domestic competition and calendar remain exactly as already
staged in the 2027 source-derived database. This user-approved *scope decision*
does not independently prove real-world league completeness, add players or
clubs, assign promotion routes, or decide which divisions are playable.
"""
from __future__ import annotations

import sqlite3
from collections import Counter

POLICY_VERSION = "fc27-original-membership-as-provided-v1"
# Pinned to the audited 21-Oct-2026 659-source-club FC27 release.
# Includes continental-bucket clubs whose domestic assignment was already
# reviewed separately: they do NOT become "original domestic source groups".
SOURCE_AS_PROVIDED_COUNTS = {
    "2027:ae.1": 1,  "2027:at.1": 12, "2027:au.1": 12,
    "2027:az.1": 1,  "2027:be.1": 18, "2027:bg.1": 1,
    "2027:bo.1": 4,  "2027:cl.1": 5,  "2027:cn.1": 16,
    "2027:co.1": 7,  "2027:cy.1": 2,  "2027:de.2": 18,
    "2027:dk.1": 12, "2027:ec.1": 5,  "2027:fi.1": 1,
    "2027:gr.1": 4,  "2027:hr.1": 2,  "2027:hu.1": 1,
    "2027:ie.1": 10, "2027:kr.1": 12, "2027:mx.1": 18,
    "2027:no.1": 16, "2027:pe.1": 5,  "2027:pl.1": 18,
    "2027:py.1": 4,  "2027:ro.1": 16, "2027:sa.1": 18,
    "2027:sco.1": 12,"2027:se.1": 16, "2027:th.1": 1,
    "2027:ua.1": 2,  "2027:uy.1": 5,  "2027:ve.1": 5,
}
if len(SOURCE_AS_PROVIDED_COUNTS) != 33 or sum(SOURCE_AS_PROVIDED_COUNTS.values()) != 280:
    raise RuntimeError("FC27 membership approval source snapshot count drift")

SCHEMA = """
CREATE TABLE fc27_source_as_provided_membership_policy (
    edition INTEGER NOT NULL CHECK(edition=2027),
    competition_code TEXT NOT NULL,
    retained_source_club_count INTEGER NOT NULL CHECK(retained_source_club_count>0),
    treatment TEXT NOT NULL CHECK(
      treatment='accept_staged_FC27_clubs_without_additional_roster_expansion'),
    independent_fixture_roster_verified INTEGER NOT NULL
      CHECK(independent_fixture_roster_verified=0),
    playability TEXT NOT NULL CHECK(playability='not_changed_by_membership_policy'),
    movement_rules TEXT NOT NULL CHECK(movement_rules='independently_reviewed_later'),
    PRIMARY KEY(edition,competition_code)
);
CREATE VIEW fc27_accepted_source_as_provided_clubs AS
  SELECT c.edition,c.club_key,c.club,c.starting_competition,
         c.evidence_origin,c.verification_scope,
         p.treatment,p.playability
  FROM fc27_2026_27_complete_source_competition_alignment c
  JOIN fc27_source_as_provided_membership_policy p
    ON p.edition=c.edition AND p.competition_code=c.starting_competition;
"""

def adopt_staged_memberships(db: sqlite3.Connection, *, strict=True):
    """Mark only exact existing club-to-division records; never alter the teams."""
    rows = db.execute("""
        SELECT edition,club_key,club,starting_competition
        FROM fc27_2026_27_complete_source_competition_alignment
        WHERE edition=2027
    """).fetchall()
    if len({r[1] for r in rows}) != len(rows):
        raise ValueError("Duplicate FC27 source club; cannot approve group memberships")
    source_count = Counter(x[3] for x in rows)
    no_fixture_evidence = {
        code for code,count in db.execute("""
            SELECT a.starting_competition,COUNT(*)
            FROM fc27_2026_27_complete_source_competition_alignment a
            LEFT JOIN sourced_domestic_league_clubs fixtures
              ON fixtures.edition=a.edition AND fixtures.competition_code=a.starting_competition
            WHERE a.edition=2027
              AND NOT EXISTS (
                SELECT 1 FROM sourced_domestic_league_clubs f
                WHERE f.edition=2027 AND f.competition_code=a.starting_competition)
            GROUP BY a.starting_competition
        """)
    }
    expected = SOURCE_AS_PROVIDED_COUNTS
    if strict:
        if set(source_count) & no_fixture_evidence != set(expected):
            raise ValueError("FC27 no-fixture source divisions differ from agreed 33")
        if sum(source_count.values()) != 659:
            raise ValueError("FC27 staging no longer has 659 eligible clubs")
    if any(source_count.get(code) != count for code,count in expected.items()):
        raise ValueError("FC27 source club group membership/count changed: review before approval")
    if any(code not in no_fixture_evidence for code in expected):
        raise ValueError("An approved FC27 source division now has independent fixtures; reassess it")
    if db.execute("""
        SELECT COUNT(*) FROM edition_readiness WHERE edition=2027 AND career_ready != 0
    """).fetchone()[0]:
        raise ValueError("Scope decision cannot activate an unverified career")

    db.executescript(SCHEMA)
    db.executemany("""
        INSERT INTO fc27_source_as_provided_membership_policy
        VALUES(?,?,?,?,?,?,?)
    """, [
        (2027,code,count,
         "accept_staged_FC27_clubs_without_additional_roster_expansion",0,
         "not_changed_by_membership_policy","independently_reviewed_later")
        for code,count in sorted(expected.items())
    ])
    preserved=db.execute(
        "SELECT COUNT(*) FROM fc27_accepted_source_as_provided_clubs"
    ).fetchone()[0]
    if preserved!=280:
        raise ValueError("Approved league view did not preserve exactly 280 source clubs")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("FC27 membership policy caused broken foreign keys")
    return {
        "policy_version":POLICY_VERSION,
        "accepted_source_as_provided_competitions":len(expected),
        "retained_source_clubs_in_accepted_groups":preserved,
        "membership_roster_expansion_requested":False,
        "all_existing_fc27_clubs_preserved":True,
        "original_game_EA_ids_certified":False,
        "playability_unchanged":True,
        "promotion_relegation_rule_review_separate":True,
        "greece_2027_original_source_clubs_kept":source_count["2027:gr.1"],
        "german_second_division_original_source_clubs_kept":source_count["2027:de.2"],
    }
