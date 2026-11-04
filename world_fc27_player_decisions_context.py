"""Source-labelled FC27 game context for autonomous V2 player choice.

Strictly scoped to the verified FC27 warehouse: never claim the game-estimated
squad role, listing, or renewal intentions are verified real-world facts.
Existing explicit user assumptions always take priority.
"""
from __future__ import annotations
from world_ai_bidding import position_family

FC27_DATASET="fc27-warehouse-659-mens-2026-27"
SOURCE_LABEL="FC27_GAME_ESTIMATE_FROM_SOURCE_WAGES_AND_SQUAD_RANK"


def is_fc27_context(conn,career_id):
    row=conn.execute("""SELECT dataset_id FROM world_career_saves
        WHERE career_id=?""",(career_id,)).fetchone()
    return row is not None and row[0]==FC27_DATASET


def game_player_facts(conn,career_id,player_id):
    """EA source-game wage/expiry plus transparent SIMULATED role/exit stance.

    Missing source wage/rating is never silently inferred. This simulation is
    deliberately limited to the FC27 dataset and used only when the manager
    has not supplied an explicit fact.
    """
    if not is_fc27_context(conn,career_id):
        return None
    row=conn.execute("""SELECT r.club_id,p.primary_position,ra.overall,
        cs.weekly_wage_gbp,cs.expires_on,c.next_summer_date
        FROM world_career_saves c
        JOIN world_career_registrations r ON r.career_id=c.career_id
        JOIN world_players p ON p.player_id=r.player_id
        JOIN world_dataset_ratings ra ON ra.dataset_id=c.dataset_id
           AND ra.player_id=r.player_id
        JOIN world_career_contract_snapshots cs ON cs.career_id=c.career_id
           AND cs.player_id=r.player_id
        WHERE c.career_id=? AND r.player_id=?""",
        (career_id,player_id)).fetchone()
    if row is None:
        return None
    club,pos,overall,wage,expires,summer=row
    if type(wage) is not int or not 0<=wage<=1_000_000:
        return None
    if type(overall) is not int or not 1<=overall<=99:
        return None
    # Prefer the already materialised manager-squad game model when present.
    live=conn.execute("""SELECT squad_role_estimate,transfer_listed_estimate
        FROM world_career_live_player_context
        WHERE career_id=? AND player_id=? ORDER BY window_id DESC LIMIT 1""",
        (career_id,player_id)).fetchone()
    if live:
        role=str(live[0])
        listed=bool(live[1])
    else:
        # Deterministic rank in the *same* source-rated club. Keeper depth
        # is ranked among GKs; elsewhere, rank the highest rated squad.
        from world_career_player_profiles import fc27_source_squad_role
        role=fc27_source_squad_role(conn,career_id,player_id,club)
        listed=bool(role=="fringe" and expires and summer and expires<=summer)
    # Renewal attitude is a game scenario based on contract horizon, NEVER a
    # claim about the club's actual decision or a current transfer request.
    nonrenewal=bool(role=="fringe" and expires and summer and expires<=summer)
    return {
        "current_wage_weekly":wage,
        "current_role":role,
        "transfer_listed":listed,
        "renewal_status":"not_offered" if nonrenewal else "renewal_offered",
        "source_kind":SOURCE_LABEL,
        "updated_at":None,
    }
