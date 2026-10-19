"""Manager-initiated purchases in the 30-minute autonomous pre-season market.

The human manager chooses targets and terms; they NEVER supply seller facts.
Modelled player/club circumstances have explicit provenance and are frozen
per saved career. The existing seller, player, agent and board decision
engines remain authoritative. This module cannot edit the Xbox PES save.
"""
from datetime import date,timedelta
import sqlite3

from world_preseason_window import assert_window_allows_negotiation
from world_careers import (
    _player_reference,propose_offer,accept_counter,agent_terms,negotiate_agent,
    confirm_future_agreement,budget_remaining,
)
from world_career_selling import (
    get_seller_assumptions,record_seller_assumptions,
)
from world_live_market import _stable,_modelled_europe,_message,VERSION

POLICY_VERSION="human-buying-autonomous-seller-v1"


def _buyer_target(conn,*,career_id,player_id):
    row=conn.execute("""SELECT s.dataset_id,s.manager_club_id,s.pes_lock_date,
        r.club_id,p.full_name,x.overall
        FROM world_career_saves s
        JOIN world_career_registrations r ON r.career_id=s.career_id
        JOIN world_players p ON p.player_id=r.player_id
        LEFT JOIN world_dataset_ratings x ON x.dataset_id=s.dataset_id
             AND x.player_id=r.player_id
        WHERE s.career_id=? AND s.state='sandbox' AND r.player_id=?""",
        (career_id,player_id)).fetchone()
    if row is None:
        raise ValueError("Select a player registered in this career")
    dataset,manager,pes_date,seller,name,overall=row
    if seller==manager:
        raise ValueError("This player is already in your squad")
    if type(overall) is not int or not 1<=overall<=99:
        raise ValueError("A PES-compatible player rating is needed before an offer can be made")
    value,_=_player_reference(conn,dataset,player_id)
    if type(value) is not int or value<=0:
        raise ValueError("The player has no valid source-rated market valuation")
    return dict(dataset=dataset,manager=manager,pes_date=pes_date,
                seller=seller,name=name,overall=overall,value=value)


def _model_player_and_seller(conn,*,career_id,player_id,target):
    """Fill missing facts from a documented fictional policy, never user forms.

    Recorded historical circumstances always win. We cannot retroactively
    alter frozen seller assumptions, even if they predate the timed window.
    """
    rows=conn.execute("""SELECT r.player_id,x.overall
        FROM world_career_registrations r
        JOIN world_dataset_ratings x ON x.dataset_id=? AND x.player_id=r.player_id
        WHERE r.career_id=? AND r.club_id=? AND x.overall IS NOT NULL
        ORDER BY x.overall DESC,r.player_id""",
        (target["dataset"],career_id,target["seller"])).fetchall()
    ranked=[(int(pid),int(rating)) for pid,rating in rows if
            type(rating) is int and 1<=rating<=99]
    if len(ranked)<8:
        raise ValueError("Selling club has insufficient rated squad depth for a reliable response")
    order=[pid for pid,rating in ranked]
    rank=order.index(player_id)
    role=("key_player" if rank<3 else "regular_starter" if rank<11
          else "rotation" if rank<18 else "fringe")
    term=1+_stable(career_id,player_id,VERSION)%4
    listed=role=="fringe" and term<=2
    estimated=min(350000,max(1000,round(
        1000*2**((target["overall"]-55)/8)/500)*500))
    existing=get_seller_assumptions(conn,career_id,player_id)
    if existing is None:
        record_seller_assumptions(
            conn,career_id=career_id,player_id=player_id,
            market_value=target["value"],contract_years=term,
            squad_role=role,transfer_listed=listed,player_wants_exit=listed,
            financial_state="stable",
            replacement="difficult" if rank<11 else "available",
            seller_stance=("retain" if rank<3 else
                           "neutral" if rank<18 else "sell"),
            board_enabled=False,
            source_note=(
                "fictional-autonomous-seller-v1: PES player rating, "
                "selling-club ranked squad depth, deterministic contract proxy; "
                "not a verified real salary, player intention or contract."))
    known=conn.execute("""SELECT 1 FROM world_career_player_circumstances
        WHERE career_id=? AND player_id=?""",(career_id,player_id)).fetchone()
    if known is None:
        conn.execute("""INSERT OR IGNORE INTO world_career_player_circumstances
            (career_id,player_id,current_wage_weekly,current_role,
             transfer_listed,renewal_status,source_kind)
            VALUES(?,?,?,?,?,?,?)""",
            (career_id,player_id,estimated,role,int(listed),
             "not_offered" if term==1 else "renewal_offered",
             "fictional-autonomous-seller-v1"))
        conn.commit()
    return dict(role=role,contract_years=term,listed=listed,rank=rank+1,
                modelled_wage=estimated)


def _agent_opening_quote(conn, *, career_id, offer_id, window_id, now=None):
    """Invite the agent to provide an opening wage, never auto-accept terms."""
    from world_careers import agent_terms
    existing=conn.execute("""SELECT demanded_wage_weekly FROM world_career_agent_terms
        WHERE career_id=? AND offer_id=?""",(career_id,offer_id)).fetchone()
    if existing:
        return existing[0]
    terms=agent_terms(conn,career_id=career_id,offer_id=offer_id)
    demand=terms["demanded_wage_weekly"]
    _message(conn,career_id=career_id,window_id=window_id,
        key=f"agent-opening-wage:{offer_id}",offer_id=offer_id,when=now,
        headline="Agent makes opening wage request",
        detail=f"Player's agent requests £{demand:,} per week. Submit your preferred contract terms.")
    conn.commit()
    return demand


def submit_buy_offer(conn,*,career_id,player_id,offered_fee,request_key,now=None):
    """Make a real recorded offer; AI seller responds from frozen model inputs."""
    snap=assert_window_allows_negotiation(conn,career_id=career_id,now=now)
    if snap is None:raise ValueError("Start the 30-minute summer window first")
    if type(player_id) is not int or type(offered_fee) is not int:
        raise ValueError("Choose a player and an integer transfer fee")
    if not 0<offered_fee<=1_000_000_000:
        raise ValueError("Transfer fee must be a positive whole-pound amount")
    if not isinstance(request_key,str) or not request_key.startswith("manager-buy-v1-"):
        raise ValueError("This offer must originate from the career's buying form")
    saved=conn.execute("""SELECT offer_id,status FROM world_career_offers
        WHERE career_id=? AND request_key=?""",(career_id,request_key)).fetchone()
    if saved:
        return {"offer_id":saved[0],"status":saved[1],"existing":True}
    target=_buyer_target(conn,career_id=career_id,player_id=player_id)
    if offered_fee>budget_remaining(conn,career_id,target["manager"]):
        raise ValueError("Your offer exceeds your unreserved transfer funds")
    _model_player_and_seller(conn,career_id=career_id,
                             player_id=player_id,target=target)
    game_date=(date.fromisoformat(target["pes_date"])-
               timedelta(days=1)).isoformat()
    offer_id=propose_offer(conn,career_id=career_id,request_key=request_key,
        player_id=player_id,buying_club_id=target["manager"],
        offered_fee=offered_fee,agreement_date=game_date)
    # Continental participation affects consent; fictional career estimate,
    # not an assertion of real Champions League qualification.
    conn.execute("""INSERT OR IGNORE INTO world_career_offer_europe
        (career_id,offer_id,buyer_europe,seller_europe,source_kind)
        VALUES(?,?,?,?,?)""",
        (career_id,offer_id,
         _modelled_europe(conn,career_id=career_id,club_id=target["manager"]),
         _modelled_europe(conn,career_id=career_id,club_id=target["seller"]),
         "fictional-preseason-prestige-seeding-v1"))
    status=conn.execute("SELECT status FROM world_career_offers WHERE offer_id=?",
                        (offer_id,)).fetchone()[0]
    club=conn.execute("SELECT name FROM world_clubs WHERE club_id=?",
                      (target["seller"],)).fetchone()[0]
    _message(conn,career_id=career_id,window_id=snap["window_id"],
        key=f"manager-bid:{offer_id}",offer_id=offer_id,when=now,
        headline=("Transfer bid rejected by selling club" if status=="rejected"
                  else "Selling club makes a counteroffer" if status=="countered"
                  else "Transfer fee agreed, player talks pending"
                  if status=="accepted_pending_contract"
                  else "Your transfer offer submitted"),
        detail=(f"£{offered_fee:,} bid for {target['name']} of {club}. "
                f"Selling club response: {status.replace('_',' ')}. "
                "No sale is final until the player and agent agree terms."))
    conn.commit()
    if status=="accepted_pending_contract":
        try:
            _agent_opening_quote(conn,career_id=career_id,offer_id=offer_id,
                                 window_id=snap["window_id"],now=now)
        except ValueError:
            # A player refusing talks must not be silently deemed signed.
            # The original agreed fee and any refusal remain visible.
            pass
    return {"offer_id":offer_id,"status":status,"existing":False}


def negotiate_seller_counter(conn, *, career_id, offer_id, offered_fee, now=None):
    """Human buyer proposes an intermediate fee in response to a seller counter.

    The seller may accept, refuse or lower its asking price. A new counter
    supersedes the previous number but never overwrites the historical
    selling-club decision snapshot. No transfer is signed automatically.
    """
    from world_ai_bidding import round_up_fee
    snap=assert_window_allows_negotiation(conn,career_id=career_id,now=now)
    if snap is None:raise ValueError("Start the 30-minute window first")
    if type(offered_fee) is not int or offered_fee<=0 or offered_fee>1_000_000_000:
        raise ValueError("Enter a positive whole-pound transfer fee")
    row=conn.execute("""SELECT o.offered_fee,o.demanded_fee,o.status,
        o.player_id,o.buying_club_id,c.manager_club_id
        FROM world_career_offers o JOIN world_career_saves c
          ON c.career_id=o.career_id
        JOIN world_career_preseason_window_offers wt ON wt.offer_id=o.offer_id
        WHERE o.career_id=? AND o.offer_id=? AND wt.window_id=?""",
        (career_id,offer_id,snap["window_id"])).fetchone()
    if (not row or row[4]!=row[5] or row[2]!="countered"
            or row[1] is None):
        raise ValueError("No selling-club counteroffer is available to negotiate")
    old_bid,asking,_,player_id,buyer,_=row
    if not old_bid<offered_fee<asking:
        raise ValueError("Your revised bid must exceed your last bid and remain below the asking price")
    used=conn.execute("""SELECT COUNT(*) FROM world_career_offer_events
        WHERE offer_id=? AND event_type='buyer_revised_bid'""",
        (offer_id,)).fetchone()[0]
    if used>=2:raise ValueError("Maximum two revised bids reached. Accept the counter or withdraw.")
    current=budget_remaining(conn,career_id,buyer)
    # budget_remaining already subtracts the old reserved asking fee.
    if current+asking<offered_fee:
        raise ValueError("Your revised fee exceeds remaining available funds")
    seller=get_seller_assumptions(conn,career_id,player_id)
    # Selling clubs have distinct priorities. A valuable first-teamer at a
    # reluctant club is much harder to move than a listed fringe player.
    hardline=bool(seller and not seller["transfer_listed"] and
        (seller["seller_stance"]=="retain" or
         seller["squad_role"]=="key_player"))
    flexible=bool(seller and (seller["transfer_listed"] or
        seller["squad_role"]=="fringe"))
    threshold=round_up_fee(asking*(0.96 if hardline else
                                   0.86 if flexible else 0.9))
    if offered_fee>=threshold:
        status="accepted_pending_contract"
        demanded=None
        result=("Selling club accepts your revised fee of "
                f"{offered_fee:,} GBP. Player terms are now available.")
        event="seller_revised_bid_accepted"
    else:
        # The AI seller stands by its original desire to retain value,
        # but can narrow the gap rather than always holding firm.
        demanded=(asking if hardline else
                  min(asking,round_up_fee((offered_fee+asking)/2)))
        if demanded<=offered_fee:demanded=asking
        status="countered"
        result=(f"Selling club counters at {demanded:,} GBP after reviewing "
                f"your revised {offered_fee:,} GBP bid.")
        event="seller_revised_asking"
    conn.execute("""UPDATE world_career_offers SET offered_fee=?,
        demanded_fee=?,status=? WHERE career_id=? AND offer_id=?""",
        (offered_fee,demanded,status,career_id,offer_id))
    conn.execute("""INSERT INTO world_career_offer_events
        (offer_id,event_type,detail) VALUES(?,?,?)""",
        (offer_id,"buyer_revised_bid",f"Manager proposed £{offered_fee:,}"))
    conn.execute("""INSERT INTO world_career_offer_events
        (offer_id,event_type,detail) VALUES(?,?,?)""",
        (offer_id,event,str(demanded) if demanded is not None else result))
    _message(conn,career_id=career_id,window_id=snap["window_id"],
        key=f"seller-counter-response:{offer_id}:{used+1}",
        headline=("Seller accepts your negotiated fee" if demanded is None else
                  "Seller makes a revised counteroffer"),
        detail=result,offer_id=offer_id,when=now)
    conn.commit()
    return result


def act_on_buy_offer(conn,*,career_id,offer_id,action,weekly_wage=None,
                     contract_years=3,role_promise="regular_starter",
                     negotiated_fee=None,now=None):
    """One manager decision on a tagged outgoing offer; never AI simulation."""
    snap=assert_window_allows_negotiation(conn,career_id=career_id,now=now)
    if snap is None:raise ValueError("Start the transfer window first")
    row=conn.execute("""SELECT o.status,o.agreement_date,o.offered_fee,
        o.demanded_fee,o.player_id FROM world_career_offers o
        JOIN world_career_saves c ON c.career_id=o.career_id
        JOIN world_career_preseason_window_offers wt ON wt.offer_id=o.offer_id
        WHERE o.career_id=? AND o.offer_id=?
        AND o.buying_club_id=c.manager_club_id
        AND o.selling_club_id<>c.manager_club_id AND wt.window_id=?""",
        (career_id,offer_id,snap["window_id"])).fetchone()
    if row is None:
        raise ValueError("Only your own outgoing transfer offers can be managed here")
    status,agreement_date,fee,counter,player_id=row
    if action=="negotiate_counter":
        result=negotiate_seller_counter(
            conn,career_id=career_id,offer_id=offer_id,
            offered_fee=negotiated_fee,now=now)
        signed_fee=conn.execute("""SELECT status FROM world_career_offers
            WHERE offer_id=?""",(offer_id,)).fetchone()[0]
        if signed_fee=="accepted_pending_contract":
            try:
                _agent_opening_quote(conn,career_id=career_id,offer_id=offer_id,
                    window_id=snap["window_id"],now=now)
            except ValueError:
                pass
        return result
    if action=="request_agent":
        if status!="accepted_pending_contract":
            raise ValueError("Agree a fee before contacting the player's agent")
        quote=_agent_opening_quote(conn,career_id=career_id,offer_id=offer_id,
                                   window_id=snap["window_id"],now=now)
        return f"Agent's opening wage request: £{quote:,}/week."
    if action=="accept_counter":
        if status!="countered":raise ValueError("No selling-club counteroffer remains open")
        accept_counter(conn,career_id=career_id,offer_id=offer_id)
        result="Seller's counteroffer accepted. You can now negotiate with the player."
    elif action=="terms":
        if status!="accepted_pending_contract":
            raise ValueError("Agree a transfer fee with the selling club first")
        if type(weekly_wage) is not int or not 0<=weekly_wage<=1_000_000:
            raise ValueError("Enter a valid whole-pound weekly wage")
        if type(contract_years) is not int or contract_years not in (1,2,3,4,5):
            raise ValueError("Contracts must be one to five years")
        if role_promise not in ("key_player","regular_starter","rotation","fringe"):
            raise ValueError("Choose a credible playing-time commitment")
        # initialise agent terms if needed, then apply existing detailed
        # player-prestige/squad-role/wage/European decision policy.
        agent_terms(conn,career_id=career_id,offer_id=offer_id)
        response=negotiate_agent(conn,career_id=career_id,offer_id=offer_id,
            weekly_wage=weekly_wage,contract_years=contract_years,
            role_promise=role_promise,agreement_date=agreement_date)
        result=("Player and agent accepted. Confirm the signing before the deadline."
                if response=="accepted" else
                "Agent countered: review the demanded wage and submit improved terms.")
    elif action=="sign":
        if status!="accepted_pending_contract":
            raise ValueError("The player is not awaiting your final confirmation")
        competing=conn.execute("""SELECT 1 FROM world_career_offers
            WHERE career_id=? AND player_id=? AND offer_id<>?
              AND status IN ('agreed_future','completed') LIMIT 1""",
            (career_id,player_id,offer_id)).fetchone()
        if competing:
            raise ValueError("This player has already agreed to join another club")
        # A rival club may have agreed a fee since the player's first yes.
        # Reconsider his sporting and wage preferences at signing time.
        from world_career_incoming import competing_player_choice
        choice=competing_player_choice(conn,career_id=career_id,offer_id=offer_id)
        if choice["decision"]!="ready":
            raise ValueError(choice["reason"])
        confirm_future_agreement(conn,career_id=career_id,offer_id=offer_id,
                                 agreement_date=agreement_date)
        result="Transfer signed; player registers in your career at the deadline."
    elif action=="withdraw":
        from world_careers import withdraw_offer
        withdraw_offer(conn,career_id=career_id,offer_id=offer_id)
        result="Your transfer offer was withdrawn."
    else:
        raise ValueError("Unsupported buying action")
    if action=="accept_counter":
        try:
            quote=_agent_opening_quote(conn,career_id=career_id,
                offer_id=offer_id,window_id=snap["window_id"],now=now)
            result+=f" Agent requests £{quote:,}/week."
        except ValueError:
            pass
    _message(conn,career_id=career_id,window_id=snap["window_id"],
        key=f"manager-buy-action:{offer_id}:{action}:"+
            str(conn.execute("""SELECT COALESCE(MAX(event_id),0) FROM world_career_offer_events
                 WHERE offer_id=?""",(offer_id,)).fetchone()[0]),
        headline="Outgoing transfer update",detail=result,offer_id=offer_id,when=now)
    conn.commit()
    return result


def manager_targets(conn,*,career_id,query,limit=60):
    """Read-only rated player lookup, excluding the human club's own squad."""
    if not isinstance(query,str):raise ValueError("Invalid player search")
    q=query.strip()[:70]
    if len(q)<2:return []
    row=conn.execute("""SELECT dataset_id,manager_club_id FROM world_career_saves
        WHERE career_id=? AND state='sandbox'""",(career_id,)).fetchone()
    if row is None:raise ValueError("Unknown development career")
    escaped=q.lower().replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
    results=conn.execute("""SELECT p.player_id,p.full_name,c.name club_name,
        x.overall FROM world_career_registrations r
        JOIN world_players p ON p.player_id=r.player_id
        JOIN world_clubs c ON c.club_id=r.club_id
        JOIN world_dataset_ratings x ON x.dataset_id=? AND x.player_id=r.player_id
        WHERE r.career_id=? AND r.club_id<>?
          AND LOWER(p.full_name) LIKE ? ESCAPE '\\'
          AND x.overall IS NOT NULL
        ORDER BY x.overall DESC,p.full_name,p.player_id LIMIT ?""",
        (row[0],career_id,row[1],"%"+escaped+"%",limit)).fetchall()
    return [dict(r) for r in results]
