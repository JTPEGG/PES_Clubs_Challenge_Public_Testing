"""Audit cross-source identities and squad-registration readiness.

Candidate differences are warnings, NOT confirmed transfers. Short names such
as 'James' or 'Neto' can refer to multiple unrelated players. No automatic
reassignment or overwrite is permitted by this module.
"""
import re
import unicodedata
from collections import Counter, defaultdict
from world_2026_27_players import PLAYER_SEED
from world_fc27_english import FC27_PLAYERS


def norm(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(x for x in value if not unicodedata.combining(x))
    return re.sub("[^a-z0-9]", "", value.casefold())


def audit_seed_sources():
    """Provide repeatable source reconciliation, suitable for a read-only UI."""
    ea_by_club = defaultdict(list)
    ea_by_name = defaultdict(list)
    for row in FC27_PLAYERS:
        eid, display, first, last, common, position, club, league, rating, *rest = row
        ea_by_club[club].append(row)
        for text in set(filter(None, [display, common, last])):
            if norm(text):
                ea_by_name[norm(text)].append(row)
    ea_ids = [str(x[0]) for x in FC27_PLAYERS]
    fpl_ids = [str(x[0]) for x in PLAYER_SEED]
    warnings = []
    for code, display, position, club in PLAYER_SEED:
        # Candidate discovery only. A match by last name can be a false
        # positive (e.g. different players with the same common surname).
        candidates = {str(row[0]): row for row in ea_by_name.get(norm(display), [])}
        external = [r for r in candidates.values() if r[6] != club]
        local = [r for r in candidates.values() if r[6] == club]
        if len(candidates) == 1 and external and not local:
            match = external[0]
            warnings.append({
                "fpl_id": str(code), "fpl_name": display, "fpl_club": club,
                "ea_id": str(match[0]), "ea_name": match[1],
                "ea_club": match[6], "reason": "possible club or identity mismatch",
            })
    return {
        "ea_records": len(FC27_PLAYERS),
        "fpl_records": len(PLAYER_SEED),
        "ea_unique_ids": len(set(ea_ids)),
        "fpl_unique_ids": len(set(fpl_ids)),
        "ea_league_counts": dict(Counter(row[7] for row in FC27_PLAYERS)),
        "possible_conflicts": sorted(warnings, key=lambda x: (x["fpl_club"], x["fpl_name"])),
    }


def audit_database(conn):
    """Check the actual imported DB. Does not modify any rows."""
    def count(sql, params=()):
        return conn.execute(sql, params).fetchone()[0]
    return {
        "players": count("SELECT COUNT(*) FROM world_players"),
        "ea_rated": count("SELECT COUNT(*) FROM world_external_ratings WHERE source_name='EA FC 27'"),
        "fpl_source_refs": count("SELECT COUNT(*) FROM world_player_source_refs WHERE source_name='FPL'"),
        "ea_source_refs": count("SELECT COUNT(*) FROM world_player_source_refs WHERE source_name='EAFC27'"),
        "provisional_rosters": count("SELECT COUNT(*) FROM world_rosters WHERE verification_status='provisional'"),
        "source_matched_rosters": count("SELECT COUNT(*) FROM world_rosters WHERE verification_status='source-matched'"),
        "pes_id_matches": count("SELECT COUNT(*) FROM world_pes_player_map"),
        "contracts": count("SELECT COUNT(*) FROM world_contracts"),
        "duplicate_ea_ids": count("""SELECT COUNT(*) FROM (
            SELECT external_id FROM world_player_source_refs
            WHERE source_name='EAFC27' GROUP BY external_id HAVING COUNT(*)>1)"""),
        "duplicate_season_registrations": count("""SELECT COUNT(*) FROM (
            SELECT season_id,player_id FROM world_rosters
            GROUP BY season_id,player_id HAVING COUNT(*)>1)"""),
        "unassigned_players": count("""SELECT COUNT(*) FROM world_players p WHERE NOT EXISTS (
            SELECT 1 FROM world_rosters r WHERE r.player_id=p.player_id AND r.season_id='2026/27')"""),
        "fc27_without_roster": count("""SELECT COUNT(*) FROM world_player_source_refs s
            WHERE s.source_name='EAFC27' AND NOT EXISTS (
                SELECT 1 FROM world_rosters r WHERE r.player_id=s.player_id AND r.season_id='2026/27')"""),
    }
