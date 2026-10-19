"""AI-to-AI pre-season activity, isolated from the human manager.

Each recorded market moment gives independent clubs the opportunity to seek
positional upgrades from other AI clubs. A deal only becomes binding after
seller acceptance, real modelled player/agent consent, buyer board review and
budget checks. Registration still occurs ONLY in the shared deadline batch.
All unknown contracts/intentions are explicitly fictional model assumptions.
"""
from collections import defaultdict
from datetime import date, timedelta

from world_ai_bidding import club_need, determine_offer, position_family
from world_careers import (
    _player_reference, budget_remaining, wage_budget_breakdown,
    propose_offer, agent_terms, negotiate_agent, player_move_interest,
)
from world_preseason_window import window_snapshot
from world_career_board_policy import career_board_decision, require_board_approval
from world_squad_planner import projected_squads, recruitment_fit, departure_guard, lane_of
from world_recruitment_strategy import (development_signals, prospect_fit,
    prospect_fee_cap, MAX_PROSPECTS_PER_WINDOW)

AI_WORLD_VERSION = "ai-world-v4-projected-squads-and-future"
# Global ceiling is a safety bound, not a target. A real market may be quiet.
# Multiple independent clubs may agree moves during one market interval.
MAX_AI_DEALS = 90  # upper safety bound, not a minimum or forced sales
MAX_SIGNINGS_PER_AI_CLUB = 3  # do not let one club dominate a short window
MAX_OUTGOING_PER_AI_CLUB = 4
AI_APPROACHES_PER_ATTEMPT = 5


def _need_for_family(*,family,overall,ratings):
    """Different first-team structures require different replacement depth.

    Using the third-best player for ALL roles nearly eliminated defenders
    from the old market (4 of 234 deals) because full-back and centre-back
    strength were mixed into one group. A four-defender team has a fourth
    starter and needs cover through its sixth/eighth defender.
    """
    normal=club_need(overall=overall,ratings=ratings,
                     position_group=family)
    if not ratings:return normal["score"]
    ranked=sorted(ratings,reverse=True)
    if family=="DEF":
        # Fourth-choice starter and first depth candidate are both
        # relevant; don't require an improvement on an elite third defender.
        baseline=ranked[min(4,len(ranked)-1)]
        need=49+(overall-baseline)*5+min(12,max(0,8-len(ranked))*3)
        return max(15,min(95,need))
    if family=="GK":
        # A third-choice keeper is not a starting-position vacancy.
        baseline=ranked[0]
        need=44+(overall-baseline)*6+min(9,max(0,3-len(ranked))*4)
        return max(15,min(92,need))
    return normal["score"]


def _keeper_slot_open(keepers,other):
    """Keeper purchases remain a small minority of independently signed moves."""
    return keepers<max(1,(other+4)//8)


def _ai_wage_opening(*,demand,career_id,buyer,player_id):
    """Repeatable buyer negotiating style: pay in full only occasionally."""
    from world_live_market import _stable
    style=_stable(career_id,buyer,player_id,AI_WORLD_VERSION,"salary")%100
    if style<17:
        return demand,style
    # Every routine AI agent approach now involves a genuine negotiation.
    fraction=0.84+((style%11)*0.01)
    opening=max(500,int((demand*fraction)//500)*500)
    return min(demand,opening),style


def _candidates(conn, career_id, dataset, manager):
    """Read the *projected* roster including already agreed sales/purchases."""
    projections=projected_squads(conn,career_id=career_id,dataset=dataset)
    squads=defaultdict(lambda:defaultdict(list))
    players=defaultdict(list)
    for club,lanes in projections.items():
        for group in lanes.values():
            for pid,overall,pos in group:
                family=position_family(pos)
                if family is None:continue
                squads[club][family].append(overall)
                if club!=manager:
                    players[family].append((club,pid,overall))
    return squads,players


def _sign_ai_deal(conn, *, career_id, offer_id, buyer, seller, fee,
                  wage, game_date):
    """AI-only approval; never impersonate a human manager signing a deal."""
    from world_career_selling import evaluate_career_seller_bid
    row=conn.execute("""SELECT o.player_id,o.status,o.offered_fee,o.selling_club_id,
        o.buying_club_id,t.status,t.proposed_wage_weekly
        FROM world_career_offers o
        LEFT JOIN world_career_agent_terms t ON t.offer_id=o.offer_id
        WHERE o.career_id=? AND o.offer_id=?""",
        (career_id,offer_id)).fetchone()
    if not row or tuple(row[1:])!=(
            "accepted_pending_contract",fee,seller,buyer,"accepted",wage):
        raise ValueError("AI deal requires valid seller, fee and accepted agent terms")
    rival=conn.execute("""SELECT 1 FROM world_career_offers
        WHERE career_id=? AND player_id=? AND offer_id<>?
          AND status IN ('agreed_future','completed') LIMIT 1""",
        (career_id,row[0],offer_id)).fetchone()
    if rival:
        raise ValueError("Player has already signed for another club")
    from world_player_morale import is_unavailable
    snap=window_snapshot(conn,career_id=career_id)
    if is_unavailable(conn,career_id=career_id,window_id=snap["window_id"],
                      player_id=row[0]):
        raise ValueError("Player refusing to play cannot sign for the coming PES season")
    dataset=conn.execute("SELECT dataset_id FROM world_career_saves WHERE career_id=?",
                         (career_id,)).fetchone()[0]
    value,_=_player_reference(conn,dataset,row[0])
    seller_review=evaluate_career_seller_bid(conn,career_id=career_id,
        player_id=row[0],seller_club_id=seller,offer_fee=fee,
        buying_club_id=buyer)
    if seller_review["decision"]!="accept":
        raise ValueError("Selling club has not accepted the final AI transfer fee")
    headroom=wage_budget_breakdown(conn,career_id,buyer)["remaining"]
    if fee>budget_remaining(conn,career_id,buyer)+fee or wage>headroom:
        raise ValueError("AI buyer cannot fund the signed contract")
    require_board_approval(career_board_decision(conn,career_id=career_id,
        club_id=buyer,offer_fee=fee,market_value=value,
        offered_wage=wage,wage_headroom=headroom,stage="terms"))
    conn.execute("""UPDATE world_career_offers SET status='agreed_future',
        offered_wage_weekly=?,agreement_date=? WHERE offer_id=? AND status='accepted_pending_contract'""",
        (wage,game_date,offer_id))
    conn.execute("""INSERT INTO world_career_offer_events
        (offer_id,event_type,detail) VALUES(?,?,?)""",
        (offer_id,"ai_world_signed",
         "AI buyer and seller agreed; independent modelled player and agent terms "
         "accepted, affordability and board checks passed. Registration at deadline only."))
    conn.commit()


def consider_ai_world_deal(conn, *, career_id, window_id, slot, now=None):
    """One independent club-led AI market opportunity per persisted attempt.

    Returns a completed agreement ID or None. Failed negotiations never create
    registrations. Replaying a moment is blocked by the caller's moment ledger.
    """
    from world_live_market import _stable, _message, _modelled_europe, _market_money
    from world_live_buying import _model_player_and_seller

    snap=window_snapshot(conn,career_id=career_id,now=now)
    if snap["state"]!="open" or snap["window_id"]!=window_id:
        return None
    # Commit an immutable checkpoint before any seller/agent operation,
    # several of which have independent internal commits. A retry cannot
    # cause a second AI transfer from the same market moment.
    try:
        conn.execute("""INSERT INTO world_career_ai_world_moments
            (window_id,moment_index,created_at) VALUES(?,?,?)""",
            (window_id,slot,snap["started_at"]))
        conn.commit()
    except __import__("sqlite3").IntegrityError:
        conn.rollback()
        return None
    existing=conn.execute("""SELECT COUNT(*) FROM world_career_offer_events e
        JOIN world_career_offers o ON o.offer_id=e.offer_id
        JOIN world_career_preseason_window_offers wo ON wo.offer_id=o.offer_id
        WHERE wo.window_id=? AND e.event_type='ai_world_signed'""",
        (window_id,)).fetchone()[0]
    if existing>=MAX_AI_DEALS:
        return None
    c=conn.execute("""SELECT dataset_id,manager_club_id,pes_lock_date
        FROM world_career_saves WHERE career_id=?""",(career_id,)).fetchone()
    if c is None:
        return None
    dataset,manager,lock_date=c
    squads,players=_candidates(conn,career_id,dataset,manager)
    projected=projected_squads(conn,career_id=career_id,dataset=dataset)
    # Age is measured at the HISTORICAL dataset snapshot, not today's date.
    scouting=development_signals(conn,dataset=dataset)
    projected_positions={pid:pos for lanes in projected.values() for group in lanes.values()
                         for pid,_overall,pos in group}
    buyers=sorted((club for club in squads if club!=manager),
                  key=lambda club:_stable(career_id,window_id,slot,club,AI_WORLD_VERSION))
    game_date=(date.fromisoformat(lock_date)-timedelta(days=1)).isoformat()
    previous=conn.execute("""SELECT o.player_id FROM world_career_offers o
        JOIN world_career_preseason_window_offers wo ON wo.offer_id=o.offer_id
        WHERE wo.window_id=? AND o.status='agreed_future'""",
        (window_id,)).fetchall()
    signed_players={r[0] for r in previous}
    # Cap scanning and attempts: a world-wide market must not monopolise an
    # interactive request or manufacture activity when no credible deal exists.
    approaches=0
    signings_by_buyer=defaultdict(int)
    signings_by_seller=defaultdict(int)
    youth_signings=defaultdict(int)
    for club,n in conn.execute("""SELECT o.buying_club_id,COUNT(*)
        FROM world_career_offer_events e
        JOIN world_career_offers o ON o.offer_id=e.offer_id
        JOIN world_career_preseason_window_offers wo ON wo.offer_id=o.offer_id
        WHERE wo.window_id=? AND e.event_type='ai_prospect_signed'
        GROUP BY o.buying_club_id""",(window_id,)).fetchall():
        youth_signings[club]=n
    for buying,selling in conn.execute("""SELECT o.buying_club_id,
        o.selling_club_id FROM world_career_offer_events e
        JOIN world_career_offers o ON o.offer_id=e.offer_id
        JOIN world_career_preseason_window_offers wo ON wo.offer_id=o.offer_id
        WHERE wo.window_id=? AND e.event_type='ai_world_signed'""",
        (window_id,)).fetchall():
        signings_by_buyer[buying]+=1
        signings_by_seller[selling]+=1
    # An entire football world has only one starting goalkeeper per club.
    # Do not allow keeper churn to consume the same volume of transactions
    # as the far larger outfield population.
    family_counts=defaultdict(int)
    for (pos,) in conn.execute("""SELECT p.primary_position
        FROM world_career_offer_events e
        JOIN world_career_offers o ON o.offer_id=e.offer_id
        JOIN world_career_preseason_window_offers wo ON wo.offer_id=o.offer_id
        JOIN world_players p ON p.player_id=o.player_id
        WHERE wo.window_id=? AND e.event_type='ai_world_signed'""",
        (window_id,)).fetchall():
        family_counts[position_family(pos)]+=1
    non_keeper=sum(n for group,n in family_counts.items() if group!="GK")
    for buyer in buyers[:32]:
        if (signings_by_buyer[buyer]>=MAX_SIGNINGS_PER_AI_CLUB or
                budget_remaining(conn,career_id,buyer)<=0):
            continue
        profiles=squads[buyer]
        # Compare position depth to plausible squad composition instead
        # of sorting on absolute count. An average squad might carry 3 GKs
        # but 7-9 defenders/midfielders; 3 keepers are NOT the largest need.
        expected={"GK":3,"DEF":8,"MID":9,"FWD":6}
        priorities=sorted(profiles,key=lambda group:(
            len(profiles[group])/expected.get(group,6)+
            (0.36 if group=="GK" else -0.12 if group=="DEF" else 0),
            _stable(slot,buyer,group,AI_WORLD_VERSION)))
        for family in priorities:
            if family=="GK" and not _keeper_slot_open(
                    family_counts["GK"],non_keeper):
                continue
            if family=="FWD":
                # A 92-club world has a far larger need for defenders and
                # midfielders than for permanent forward replacements.
                # Avoid replacing keeper saturation with striker saturation.
                not_forwards=sum(n for g,n in family_counts.items()
                                 if g!="FWD")
                if family_counts["FWD"]>=max(2,not_forwards*2//3):
                    continue
            club_ratings=profiles[family]
            options=[]
            for seller,pid,overall in players[family]:
                if (seller==buyer or pid in signed_players or
                        signings_by_seller[seller]>=MAX_OUTGOING_PER_AI_CLUB):
                    continue
                try:
                    from world_player_morale import is_unavailable
                    if is_unavailable(conn,career_id=career_id,
                                      window_id=window_id,player_id=pid):
                        continue
                except __import__("sqlite3").OperationalError:
                    pass
                # Do not mistake an extra average defender for a needed CB:
                # only the player's actual specialist slot can justify demand.
                position=projected_positions.get(pid)
                fit=recruitment_fit(projected,buyer=buyer,
                                    position=position,overall=overall)
                # Future recruitment is separate from a starting-XI upgrade.
                # Never manufacture a potential rating or guarantee a deal:
                # agent and seller can still independently refuse.
                if not fit["eligible"]:
                    fit=prospect_fit(projected,buyer=buyer,player_id=pid,
                        position=position,overall=overall,signals=scouting,
                        existing_prospects=youth_signings[buyer])
                if not fit["eligible"]:
                    continue
                release=departure_guard(projected,seller=seller,
                    player_id=pid,position=position,overall=overall)
                if not release["allowed"]:
                    continue
                need=fit["score"]
                if overall>max(club_ratings)+14:
                    continue
                lane=lane_of(position)
                seller_depth=projected.get(seller,{}).get(lane,[])
                seller_rank=next((i for i,item in enumerate(seller_depth)
                                  if item[0]==pid),len(seller_depth))
                seller_fit=8 if seller_rank>=3 else -5 if seller_rank==0 else 0
                options.append((seller,pid,overall,need,need+seller_fit,fit))
            options.sort(key=lambda v:(-v[4],
                _stable(career_id,slot,buyer,v[1],AI_WORLD_VERSION)))
            for seller,pid,overall,need,_score,fit in options[:10]:
                value,_=_player_reference(conn,dataset,pid)
                money=budget_remaining(conn,career_id,buyer)
                if not isinstance(value,int) or value<=0 or money<value*0.85:
                    continue
                if fit.get("category")=="prospect":
                    ledger=conn.execute("""SELECT transfer_budget FROM
                        world_career_club_ledger WHERE career_id=? AND club_id=?""",
                        (career_id,buyer)).fetchone()
                    if ledger is None or value*0.85>prospect_fee_cap(
                            initial_transfer_budget=ledger[0],
                            available_budget=money):
                        continue
                # Existing manager offers or future commitments have precedence.
                conflict=conn.execute("""SELECT 1 FROM world_career_offers
                    WHERE career_id=? AND player_id=?
                    AND status IN ('agreed_future','completed') LIMIT 1""",
                    (career_id,pid)).fetchone()
                if conflict:
                    continue
                key=f"ai-world-v1-{window_id}-{slot}-{buyer}-{pid}"
                already=conn.execute("""SELECT 1 FROM world_career_offers
                    WHERE career_id=? AND request_key=?""",(career_id,key)).fetchone()
                if already:
                    continue
                # The normal seller and contract decision engines remain
                # authoritative; no unilateral movement of another squad.
                target=dict(dataset=dataset,seller=seller,overall=overall,
                            value=value)
                if approaches>=AI_APPROACHES_PER_ATTEMPT:
                    return None
                approaches+=1
                try:
                    _model_player_and_seller(conn,career_id=career_id,
                                              player_id=pid,target=target)
                    from world_career_selling import get_seller_assumptions
                    seller_facts=get_seller_assumptions(conn,career_id,pid)
                    price=determine_offer(career_id=career_id,player_id=pid,
                        club_id=buyer,valuation=value,available_budget=money,
                        need_score=need,eligible_clubs=1,
                        seller_assumptions=seller_facts)
                    if price["fee"] is None:
                        continue
                    if fit.get("category")=="prospect" and price["fee"]>prospect_fee_cap(
                            initial_transfer_budget=ledger[0],
                            available_budget=money):
                        continue
                    oid=propose_offer(conn,career_id=career_id,request_key=key,
                        player_id=pid,buying_club_id=buyer,offered_fee=price["fee"],
                        agreement_date=game_date,
                        ai_bid_snapshot={**price,"recruitment_type":
                            fit.get("category","first_team"),
                            "recruitment_reason":fit["reason"],
                            "scouting_evidence":fit.get("evidence")})
                    terms_row=conn.execute("""SELECT status,offered_fee,demanded_fee
                        FROM world_career_offers WHERE offer_id=?""",(oid,)).fetchone()
                    status=terms_row["status"]
                    final_fee=terms_row["offered_fee"]
                    if status=="countered":
                        asking=terms_row["demanded_fee"]
                        # AI accepts a reasoned asking price only within its
                        # independent ceiling and the remaining budget.
                        if (asking is None or asking>value*1.25
                                or asking>money or asking<=final_fee or
                                (fit.get("category")=="prospect" and
                                 asking>prospect_fee_cap(
                                     initial_transfer_budget=ledger[0],
                                     available_budget=money))):
                            continue
                        from world_careers import accept_counter
                        accept_counter(conn,career_id=career_id,offer_id=oid)
                        status="accepted_pending_contract"
                        final_fee=asking
                    if status!="accepted_pending_contract":
                        continue
                    from world_live_market import _modelled_europe
                    conn.execute("""INSERT OR IGNORE INTO world_career_offer_europe
                        (career_id,offer_id,buyer_europe,seller_europe,source_kind)
                        VALUES(?,?,?,?,?)""",(career_id,oid,
                        _modelled_europe(conn,career_id=career_id,club_id=buyer),
                        _modelled_europe(conn,career_id=career_id,club_id=seller),
                        "fictional-preseason-prestige-seeding-v1"))
                    conn.commit()
                    promise=("rotation" if fit.get("category")=="prospect" else
                             "key_player" if need>=90 and
                             overall>=max(club_ratings) else "regular_starter")
                    interest=player_move_interest(conn,career_id=career_id,
                        offer_id=oid,role_promise=promise)
                    if not interest["can_negotiate"]:
                        continue
                    terms=agent_terms(conn,career_id=career_id,offer_id=oid)
                    demand=terms["demanded_wage_weekly"]
                    if demand>wage_budget_breakdown(conn,career_id,buyer)["remaining"]:
                        continue
                    first_wage,style=_ai_wage_opening(
                        demand=demand,career_id=career_id,buyer=buyer,
                        player_id=pid)
                    response=negotiate_agent(conn,career_id=career_id,
                        offer_id=oid,weekly_wage=first_wage,contract_years=3,
                        role_promise=promise,agreement_date=game_date)
                    final_wage=first_wage
                    if response=="countered":
                        # Neither the player's agent nor the AI buyer must
                        # compromise. Some clubs walk away after the counter;
                        # others will match the updated demand if affordable.
                        if style%9==0 or style>=93:
                            continue
                        demand=conn.execute("""SELECT demanded_wage_weekly
                            FROM world_career_agent_terms
                            WHERE offer_id=?""",(oid,)).fetchone()[0]
                        if demand>wage_budget_breakdown(
                                conn,career_id,buyer)["remaining"]:
                            continue
                        final_wage=demand
                        response=negotiate_agent(conn,career_id=career_id,
                            offer_id=oid,weekly_wage=final_wage,
                            contract_years=3,role_promise=promise,
                            agreement_date=game_date)
                    if response!="accepted":
                        continue
                    _sign_ai_deal(conn,career_id=career_id,offer_id=oid,buyer=buyer,
                        seller=seller,fee=final_fee,wage=final_wage,
                        game_date=game_date)
                    if fit.get("category")=="prospect":
                        conn.execute("""INSERT INTO world_career_offer_events
                            (offer_id,event_type,detail) VALUES(?,? ,?)""",
                            (oid,"ai_prospect_signed",
                             "Independently scouted youth investment; future ability unverified"))
                        conn.commit()
                        youth_signings[buyer]+=1
                    signings_by_buyer[buyer]+=1
                    signings_by_seller[seller]+=1
                    family_counts[family]+=1
                    if family!="GK":non_keeper+=1
                    club_names=dict(conn.execute("""SELECT club_id,name
                        FROM world_clubs WHERE club_id IN (?,?)""",
                        (buyer,seller)).fetchall())
                    player_name=conn.execute("""SELECT full_name FROM world_players
                        WHERE player_id=?""",(pid,)).fetchone()[0]
                    _message(conn,career_id=career_id,window_id=window_id,
                        key=f"ai-world-signed:{oid}",offer_id=oid,when=now,
                        headline="Elsewhere in the transfer market",
                        detail=(f"{club_names[seller]} have agreed to sell "
                                f"{player_name} to {club_names[buyer]} for "
                                f"{_market_money(final_fee)}. "
                                + ("Development signing. " if
                                   fit.get("category")=="prospect" else
                                   "First-team recruitment. ")
                                + "The deal registers at the deadline."))
                    conn.commit()
                    return oid
                except (ValueError, TypeError):
                    # Unsupported or refused terms do not invent player consent.
                    continue
    return None
