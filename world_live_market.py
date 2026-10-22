"""Autonomous, persisted market moments for the 30-minute pre-season.

The manager may decide on bids, not supply simulation input or press a
'simulate AI' button. This first iteration targets the managed club; AI-to-AI
completion is a later separate feature. All wages/contracts/intentions used
here are fictional policy estimates with source labels, never claimed facts.
"""
import hashlib
import secrets
import sqlite3
from datetime import datetime,timezone,timedelta
from world_preseason_window import (
    window_snapshot,start_preseason_window,finalise_preseason_window,
    assert_window_allows_negotiation,_utc,_iso,
)
from world_careers import (
    _player_reference,ai_interest,budget_remaining,propose_offer,
    reject_incoming_offer,
)
from world_ai_bidding import determine_offer,position_family
from world_career_incoming import (
    advance_incoming_approach,incoming_approach,finalise_incoming_approach,
)
from world_career_transfer_protocol import (
    transfer_protocol_enabled,enable_transfer_protocol,
)
from world_career_selling import selling_enabled,enable_career_selling

VERSION="inbox-autonomous-market-v2-projected-squads"
# Irregular spacing is deliberate: a market does not mechanically bid once
# every minute. Each slot can also produce NO offer.
MARKET_MOMENTS=(35,175,355,545,735,945,1165,1385,1580,1720,1740,1765)

SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_live_market_access(
 window_id INTEGER PRIMARY KEY REFERENCES world_career_preseason_windows(window_id),
 spectator_token TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS world_career_live_player_context(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 value_gbp INTEGER NOT NULL,
 overall INTEGER NOT NULL,
 weekly_wage_estimate INTEGER NOT NULL,
 contract_years_estimate INTEGER NOT NULL,
 squad_role_estimate TEXT NOT NULL,
 transfer_listed_estimate INTEGER NOT NULL,
 model_note TEXT NOT NULL,
 PRIMARY KEY(career_id,player_id,window_id)
);
CREATE TABLE IF NOT EXISTS world_career_ai_world_moments(
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 moment_index INTEGER NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(window_id,moment_index)
);
CREATE TABLE IF NOT EXISTS world_career_market_moments(
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 moment_index INTEGER NOT NULL,
 processed_at TEXT NOT NULL,
 outcome TEXT NOT NULL,
 offer_id INTEGER,
 PRIMARY KEY(window_id,moment_index)
);
CREATE TABLE IF NOT EXISTS world_career_market_inbox(
 message_id INTEGER PRIMARY KEY,
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 offer_id INTEGER REFERENCES world_career_offers(offer_id),
 message_key TEXT NOT NULL,
 headline TEXT NOT NULL,
 detail TEXT NOT NULL,
 created_at TEXT NOT NULL,
 is_read INTEGER NOT NULL DEFAULT 0 CHECK(is_read IN (0,1)),
 UNIQUE(career_id,message_key)
);
CREATE INDEX IF NOT EXISTS world_career_market_inbox_time
 ON world_career_market_inbox(career_id,message_id DESC);
"""

def initialise_live_market(conn):
    conn.executescript(SCHEMA)
    from world_fc27_market_schedule import initialise_fc27_market_schedule
    initialise_fc27_market_schedule(conn)
    from world_offer_deadlines import initialise_confirmation_deadlines
    initialise_confirmation_deadlines(conn)
    from world_player_morale import initialise_player_morale
    initialise_player_morale(conn)
    conn.commit()

def _market_money(value):
    amount=int(value)
    prefix="-" if amount<0 else ""
    amount=abs(amount)
    if amount>=1_000_000:
        return f"{prefix}£{amount/1_000_000:,.2f}m"
    if amount>=1_000:
        return f"{prefix}£{amount/1_000:,.0f}k"
    return f"{prefix}£{amount:,}"

def _stable(*parts):
    raw="|".join(str(p) for p in parts).encode("utf8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8],"big")

def _message(conn,*,career_id,window_id,key,headline,detail,offer_id=None,when=None):
    conn.execute("""INSERT OR IGNORE INTO world_career_market_inbox
        (career_id,window_id,offer_id,message_key,headline,detail,created_at)
        VALUES(?,?,?,?,?,?,?)""",(career_id,window_id,offer_id,
        key,headline,detail,_iso(_utc(when))))

def _context(conn,*,career_id,window_id,player_id):
    r=conn.execute("""SELECT * FROM world_career_live_player_context
        WHERE career_id=? AND window_id=? AND player_id=?""",
        (career_id,window_id,player_id)).fetchone()
    return dict(r) if r is not None else None

def _seed_context(conn,*,career_id,window_id):
    """Reproducible modelled facts for the human club; never rewrite known facts."""
    c=conn.execute("""SELECT dataset_id,manager_club_id FROM world_career_saves
        WHERE career_id=?""",(career_id,)).fetchone()
    ds,manager=c
    team=conn.execute("""SELECT r.player_id,x.overall,p.primary_position
        FROM world_career_registrations r
        JOIN world_dataset_ratings x ON x.dataset_id=? AND x.player_id=r.player_id
        JOIN world_players p ON p.player_id=r.player_id
        WHERE r.career_id=? AND r.club_id=? AND x.overall IS NOT NULL
        ORDER BY x.overall DESC,r.player_id""",(ds,career_id,manager)).fetchall()
    ids=[(r[0],r[1],r[2]) for r in team
         if type(r[1]) is int and 1<=r[1]<=99]
    goalie_rank=0
    for rank,(player_id,overall,position) in enumerate(ids):
        ref,_=_player_reference(conn,ds,player_id)
        if ref is None or ref<=0:continue
        if position_family(position)=="GK":
            # Goalkeepers are competing for ONE starting place, not eleven:
            # the best GK is a regular regardless of low team-wide OVR rank.
            # A second keeper rotates; further keepers are fringe.
            role=("key_player" if goalie_rank==0 and rank<3 else
                  "regular_starter" if goalie_rank==0 else
                  "rotation" if goalie_rank==1 else "fringe")
            goalie_rank+=1
        else:
            role=("key_player" if rank<3 else "regular_starter"
                  if rank<11 else "rotation" if rank<18 else "fringe")
        contract_years=1+_stable(career_id,player_id,VERSION)%4
        listed=int(role=="fringe" and contract_years<=2)
        estimated=min(350000,max(1000,round(1000*2**((overall-55)/8)/500)*500))
        model_note=("Career-only modelling from player ability; "
                    "no verified historical wage available")
        source_contract=conn.execute("""SELECT weekly_wage_gbp,expires_on,
            source_kind FROM world_career_contract_snapshots
            WHERE career_id=? AND player_id=?""",(career_id,player_id)).fetchone()
        from world_historical_career_finances import is_historical_finance_career
        if is_historical_finance_career(conn,career_id):
            if source_contract is None or source_contract[0] is None:
                raise ValueError("Historical starting contract wage is missing")
            estimated=int(source_contract[0])
            locked=conn.execute("""SELECT pes_lock_date FROM world_career_saves
                WHERE career_id=?""",(career_id,)).fetchone()[0]
            if source_contract[1]:
                contract_years=max(1,min(10,int(source_contract[1][:4])-int(locked[:4])))
            model_note=("Starting historical contract snapshot, source or flagged "
                        "game estimate: "+str(source_contract[2]))
        manager_changes=conn.execute("""SELECT current_role,transfer_listed
            FROM world_career_player_circumstances
            WHERE career_id=? AND player_id=?""",
            (career_id,player_id)).fetchone()
        if manager_changes:
            role=manager_changes[0]
            listed=int(manager_changes[1])
        conn.execute("""INSERT OR IGNORE INTO world_career_live_player_context(
            career_id,player_id,window_id,value_gbp,overall,weekly_wage_estimate,
            contract_years_estimate,squad_role_estimate,transfer_listed_estimate,model_note)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",(career_id,player_id,window_id,ref,
            overall,estimated,contract_years,role,listed,
            model_note))
        # Feed the game's existing player-choice rules without asking
        # the human manager for missing wages or playing-time circumstances.
        existing=conn.execute("""SELECT 1 FROM world_career_player_circumstances
            WHERE career_id=? AND player_id=?""",(career_id,player_id)).fetchone()
        if existing is None:
            conn.execute("""INSERT INTO world_career_player_circumstances
                (career_id,player_id,current_wage_weekly,current_role,
                 transfer_listed,renewal_status,source_kind)
                VALUES(?,?,?,?,?,?,?)""",(career_id,player_id,estimated,role,listed,
                "not_offered" if contract_years==1 else "renewal_offered",
                "historical-contract-snapshot" if is_historical_finance_career(conn,career_id)
                else "modelled-autonomous-v1"))
    conn.commit()

def start_live_market(conn,*,career_id,now=None):
    """Explicit manager-confirmed start, idempotent on retry or reload."""
    t=_utc(now)
    prev=window_snapshot(conn,career_id=career_id,now=t)
    if prev["state"]=="not_started":
        # The existing five-stage transfer rules become the standard
        # negotiating framework; never overwrite an earlier activation.
        if not transfer_protocol_enabled(conn,career_id):
            enable_transfer_protocol(conn,career_id=career_id,
                activation_note="Autonomous pre-season career: modelled five-stage rules")
        if not selling_enabled(conn,career_id):
            enable_career_selling(conn,career_id=career_id,
                source_note="Autonomous summer market: source-labelled modelled seller facts; "
                            "the human manager decides on incoming offers")
    snap=start_preseason_window(conn,career_id=career_id,now=t)
    win=snap["window_id"]
    access=conn.execute("""SELECT spectator_token FROM world_career_live_market_access
        WHERE window_id=?""",(win,)).fetchone()
    if access is None:
        conn.execute("""INSERT OR IGNORE INTO world_career_live_market_access
            (window_id,spectator_token,created_at) VALUES(?,?,?)""",
            (win,secrets.token_urlsafe(26),_iso(t)))
        conn.commit()
    _seed_context(conn,career_id=career_id,window_id=win)
    _message(conn,career_id=career_id,window_id=win,key=f"open:{win}",
        headline="The summer transfer window is open",
        detail="AI clubs are assessing squad needs and financial constraints. "
               "Offers may arrive during the next 30 minutes. "
               "Only completed deals register before the season.",
        when=t)
    conn.commit()
    return snap

def spectator_token(conn,*,career_id):
    r=conn.execute("""SELECT a.spectator_token
        FROM world_career_live_market_access a
        JOIN world_career_preseason_windows w ON w.window_id=a.window_id
        WHERE w.career_id=? AND w.season_index=1""",(career_id,)).fetchone()
    return r[0] if r else None

def _modelled_europe(conn,*,career_id,club_id):
    """Fictional starting qualification, not real-life European results.

    A Premier League-like top-tier side's existing frozen prestige ranking
    seeds the game's initial UCL/UEL/Conference slots. Non-top-tier clubs
    enter no continental competition in this first English-world model.
    Never extrapolate a real Champions League place from squad rating alone.
    """
    row=conn.execute("""SELECT c.tier FROM world_career_saves s
        JOIN world_dataset_entries e ON e.dataset_id=s.dataset_id
        JOIN world_competitions c ON c.competition_id=e.competition_id
        WHERE s.career_id=? AND e.club_id=?
        LIMIT 1""",(career_id,club_id)).fetchone()
    if row is None:return "unknown"
    if row[0]!=1:return "none"
    ranks=conn.execute("""SELECT p.club_id,p.prestige_score FROM
        world_career_prestige_snapshots p
        JOIN world_career_saves s ON s.career_id=p.career_id
        JOIN world_dataset_entries e ON e.dataset_id=s.dataset_id
                                    AND e.club_id=p.club_id
        JOIN world_competitions c ON c.competition_id=e.competition_id
        WHERE p.career_id=? AND c.tier=1
        ORDER BY p.prestige_score DESC,p.club_id""",(career_id,)).fetchall()
    # No stored league ranking = no justified assumption about the
    # starting European status. Player decisions may then require review.
    if not ranks:return "unknown"
    positions={int(club):index for index,(club,_) in enumerate(ranks)}
    if club_id not in positions:return "unknown"
    rank=positions[club_id]
    if rank<4:return "champions_league"
    if rank==4:return "europa_league"
    if rank==5:return "conference_league"
    return "none"


def _club_led_opportunities(conn, *, career_id, window_id, candidates, slot):
    """Let buying clubs search for positional upgrades, not select a buyer
    shortlist for each managed-club player.

    All registered AI clubs independently assess their rated positional depth,
    buying capacity and the managed club's available squad. The resulting
    proposed *interests* are reproducible; they are not invented signed deals.
    """
    from collections import defaultdict
    from world_squad_planner import projected_squads, recruitment_fit, lane_of
    from world_recruitment_strategy import (
        development_signals, prospect_fit, prospect_fee_cap,
    )

    save=conn.execute("""SELECT dataset_id,manager_club_id
        FROM world_career_saves WHERE career_id=?""",(career_id,)).fetchone()
    dataset,managed_club=save
    projected=projected_squads(conn,career_id=career_id,dataset=dataset)
    from world_fc27_ai_recruitment import read_fc27_profiles
    from world_ai_tactics import preferred_formation,tactical_needs
    club_context=read_fc27_profiles(conn,dataset=dataset)
    tactical_starters={club:tactical_needs(preferred_formation(
        club_id=club,profile=profile))["starting_roles"]
        for club,profile in club_context.items()}
    scouting=development_signals(conn,dataset=dataset)
    squads=defaultdict(lambda: {"all":[]})
    for club_id,lanes in projected.items():
        for rated in lanes.values():
            squads[club_id]["all"].extend(p[1] for p in rated)
    # Explicit manager listings/outreach affect AI *interest*, not consent
    # or guaranteed offers. Other positions still compete on true squad need.
    try:
        advertised={r[0] for r in conn.execute("""SELECT player_id
            FROM world_career_squad_outreach WHERE career_id=? AND window_id=?""",
            (career_id,window_id)).fetchall()}
    except sqlite3.OperationalError:
        advertised=set()
    player_info={}
    for player_id,overall in candidates:
        context=_context(conn,career_id=career_id,window_id=window_id,
                         player_id=player_id)
        if context is None:
            continue
        position=conn.execute("""SELECT primary_position FROM world_players
            WHERE player_id=?""",(player_id,)).fetchone()
        raw_position=position[0] if position else None
        lane=lane_of(raw_position)
        # Agreed outgoing players must not be offered again, even though
        # source registration only changes at the final transfer deadline.
        if not lane or not any(p[0]==player_id for p in
                               projected.get(managed_club,{}).get(lane,[])):
            continue
        player_info[player_id]=(overall,raw_position,context)

    clubs=conn.execute("""SELECT l.club_id,c.name
        FROM world_career_club_ledger l
        JOIN world_clubs c ON c.club_id=l.club_id
        WHERE l.career_id=? AND l.club_id<>?
        ORDER BY l.club_id""",(career_id,managed_club)).fetchall()
    previous=dict(conn.execute("""SELECT o.buying_club_id,COUNT(*)
        FROM world_career_offers o
        JOIN world_career_preseason_window_offers wo ON wo.offer_id=o.offer_id
        WHERE wo.window_id=? AND o.career_id=?
          AND o.request_key LIKE 'live-v1-%'
        GROUP BY o.buying_club_id""",(window_id,career_id)).fetchall())
    # One distinct prospect pursuit per buying club each window. A genuine
    # follow-up bid for the same prospect remains possible after rejection.
    previous_prospects=defaultdict(set)
    for club,pid in conn.execute("""SELECT o.buying_club_id,o.player_id
        FROM world_career_offer_events e
        JOIN world_career_offers o ON o.offer_id=e.offer_id
        JOIN world_career_preseason_window_offers wo ON wo.offer_id=o.offer_id
        WHERE wo.window_id=? AND e.event_type='ai_prospect_approach'""",
        (window_id,)).fetchall():
        previous_prospects[club].add(pid)
    opportunities=[]
    for club_id,club_name in clubs:
        squad=squads.get(club_id)
        if not squad or len(squad["all"])<8:
            continue
        budget=budget_remaining(conn,career_id,club_id)
        if budget<=0:
            continue
        strength=sorted(squad["all"],reverse=True)
        # A realistic club seeks either positional upgrades or squad depth.
        threshold=strength[min(15,len(strength)-1)]
        targets=[]
        for player_id,(overall,position,context) in player_info.items():
            if budget<context["value_gbp"]*0.85:
                continue
            need=recruitment_fit(projected,buyer=club_id,
                                 position=position,overall=overall,
                                 starting_roles=tactical_starters.get(club_id))
            if not need["eligible"]:
                existing=previous_prospects[club_id]
                need=prospect_fit(projected,buyer=club_id,player_id=player_id,
                    position=position,overall=overall,signals=scouting,
                    existing_prospects=0 if player_id in existing else len(existing),
                    contextual_policy=club_id in club_context)
                if need["eligible"]:
                    finances=conn.execute("""SELECT transfer_budget FROM
                        world_career_club_ledger WHERE career_id=? AND club_id=?""",
                        (career_id,club_id)).fetchone()
                    if (club_id not in club_context and
                        (finances is None or context["value_gbp"]*0.85>prospect_fee_cap(
                            initial_transfer_budget=finances[0],
                            available_budget=budget))):
                        continue
            if not need["eligible"]:
                continue
            # Priority derives from the club's own weakness and the player's
            # improvement over existing depth, rather than which AI clubs
            # happen to appear on a player's top-six interest list.
            # Listing is an invitation to negotiate; direct outreach gets
            # the attention of more recruitment desks, never a forced bid.
            priority=(need["score"]+
                (12 if context["transfer_listed_estimate"] else 0)+
                (12 if player_id in advertised else 0))
            targets.append((priority,need["score"],player_id,need))
        if not targets:
            continue
        targets.sort(key=lambda x:(-x[0],
            _stable(career_id,window_id,slot,club_id,x[2],VERSION)))
        # Clubs shortlist a few prospects and favour a genuine improvement,
        # while leaving later slots free to target another position/player.
        for priority,need_score,player_id,need in targets:
            opportunities.append(({
                "club_id":club_id,"club_name":club_name,
                "need_score":need_score,"priority_score":priority,
                "need_reason":need["reason"],
                "recruitment_type":need.get("category","first_team"),
                "scouting_evidence":need.get("evidence"),
                "available_budget":budget},player_id))
    # Clubs which have not yet acted get a turn to inspect the market. Within
    # each group deterministic timing varies; neither division nor a single
    # lower-league club is guaranteed an offer.
    opportunities.sort(key=lambda pair:(
        0 if previous.get(pair[0]["club_id"],0)==0 else 1,
        previous.get(pair[0]["club_id"],0),
        _stable(career_id,window_id,slot,pair[0]["club_id"],VERSION),
        -pair[0]["need_score"],
        _stable(slot,pair[1],VERSION)))
    return opportunities

def _consider_bid(conn,*,career_id,window_id,slot,t):
    """Exactly one plausible proposal opportunity per due market moment."""
    from world_recruitment_strategy import prospect_fee_cap
    from world_fc27_ai_recruitment import read_fc27_profiles
    row=conn.execute("""SELECT c.dataset_id,c.manager_club_id,c.pes_lock_date
        FROM world_career_saves c WHERE c.career_id=?""",(career_id,)).fetchone()
    dataset,manager,pes_lock=row
    # Every generated bid must stand on its sporting and financial merit.
    # The managed club's inbox has no artificial total or GK-specific quota.
    candidates=conn.execute("""SELECT player_id,overall
        FROM world_career_live_player_context
        WHERE career_id=? AND window_id=?
        ORDER BY overall DESC,player_id""",(career_id,window_id)).fetchall()
    if not candidates:return None,"No eligible rated human-club players"
    # Clubs establish their own transfer targets from squad needs. An
    # eligible player alone no longer determines which clubs are consulted.
    opportunities=_club_led_opportunities(conn,career_id=career_id,
        window_id=window_id,candidates=candidates,slot=slot)
    for buyer,player_id in opportunities:
        context=_context(conn,career_id=career_id,window_id=window_id,
                         player_id=player_id)
        if not context:
            continue
        rivals=len({other["club_id"] for other,pid in opportunities
                    if pid==player_id})
        rivals=min(25,rivals)
        buyer_id=buyer["club_id"]
        if buyer_id==manager:continue
        pos=conn.execute("SELECT primary_position FROM world_players WHERE player_id=?",
                         (player_id,)).fetchone()
        history=conn.execute("""SELECT offer_id,offered_fee,status FROM
            world_career_offers WHERE career_id=? AND player_id=?
            AND buying_club_id=? AND request_key LIKE 'live-v1-%'
            ORDER BY offer_id""",(career_id,player_id,buyer_id)).fetchall()
        if history and (history[-1][2]!="rejected" or len(history)>=3):
            continue
        rnd=len(history)+1
        prev=history[-1][1] if history else None
        money=budget_remaining(conn,career_id,buyer_id)
        if money<=0:continue
        active=conn.execute("""SELECT COUNT(DISTINCT buying_club_id)
            FROM world_career_offers WHERE career_id=? AND player_id=?
            AND buying_club_id<>? AND status IN
            ('proposed','countered','accepted_pending_contract','agreed_future')""",
            (career_id,player_id,buyer_id)).fetchone()[0]
        # The source is explicitly marked as simulated circumstances;
        # no player's genuine private intentions are asserted.
        request=conn.execute("""SELECT status FROM world_career_player_morale
            WHERE career_id=? AND window_id=? AND player_id=?""",
            (career_id,window_id,player_id)).fetchone()
        if request and request[0]=="refusing_to_play":
            continue
        seller=dict(transfer_listed=context["transfer_listed_estimate"],
            player_wants_exit=bool(request) or context["transfer_listed_estimate"],
            contract_years=context["contract_years_estimate"],
            squad_role=context["squad_role_estimate"])
        price=determine_offer(career_id=career_id,player_id=player_id,
            club_id=buyer_id,valuation=context["value_gbp"],
            available_budget=money,need_score=int(buyer["need_score"]),
            eligible_clubs=rivals,active_rival_clubs=active,
            seller_assumptions=seller,prior_fee=prev,round_number=rnd)
        if price["fee"] is None:continue
        if (buyer["recruitment_type"]=="prospect" and not
                read_fc27_profiles(conn,dataset=dataset,club_id=buyer_id)):
            initial=conn.execute("""SELECT transfer_budget FROM
                world_career_club_ledger WHERE career_id=? AND club_id=?""",
                (career_id,buyer_id)).fetchone()
            if initial is None or price["fee"]>prospect_fee_cap(
                    initial_transfer_budget=initial[0],available_budget=money):
                continue
        from datetime import date
        game_date=(date.fromisoformat(pes_lock)-timedelta(days=1)).isoformat()
        key=f"live-v1-{window_id}-{slot}-{player_id}-{buyer_id}-r{rnd}"
        audit={**price,"buyer_name":buyer["club_name"],
            "need_reason":buyer["need_reason"],
            "recruitment_type":buyer["recruitment_type"],
            "scouting_evidence":buyer["scouting_evidence"],
            "prior_offer_id":
            history[-1][0] if history else None,
            "note":"Fictional autonomous player and club assessment. "
                   "No verified wage, intentions or real transfer rumour."}
        offer_id=propose_offer(conn,career_id=career_id,request_key=key,
            player_id=player_id,buying_club_id=buyer_id,
            offered_fee=price["fee"],agreement_date=game_date,
            ai_bid_snapshot=audit,autonomous_inbox=True)
        if buyer["recruitment_type"]=="prospect":
            conn.execute("""INSERT INTO world_career_offer_events
                (offer_id,event_type,detail) VALUES(?,?,?)""",
                (offer_id,"ai_prospect_approach",
                 "Long-term scouting bid, not current starting-XI improvement"))
        # Fictional *career* European places use saved club prestige,
        # not undocumented real-world Champions League claims. The
        # actual qualification table can supersede this in the future.
        buyer_europe=_modelled_europe(conn,career_id=career_id,
                                     club_id=buyer_id)
        seller_europe=_modelled_europe(conn,career_id=career_id,
                                      club_id=manager)
        conn.execute("""INSERT OR IGNORE INTO world_career_offer_europe
            (career_id,offer_id,buyer_europe,seller_europe,source_kind)
            VALUES(?,?,?,?,?)""",
            (career_id,offer_id,buyer_europe,seller_europe,
             "fictional-preseason-prestige-seeding-v1"))
        name=conn.execute("SELECT full_name FROM world_players WHERE player_id=?",
                          (player_id,)).fetchone()[0]
        text=(f"{buyer['club_name']} offer {_market_money(price['fee'])} for {name}. "
              f"{'Development investment' if buyer['recruitment_type']=='prospect' else 'Squad need'} "
              f"{buyer['need_score']}/100; "
              f"{rivals} prospective clubs for this player. "
              f"{'Improved offer after rejection.' if rnd>1 else 'Opening approach.'}")
        _message(conn,career_id=career_id,window_id=window_id,
            key=f"offer:{offer_id}",headline=(
                "Improved AI transfer offer" if rnd>1 else "New transfer offer"),
            detail=text,offer_id=offer_id,when=t)
        conn.commit()
        return offer_id,text
    return None,"No buyer met squad fit, valuation, budget and negotiation limits"

def _respond_to_counter(conn,*,career_id,offer_id,window_id,t):
    """Automated club reaction to a human manager's proposed selling price."""
    from world_ai_bidding import round_up_fee
    o=conn.execute("""SELECT player_id,buying_club_id,demanded_fee,offered_fee
        FROM world_career_offers WHERE career_id=? AND offer_id=? AND status='countered'""",
        (career_id,offer_id)).fetchone()
    if o is None:return False
    player,buyer,counter,original=o
    context=_context(conn,career_id=career_id,window_id=window_id,player_id=player)
    if context is None:return False
    if counter is None:return False
    available=budget_remaining(conn,career_id,buyer)
    # Counter fee is reserved and already subtracted by budget_remaining;
    # add its own reservation back when assessing this one bid.
    ceiling=round_up_fee(context["value_gbp"]*1.48)
    budget_headroom=available+counter
    approved=counter<=ceiling and counter<=budget_headroom
    if approved:
        conn.execute("""UPDATE world_career_offers SET status='accepted_pending_contract',
            offered_fee=demanded_fee,demanded_fee=NULL WHERE offer_id=?""",(offer_id,))
        headline="Buying club accepts your counteroffer"
        detail=f"Counteroffer of £{counter:,} accepted subject to player and agent agreement."
        event="ai_counter_accepted"
    else:
        conn.execute("""UPDATE world_career_offers SET status='rejected'
            WHERE offer_id=?""",(offer_id,))
        headline="Buying club walks away"
        detail="The counteroffer exceeds the buyer's prudent valuation or remaining transfer funds."
        event="ai_counter_declined"
    conn.execute("""INSERT INTO world_career_offer_events
        (offer_id,event_type,detail) VALUES(?,?,?)""",(offer_id,event,detail))
    _message(conn,career_id=career_id,window_id=window_id,
        key=f"response:{offer_id}",headline=headline,detail=detail,
        offer_id=offer_id,when=t)
    conn.commit()
    return True

def process_live_market(conn,*,career_id,now=None,
                        fc27_activity_scale_qa=1):
    """Reconcile due market moments, then close at 30 min; safe on rerun.

    Each moment's row is unique and each AI proposal has an immutable request
    key, so polling/reloading cannot create duplicate offers. The deadline is
    checked against the server's UTC clock, never a browser-provided timestamp.
    """
    t=_utc(now)
    snap=window_snapshot(conn,career_id=career_id,now=t)
    if snap["state"]=="not_started":
        return {"state":"not_started","changed":False,"new_offers":0}
    if snap["state"]=="closed":
        return {"state":"closed","changed":False,"new_offers":0}
    win=snap["window_id"]
    if fc27_activity_scale_qa not in (1,3):
        raise ValueError("Unsupported isolated FC27 activity scenario")
    from world_fc27_market_schedule import (
        is_fc27_market,process_fc27_market_interval)
    fc27_club_led=is_fc27_market(conn,career_id=career_id)
    if fc27_activity_scale_qa!=1 and not fc27_club_led:
        raise ValueError("QA scaling cannot apply to existing non-FC27 careers")
    if snap["state"]=="deadline_reached":
        from world_player_morale import reconcile_player_morale
        reconcile_player_morale(conn,career_id=career_id,
                                now=datetime.fromisoformat(snap["deadline_at"]))
        result=finalise_preseason_window(conn,career_id=career_id,now=t)
        _message(conn,career_id=career_id,window_id=win,
            key=f"closed:{win}",headline="The transfer window has closed",
            detail=(f"{result['registered']} completed transfer(s) registered "
                    f"for the new season; {result['expired']} unfinished talks expired."),
            when=t)
        conn.commit()
        return {**result,"state":"closed","changed":True,"new_offers":0}

    from world_offer_deadlines import reconcile_confirmations
    confirmation_changes=reconcile_confirmations(conn,career_id=career_id,now=t)
    started=datetime.fromisoformat(snap["started_at"])
    elapsed=(t-started).total_seconds()
    new_offers=0
    changed=False
    for index,offset in enumerate(MARKET_MOMENTS):
        if elapsed<offset:break
        seen=conn.execute("""SELECT 1 FROM world_career_market_moments
            WHERE window_id=? AND moment_index=?""",(win,index)).fetchone()
        if seen:
            if fc27_club_led:
                # Recovery if a process died after recording the real-time
                # interval but before clearing the durable club activity plan.
                process_fc27_market_interval(conn,career_id=career_id,
                    window_id=win,interval_index=index,when=t,activity_scale_qa=fc27_activity_scale_qa)
            continue
        # Deal with accepted human fee decisions and manager counters on
        # each market moment, not on each page refresh.
        unresolved=conn.execute("""SELECT o.offer_id,o.status FROM
            world_career_preseason_window_offers wt
            JOIN world_career_offers o ON o.offer_id=wt.offer_id
            WHERE wt.window_id=? AND o.career_id=?
              AND o.selling_club_id=(SELECT manager_club_id
                  FROM world_career_saves WHERE career_id=?)
              AND o.status IN ('countered','accepted_pending_contract')
            ORDER BY o.offer_id""",(win,career_id,career_id)).fetchall()
        for oid,status in unresolved[:12]:
            if status=="countered":
                _respond_to_counter(conn,career_id=career_id,offer_id=oid,
                                    window_id=win,t=t)
            else:
                try:
                    before=incoming_approach(conn,oid)
                    after=advance_incoming_approach(conn,career_id=career_id,offer_id=oid)
                    if (after and after["status"]!="needs_information" and
                        (before is None or after["status"]!=before["status"])):
                        _message(conn,career_id=career_id,window_id=win,
                            key=f"agent:{oid}:{after['attempts']}:{after['status']}",
                            headline=("Player terms agreed" if
                                      after["status"]=="terms_accepted"
                                      else "Agent negotiation update"),
                            detail=after["decision_reason"],offer_id=oid,when=t)
                        conn.commit()
                except (ValueError,sqlite3.OperationalError) as exc:
                    # Player consent/agent constraints are real vetoes. Do
                    # not invent a signing to keep the narrative moving.
                    _message(conn,career_id=career_id,window_id=win,
                        key=f"agent-blocked:{oid}:{index}",
                        headline="Player talks cannot progress",
                        detail=str(exc)[:260],offer_id=oid,when=t)
                    conn.commit()
        try:
            offer_id,outcome=_consider_bid(conn,career_id=career_id,
                                          window_id=win,slot=index,t=t)
        except ValueError as exc:
            # Failed eligibility never manufactures an offer.
            offer_id,outcome=None,"No eligible offer: "+str(exc)[:220]
        if fc27_club_led:
            # All solvent source-rated clubs make their own activity choice.
            # The count of interested clubs changes with current tactical
            # needs, club ambitions, budgets, recent sales, and the interval.
            # There is no "112 opportunities" formula for FC27 worlds.
            process_fc27_market_interval(conn,career_id=career_id,
                window_id=win,interval_index=index,when=t,
                activity_scale_qa=fc27_activity_scale_qa)
        else:
            # IMMUTABLE older careers use their original replay-safe moment
            # keys and original 112 checks. Do not renumber historical slots.
            from world_ai_world import consider_ai_world_deal
            attempts=(5 if index<4 else
                      10 if index<6 else
                      13 if index==6 else
                      18 if index==7 else
                      11 if index==8 else 10)
            for round_index in range(attempts):
                world_slot=(index if round_index==0 else
                    len(MARKET_MOMENTS)+index*3+round_index-1
                    if round_index<4 else
                    len(MARKET_MOMENTS)*4+index*16+round_index-4)
                consider_ai_world_deal(conn,career_id=career_id,
                                       window_id=win,slot=world_slot,now=t)
        from world_player_morale import reconcile_player_morale
        reconcile_player_morale(conn,career_id=career_id,now=t)
        conn.execute("""INSERT OR IGNORE INTO world_career_market_moments
            (window_id,moment_index,processed_at,outcome,offer_id)
            VALUES(?,?,?,?,?)""",(win,index,_iso(t),outcome,offer_id))
        conn.commit()
        changed=True
        if offer_id:new_offers+=1
    # Freshly accepted agent terms from a due market moment begin their
    # own confirmation timer immediately, not on the next browser visit.
    newly_ready=reconcile_confirmations(conn,career_id=career_id,now=t)
    changed=(changed or bool(confirmation_changes["expired"]) or
             bool(newly_ready["opened"]) or bool(newly_ready["expired"]))
    return {"state":"open","changed":changed,"new_offers":new_offers}

def manager_respond(conn,*,career_id,offer_id,action,counter_fee=None,now=None):
    """Human decisions: accept, counter or reject fee; later approve signed deal."""
    snap=assert_window_allows_negotiation(conn,career_id=career_id,now=now)
    if snap is None:raise ValueError("Start the pre-season window first")
    from world_offer_deadlines import (
        reconcile_confirmations, request_confirmation_extension,
        confirmation_state,
    )
    reconcile_confirmations(conn,career_id=career_id,now=now)
    row=conn.execute("""SELECT o.offer_id,o.status,o.offered_fee,o.player_id,
        o.buying_club_id,o.selling_club_id,c.manager_club_id
        FROM world_career_offers o JOIN world_career_saves c
        ON c.career_id=o.career_id WHERE o.career_id=? AND o.offer_id=?
        AND EXISTS (SELECT 1 FROM world_career_preseason_window_offers wt
          WHERE wt.offer_id=o.offer_id AND wt.window_id=?)""",
        (career_id,offer_id,snap["window_id"])).fetchone()
    if row is None or row[5]!=row[6] or row[4]==row[6]:
        raise ValueError("Only the manager may respond to their club's live incoming bids")
    status=row[1]
    if action=="cancel":
        if status not in ("proposed","countered","accepted_pending_contract"):
            raise ValueError("Only an unsigned transfer can be cancelled")
        from world_careers import withdraw_offer
        withdraw_offer(conn,career_id=career_id,offer_id=offer_id)
        _message(conn,career_id=career_id,window_id=snap["window_id"],
            key=f"manager:cancel:{offer_id}",headline="Transfer talks cancelled",
            detail="You cancelled the unsigned transfer. No player will be registered.",
            offer_id=offer_id,when=now)
        conn.commit()
        result="Unsigned transfer cancelled; no deal will register."
    elif action=="reject":
        if status!="proposed":
            raise ValueError("Only an opening bid can be rejected")
        reject_incoming_offer(conn,career_id=career_id,offer_id=offer_id)
        result="Rejected. The AI club might submit a better offer later."
    elif action in ("accept","counter"):
        if status!="proposed":
            raise ValueError("Only a pending incoming bid can be accepted or countered")
        if action=="counter":
            if type(counter_fee) is not int or not row[2]<counter_fee<=1_000_000_000:
                raise ValueError("Counteroffer must exceed the original fee")
            if counter_fee>row[2]*2:
                raise ValueError("A single counteroffer cannot more than double the proposed fee")
            next_status="countered"
        else:
            next_status="accepted_pending_contract"
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("""UPDATE world_career_offers
                SET status=?,demanded_fee=? WHERE offer_id=?""",
                (next_status,counter_fee if action=="counter" else None,offer_id))
            conn.execute("""INSERT INTO world_career_offer_events
                (offer_id,event_type,detail) VALUES(?,?,?)""",
                (offer_id,"human_countered" if action=="counter" else "human_fee_accepted",
                 f"Human manager {action}ed AI offer; no player transfer or consent implied"))
            _message(conn,career_id=career_id,window_id=snap["window_id"],
                key=f"manager:{action}:{offer_id}",
                headline="Your transfer decision has been recorded",
                detail=(f"You have asked {_market_money(counter_fee)} for this player; buyer must respond."
                        if action=="counter" else
                        "You accepted the fee, subject to separate player and agent agreement."),
                offer_id=offer_id,when=now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        result="Counteroffer sent." if action=="counter" else "Fee accepted; player talks will follow."
    elif action=="delay":
        decision=request_confirmation_extension(
            conn,career_id=career_id,offer_id=offer_id,now=now)
        result=decision["reason"]
    elif action=="finalise":
        state=incoming_approach(conn,offer_id)
        confirmation=confirmation_state(
            conn,career_id=career_id,offer_id=offer_id,now=now)
        if confirmation and (
                confirmation["expired_at"] is not None or
                confirmation["remaining_seconds"]<=0):
            raise ValueError("The buying club has withdrawn after its signing deadline")
        if status!="accepted_pending_contract" or not state or state["status"]!="terms_accepted":
            raise ValueError("Player and agent must accept personal terms before signing")
        finalise_incoming_approach(conn,career_id=career_id,offer_id=offer_id,now=now)
        _message(conn,career_id=career_id,window_id=snap["window_id"],
            key=f"manager:finalise:{offer_id}",headline="Transfer agreement signed",
            detail="Fully signed deal will register at the transfer deadline. "
                   "The Xbox PES game file is not modified.",offer_id=offer_id,when=now)
        conn.commit()
        result="Signed deal confirmed; registration is scheduled for the deadline."
    else:
        raise ValueError("Unsupported manager action")
    return result

def mark_market_read(conn,*,career_id):
    """Only a manager-authorised HTTP POST may mark inbox notifications read.

    Reading news is not a transfer action and remains possible after the
    deadline, but it never starts or extends a window.
    """
    snap=window_snapshot(conn,career_id=career_id)
    if snap["state"]=="not_started":
        return 0
    cur=conn.execute("""UPDATE world_career_market_inbox
        SET is_read=1 WHERE career_id=? AND is_read=0""",(career_id,))
    conn.commit()
    return cur.rowcount


def market_messages(conn,*,career_id):
    rows=conn.execute("""SELECT m.message_id,m.headline,m.detail,m.created_at,
        m.is_read,m.offer_id,p.full_name AS player_name,
        b.name AS buyer_name,o.status AS offer_status,o.offered_fee,
        o.demanded_fee,ia.status AS player_status,
        ia.decision_reason AS player_reason
        FROM world_career_market_inbox m
        LEFT JOIN world_career_offers o ON o.offer_id=m.offer_id
        LEFT JOIN world_players p ON p.player_id=o.player_id
        LEFT JOIN world_clubs b ON b.club_id=o.buying_club_id
        LEFT JOIN world_career_incoming_approaches ia ON ia.offer_id=o.offer_id
        WHERE m.career_id=? ORDER BY m.message_id DESC LIMIT 70""",
        (career_id,)).fetchall()
    return [dict(x) for x in rows]
