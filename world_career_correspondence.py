"""Readable, source-backed manager correspondence for the Career Desk.

Every letter is created only from a committed world_career_market_inbox row.
No virtual acceptance, confirmation, deadline or synthetic transfer is added.
"""
import re

STEPS=("Bid", "Offer response", "Contract offer",
       "Contract accepted", "Finalise deal", "Transfer confirmed")

def _clean(value):
    return re.sub(r"\s*\[WH27:[^\]]+\]\s*$","",str(value or "")).strip()

def _money(value):
    if value is None:
        return ""
    n=int(value)
    if abs(n)>=1000000:
        return f"£{n/1000000:,.2f}m"
    if abs(n)>=1000:
        return "£"+f"{n/1000:,.2f}".rstrip("0").rstrip(".")+"k"
    return f"£{n:,}"

def correspondence(messages,manager_club_id,*,conn=None,career_id=None):
    result=[]
    for row in messages:
        m=dict(row)
        key=str(m.get("message_key") or "")
        if not m.get("offer_id") or not m.get("player_id"):
            continue
        if manager_club_id not in (m.get("buying_club_id"),m.get("selling_club_id")):
            continue
        buying=manager_club_id==m.get("buying_club_id")
        player=_clean(m.get("player_name")) or "the player"
        other=_clean(m.get("seller_name") if buying else m.get("buyer_name")) or "the other club"
        fee=_money(m.get("offered_fee"))
        detail=_clean(m.get("detail"))
        headline=_clean(m.get("headline")).lower()
        stage=None
        sender=other
        subject=""
        body=""
        if key.startswith("manager-bid:") and buying:
            stage=0;sender="Football operations"
            subject=f"Bid submitted for {player}"
            body=f"Our transfer proposal for {player} has been sent to {other}. We will report back once they have made a decision."
        elif key.startswith(("manager-buy-review:","seller-counter-response:")) and buying:
            stage=1
            if "want" in headline or "counter" in headline:
                subject=f"{other} counter our bid for {player}"
                ask=_money(m.get("demanded_fee"))
                body=(f"{other} want {ask} for {player}. " if ask else
                      f"{other} have made a counteroffer for {player}. ")
                body+="Review the fee and either accept, negotiate, or withdraw."
            elif "declined" in headline or "rejected" in headline:
                subject=f"{other} reject our bid for {player}"
                body=f"{other} have turned down our proposed transfer fee. You can consider a revised approach if the window remains open."
            else:
                subject=f"{other} accept our bid for {player}"
                body=f"{other} have agreed the proposed transfer fee. The deal is not complete: personal terms must now be negotiated with the player."
        elif key.startswith("agent-opening-wage:") and buying:
            stage=2;sender=f"{player}'s agent"
            subject=f"Contract demands for {player}"
            body=f"{player}'s representative has outlined the terms needed to progress the move. Review wages, contract length and squad role in Transfers before making your offer."
        elif key.startswith("manager-buy-action:") and buying:
            if ":terms:" in key:
                stage=2;sender="Football operations"
                subject=f"Contract offer sent to {player}"
                body=f"Your proposed contract has been submitted to {player}'s representative. Agent approval and the player's personal decision are separate steps."
            elif ":sign:" in key:
                stage=5;sender="Football operations"
                subject=f"Transfer confirmed: {player}"
                body=f"We have signed the agreement for {player}. The transfer is recorded and will register in the squad at the pre-season deadline."
            elif ":delay_signing:" in key:
                stage=4;sender="Football operations"
                subject=f"Signing delayed: {player}"
                body=f"The final signing decision has been postponed once. The overall 30-minute transfer window is unchanged."
            elif ":withdraw:" in key:
                stage=4;sender="Football operations"
                subject=f"Transfer cancelled: {player}"
                body=f"We have withdrawn from the transfer of {player}; no signing will be registered."
        elif key.startswith("player-review-started:purchase:") and buying:
            stage=3;sender=f"{player}'s representative"
            subject=f"{player} reviewing contract"
            body=f"The proposed personal terms have been presented to {player}. We must await the player's decision before signing any paperwork."
        elif key.startswith("player-review-outcome:purchase:") and buying:
            stage=3;sender=f"{player}'s representative"
            if "accept" in headline:
                subject=f"{player} accepts our contract"
                body=f"{player} has decided to join on the agreed terms. Final manager sign-off is still required before this transfer becomes confirmed."
            else:
                subject=f"{player} declines our contract"
                body=f"{player} has declined the move. The player cannot be signed on these terms."
        elif key.startswith("offer:") and not buying:
            stage=0
            subject=f"{other} submit bid for {player}"
            body=f"{other} have approached us about {player} with a proposed transfer fee of {fee}. You can accept, reject, or counter their offer."
        elif key.startswith("response:") and not buying:
            stage=1
            subject=f"{other} respond to our counter for {player}"
            body=f"{other} have replied to the terms proposed for {player}. Review the buyer's decision before taking further action."
        elif key.startswith("agent:") and not buying:
            stage=3;sender=f"{player}'s agent"
            subject=f"Personal terms update: {player}"
            body=f"Contract negotiations involving {player} have progressed. You can review the confirmed status in the Transfer Centre."
        elif key.startswith("player-review-outcome:sale:") and not buying:
            stage=3;sender=f"{player}'s agent"
            accepted="reject" not in headline
            subject=(f"{player} accepts move to {other}" if accepted
                     else f"{player} declines move to {other}")
            body=(f"{player} has agreed the move to {other}. Review the final paperwork in your Inbox."
                  if accepted else f"{player} has declined the proposed move to {other}. This deal cannot be finalised.")
        elif key.startswith("manager:finalise:") and not buying:
            stage=5;sender="Football operations"
            subject=f"Transfer confirmed: {player} to {other}"
            body=f"The agreement with {other} has been signed. {player}'s departure will register at the pre-season deadline."
        elif key.startswith("manager:cancel:") and not buying:
            stage=4;sender="Football operations"
            subject=f"Talks ended for {player}"
            body=f"The proposed move involving {player} has been cancelled."
        if stage is None:
            continue
        # The underlying event text is shown as provenance, but only when it
        # adds specific facts rather than opaque simulation terminology.
        extra=""
        if detail and len(detail)<230 and not re.search(
            r"autonomous|snapshot|decision_version|model_|simulat|offer_id|source_key",detail,re.I):
            extra=detail
        result.append(dict(message_id=m["message_id"],offer_id=m["offer_id"],
            player_id=m["player_id"],player=player,sender=sender,
            subject=subject,body=body,detail=extra,fee=fee,stage=stage,
            stage_label=STEPS[stage],created_at=m["created_at"],
            is_read=bool(m["is_read"]),side="buy" if buying else "sale"))
    if conn is not None and career_id is not None:
        result.extend(_contract_and_free_agent_letters(conn,career_id,messages))
    return sorted(result,key=lambda x:(str(x["created_at"]),str(x["message_id"])),
                  reverse=True)


def _contract_and_free_agent_letters(conn,career_id,messages):
    """Add genuine renewal and free-agent events without a second mail ledger."""
    out=[]
    rows=conn.execute("""SELECT p.player_id,p.full_name FROM world_players p
        JOIN world_career_contract_renewals a ON a.player_id=p.player_id
        WHERE a.career_id=?""",(career_id,)).fetchall() if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='world_career_contract_renewals'"
    ).fetchone() else []
    player_names={int(r[0]):r[1] for r in rows}
    free_rows=conn.execute("""SELECT f.signing_id,f.player_id,p.full_name
        FROM world_fc27_free_agent_offers f
        JOIN world_players p ON p.player_id=f.player_id
        WHERE f.career_id=?""",(career_id,)).fetchall() if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='world_fc27_free_agent_offers'"
    ).fetchone() else []
    free_by_signing={int(r[0]):(int(r[1]),r[2]) for r in free_rows}
    for row in messages:
        m=dict(row)
        key=str(m.get("message_key") or "")
        if key.startswith("fc27-renewal:"):
            parts=key.split(":")
            if len(parts)<4 or not parts[2].isdigit():continue
            pid=int(parts[2])
            if pid not in player_names:continue
            name=player_names[pid]
            event=parts[3]
            detail=_clean(m.get("detail"))
            if event=="request":
                subject=f"{name} requests a new contract"
                body=f"{name}'s representative would like to discuss improved terms. Open Squad to review the request and make an offer."
                stage=2;sender=f"{name}'s agent"
            elif event=="confirmed":
                subject=f"New contract signed: {name}"
                body=detail or f"{name} has signed a new contract for the club."
                stage=5;sender="Football operations"
            elif event.startswith("offer-"):
                subject=(f"{name}'s agent ends negotiations" if "ended" in detail else
                         f"Contract offer response: {name}")
                body=detail or "The representative has replied to your contract proposal."
                stage=3;sender=f"{name}'s agent"
            else:
                subject=f"Contract discussions ended: {name}"
                body=detail or f"Negotiations with {name} have been closed."
                stage=4;sender="Football operations"
            out.append(dict(message_id=m["message_id"],offer_id=None,
                player_id=pid,player=name,sender=sender,subject=subject,body=body,
                detail="",fee="",stage=stage,stage_label=STEPS[stage],
                created_at=m["created_at"],is_read=bool(m["is_read"]),
                side="renewal"))
        elif key.startswith("player-review-outcome:free_agent:"):
            sid=key.rsplit(":",1)[-1]
            if not sid.isdigit() or int(sid) not in free_by_signing:continue
            pid,name=free_by_signing[int(sid)]
            accepted="accept" in str(m.get("headline") or "").lower()
            subject=f"{name} accepts our contract" if accepted else f"{name} declines our contract"
            body=(f"{name} has accepted our terms. Manager approval is now required to complete this free-agent signing."
                  if accepted else f"{name} has rejected the move. This free-agent deal cannot proceed.")
            out.append(dict(message_id=m["message_id"],offer_id=None,
                player_id=pid,player=name,sender=f"{name}'s representative",
                subject=subject,body=body,detail="",fee="",stage=3,
                stage_label=STEPS[3],created_at=m["created_at"],
                is_read=bool(m["is_read"]),side="free"))
    if free_by_signing and conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='world_fc27_free_agent_events'"
    ).fetchone():
        entries=conn.execute("""SELECT e.event_id,e.signing_id,e.event,
            e.detail,e.recorded_at,f.proposed_weekly_wage_gbp,f.contract_years
            FROM world_fc27_free_agent_events e
            JOIN world_fc27_free_agent_offers f ON f.signing_id=e.signing_id
            WHERE f.career_id=? ORDER BY e.event_id DESC LIMIT 50""",
            (career_id,)).fetchall()
        for eid,sid,event,detail,stamp,wage,years in entries:
            if int(sid) not in free_by_signing:continue
            pid,name=free_by_signing[int(sid)]
            if event=="agent_response":
                agreed="agreed provisional" in str(detail).lower()
                subject=(f"{name}'s agent accepts proposed terms" if agreed
                         else f"{name}'s agent requests improved terms")
                body=(f"The representative has provisionally agreed terms with {name} at {_money(wage)}/week. The player must now make a separate decision."
                      if agreed else f"The representative has requested revised contract terms for {name}. The move has not been agreed.")
                stage=2;sender=f"{name}'s agent"
            elif event=="manager_confirmed":
                subject=f"Free-agent signing confirmed: {name}"
                body=f"Your club has signed {name} to a {years}-year contract at {_money(wage)}/week. Registration will occur at the transfer deadline."
                stage=5;sender="Football operations"
            else:
                continue
            out.append(dict(message_id=f"fa-{eid}",offer_id=None,
                player_id=pid,player=name,sender=sender,subject=subject,body=body,
                detail="",fee=_money(wage),stage=stage,
                stage_label=STEPS[stage],created_at=stamp,
                is_read=True,side="free"))
    return out

