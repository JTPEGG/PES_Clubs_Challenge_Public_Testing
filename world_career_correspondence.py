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
    return ("£"+(f"{n/1000000:,.2f}m" if abs(n)>=1000000
                else f"{n/1000:,.2f}k".rstrip("0").rstrip(".")
                if abs(n)>=1000 else f"{n:,}"))

def correspondence(messages,manager_club_id):
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
                body=f"{other} have requested revised terms for {player}. Review their asking price and either accept it, negotiate, or withdraw the offer."
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
    return result
