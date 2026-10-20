"""Bounded game-only historical sporting appeal for a sourced historical world.

The legacy assessor previously handled exclusively four original English
competition IDs. Edition-scoped historical competitions have different IDs,
so all AI-to-AI player moves were marked unassessed and no agent ever opened.
Only opt-in historical career worlds may use this model. Missing source
ratings, poor squad coverage or absent source tier remain UNKNOWN, not false
real-world prestige or verified European football.
"""
from collections import defaultdict

VERSION="historical-career-squad-sporting-appeal-v1"
MIN_RATED=11


def historical_club_appeal(conn,*,career_id,club_id):
    identity=conn.execute("""SELECT s.dataset_id,e.competition_id,
       c.tier FROM world_career_saves s
       JOIN world_dataset_pes_v2_metadata h ON h.dataset_id=s.dataset_id
       JOIN world_dataset_entries e ON e.dataset_id=s.dataset_id
       JOIN world_competitions c ON c.competition_id=e.competition_id
       WHERE s.career_id=? AND e.club_id=?""",(career_id,club_id)).fetchone()
    if identity is None or identity[2] is None:
        return None
    dataset,competition,tier=identity
    if type(tier) is not int or not 1<=tier<=20:
        return None
    ratings=[ovr for (ovr,) in conn.execute("""SELECT dr.overall FROM
         world_dataset_rosters r
         JOIN world_dataset_ratings dr ON dr.dataset_id=r.dataset_id
           AND dr.player_id=r.player_id
         WHERE r.dataset_id=? AND r.club_id=? AND dr.overall BETWEEN 1 AND 99
         ORDER BY dr.overall DESC LIMIT 16""",(dataset,club_id))]
    if len(ratings)<MIN_RATED:
        return None
    top_mean=sum(ratings)/len(ratings)
    # Shared cross-league proxy, NOT institution, UCL qualification or precise
    # division reputation. Small tier penalty is a game rule. Historic player
    # preferences and board financial decisions remain independently assessed.
    score=round(max(10,min(95,14+.78*top_mean-6*(tier-1))))
    return {"competition_id":competition,"score":score,"model":VERSION,
            "squad_top_rated":len(ratings),"source_tier":tier}
