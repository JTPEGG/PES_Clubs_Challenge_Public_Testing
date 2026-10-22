"""Game-only source-squad sporting appeal for opt-in historical editions.

FC27's source leagues have names but no tier numbers. A missing division
must remain UNKNOWN; it is not a reason to reject every transfer offer.
Only source-rated clubs with sufficient players can receive an assessment.
"""
VERSION="historical-career-squad-sporting-appeal-v2"
MIN_RATED=11

def historical_club_appeal(conn,*,career_id,club_id):
    if not conn.execute("""SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='world_dataset_pes_v2_metadata'""").fetchone():
        return None
    identity=conn.execute("""SELECT s.dataset_id,e.competition_id,c.tier FROM
        world_career_saves s
        JOIN world_dataset_pes_v2_metadata h ON h.dataset_id=s.dataset_id
        JOIN world_dataset_entries e ON e.dataset_id=s.dataset_id
        JOIN world_competitions c ON c.competition_id=e.competition_id
        WHERE s.career_id=? AND e.club_id=?""",(career_id,club_id)).fetchone()
    if identity is None:return None
    dataset,competition,tier=identity
    if tier is not None and (type(tier) is not int or not 1<=tier<=20):
        return None
    ratings=[ovr for (ovr,) in conn.execute("""SELECT dr.overall FROM
         world_dataset_rosters r JOIN world_dataset_ratings dr
         ON dr.dataset_id=r.dataset_id AND dr.player_id=r.player_id
         WHERE r.dataset_id=? AND r.club_id=? AND dr.overall BETWEEN 1 AND 99
         ORDER BY dr.overall DESC LIMIT 16""",(dataset,club_id))]
    if len(ratings)<MIN_RATED:return None
    top_mean=sum(ratings)/len(ratings)
    # No fictitious division penalty when FC27 source tier is unknown.
    # No institutional/European prestige is claimed.
    penalty=6*(tier-1) if tier is not None else 0
    score=round(max(10,min(95,14+.78*top_mean-penalty)))
    return {"competition_id":competition,"score":score,"model":VERSION,
            "squad_top_rated":len(ratings),"source_tier":tier,
            "tier_status":"source_tier" if tier is not None else "unknown"}

def assess_historical_player_interest(*,buyer_tier,seller_tier,
                                      buyer_score,seller_score):
    """Exact legacy comparison when both tiers exist, guarded strength-only
    comparison when either source division is missing. Unknown remains unknown.
    """
    from world_reputation_v2 import assess_player_interest
    if buyer_score is None or seller_score is None:
        return {"decision":"review","can_negotiate":False,
                "reason":"Unassessed source squad strength",
                "source_tier_status":"unknown"}
    if buyer_tier is not None and seller_tier is not None:
        return {**assess_player_interest(buyer_tier=buyer_tier,
                    seller_tier=seller_tier,buyer_score=buyer_score,
                    seller_score=seller_score),
                "source_tier_status":"both_source_tiers_known"}
    gap=seller_score-buyer_score
    note="Source league tier unknown: no divisional benefit or penalty assumed; "
    if gap>=28:
        return {"decision":"uninterested","can_negotiate":False,
                "reason":note+f"major sporting-strength downgrade ({gap} points)",
                "source_tier_status":"unknown"}
    if gap>=10:
        return {"decision":"needs_assurances","can_negotiate":True,
                "reason":note+f"sporting-strength downgrade ({gap} points), salary and role assurances required",
                "source_tier_status":"unknown"}
    return {"decision":"open_to_talks","can_negotiate":True,
            "reason":note+"source-rated sporting strength is reasonably comparable; final player and agent terms remain separate",
            "source_tier_status":"unknown"}
