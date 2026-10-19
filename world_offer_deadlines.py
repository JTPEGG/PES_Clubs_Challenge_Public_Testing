"""Finite AI buyer patience after a human seller's agent terms are agreed.

This rule applies ONLY to unconfirmed incoming offers in a live 30-minute
preseason transfer window. A buyer gives the selling manager four real minutes
to sign; a single request MAY win a further two minutes, never beyond the
overall window. Deadlines survive refreshes and are checked on the server.
"""
import hashlib
from datetime import datetime, timedelta
from world_preseason_window import (
    window_snapshot, assert_window_allows_negotiation, _utc, _iso,
)

CONFIRM_SECONDS=4*60
EXTENSION_SECONDS=2*60

SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_incoming_confirmations(
 offer_id INTEGER PRIMARY KEY REFERENCES world_career_offers(offer_id),
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 offered_at TEXT NOT NULL,
 initial_deadline_at TEXT NOT NULL,
 deadline_at TEXT NOT NULL,
 extension_requested INTEGER NOT NULL DEFAULT 0 CHECK(extension_requested IN (0,1)),
 extension_granted INTEGER NOT NULL DEFAULT 0 CHECK(extension_granted IN (0,1)),
 expired_at TEXT,
 extension_reason TEXT,
 CHECK(extension_granted<=extension_requested)
);
CREATE INDEX IF NOT EXISTS world_career_incoming_confirmations_window
 ON world_career_incoming_confirmations(window_id,deadline_at);
"""

def initialise_confirmation_deadlines(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def confirmation_state(conn, *, career_id, offer_id, now=None):
    cursor=conn.execute("""SELECT d.* FROM world_career_incoming_confirmations d
        WHERE d.career_id=? AND d.offer_id=?""",(career_id,offer_id))
    row=cursor.fetchone()
    if row is None:return None
    info=dict(zip((col[0] for col in cursor.description),row))
    end=datetime.fromisoformat(info["deadline_at"])
    info["remaining_seconds"]=max(0,int((end-_utc(now)).total_seconds()+0.999999))
    return info


def reconcile_confirmations(conn, *, career_id, now=None):
    """Open/expire clocks once. No player is moved and no deal auto-signed."""
    t=_utc(now)
    snap=window_snapshot(conn,career_id=career_id,now=t)
    if snap["state"]!="open":
        return {"opened":0,"expired":0}
    # For previously existing careers lacking this new feature, start the
    # clock on first observation instead of retrospectively timing them out.
    end=min(t+timedelta(seconds=CONFIRM_SECONDS),
            datetime.fromisoformat(snap["deadline_at"]))
    ids=conn.execute("""SELECT o.offer_id FROM world_career_preseason_window_offers wo
        JOIN world_career_offers o ON o.offer_id=wo.offer_id
        JOIN world_career_saves c ON c.career_id=o.career_id
        JOIN world_career_incoming_approaches a ON a.offer_id=o.offer_id
        JOIN world_career_agent_terms t ON t.offer_id=o.offer_id
        WHERE wo.window_id=? AND o.career_id=? AND o.status='accepted_pending_contract'
        AND o.selling_club_id=c.manager_club_id
        AND o.buying_club_id<>c.manager_club_id
        AND a.status='terms_accepted' AND t.status='accepted'
        AND NOT EXISTS(SELECT 1 FROM world_career_incoming_confirmations d
                       WHERE d.offer_id=o.offer_id)""",
        (snap["window_id"],career_id)).fetchall()
    for (offer_id,) in ids:
        conn.execute("""INSERT OR IGNORE INTO world_career_incoming_confirmations
            (offer_id,career_id,window_id,offered_at,initial_deadline_at,deadline_at)
            VALUES(?,?,?,?,?,?)""",
            (offer_id,career_id,snap["window_id"],_iso(t),_iso(end),_iso(end)))
    # Expiry depends on the authoritative server clock, never on a browser
    # countdown. An offer that is already signed or cancelled is untouched.
    expired=conn.execute("""SELECT d.offer_id FROM world_career_incoming_confirmations d
        JOIN world_career_offers o ON o.offer_id=d.offer_id
        WHERE d.window_id=? AND d.career_id=?
          AND d.expired_at IS NULL AND d.deadline_at<=?
          AND o.status='accepted_pending_contract'""",
        (snap["window_id"],career_id,_iso(t))).fetchall()
    for (offer_id,) in expired:
        conn.execute("""UPDATE world_career_offers SET status='withdrawn'
            WHERE offer_id=? AND status='accepted_pending_contract'""",(offer_id,))
        conn.execute("""UPDATE world_career_incoming_confirmations
            SET expired_at=? WHERE offer_id=? AND expired_at IS NULL""",
            (_iso(t),offer_id))
        conn.execute("""INSERT INTO world_career_offer_events
            (offer_id,event_type,detail) VALUES(?,?,?)""",
            (offer_id,"ai_buyer_confirmation_expired",
             "The buying club withdrew because the manager did not sign by the agreed decision deadline."))
        from world_live_market import _message
        _message(conn,career_id=career_id,window_id=snap["window_id"],
            key=f"buyer-patience-expired:{offer_id}",
            headline="Buying club has withdrawn its offer",
            detail="The buyer's final confirmation deadline expired. No transfer was signed.",
            offer_id=offer_id,when=t)
    if ids or expired:conn.commit()
    return {"opened":len(ids),"expired":len(expired)}


def _club_grants_extension(*, career_id, offer_id, buyer_id, rivals, seconds_left):
    """Deterministic one-shot simulated club choice; cannot reroll by refresh."""
    likelihood=max(15,65-(25 if rivals else 0)-(10 if seconds_left<60 else 0))
    digest=hashlib.sha256(
        f"confirmation-extension-v1:{career_id}:{offer_id}:{buyer_id}".encode()
    ).digest()
    return int.from_bytes(digest[:4],"big")%100 < likelihood


def request_confirmation_extension(conn, *, career_id, offer_id, now=None):
    """Request a one-time 2-minute hold. Buyer may refuse; no fee changes."""
    t=_utc(now)
    snap=assert_window_allows_negotiation(conn,career_id=career_id,now=t)
    if snap is None:raise ValueError("Start the transfer window first")
    reconcile_confirmations(conn,career_id=career_id,now=t)
    record=confirmation_state(conn,career_id=career_id,offer_id=offer_id,now=t)
    buyer=conn.execute("""SELECT o.buying_club_id,o.player_id,o.status,c.manager_club_id,
            o.selling_club_id FROM world_career_offers o
            JOIN world_career_saves c ON c.career_id=o.career_id
            WHERE o.career_id=? AND o.offer_id=?""",(career_id,offer_id)).fetchone()
    if not record or not buyer or buyer[2]!="accepted_pending_contract" or buyer[4]!=buyer[3]:
        raise ValueError("There is no live incoming signing to delay")
    if record["window_id"]!=snap["window_id"]:
        raise ValueError("This offer belongs to another transfer window")
    if record["extension_requested"]:
        raise ValueError("You have already requested more time for this transfer")
    if record["remaining_seconds"]<=0:
        raise ValueError("The buying club's confirmation deadline has passed")
    new_end=min(
        datetime.fromisoformat(record["deadline_at"])+
        timedelta(seconds=EXTENSION_SECONDS),
        datetime.fromisoformat(snap["deadline_at"]))
    rivals=conn.execute("""SELECT COUNT(DISTINCT buying_club_id)
        FROM world_career_offers WHERE career_id=? AND player_id=? AND offer_id<>?
        AND status IN ('proposed','countered','accepted_pending_contract')""",
        (career_id,buyer[1],offer_id)).fetchone()[0]
    room_available=new_end>datetime.fromisoformat(record["deadline_at"])
    accepted=(room_available and _club_grants_extension(
        career_id=career_id,offer_id=offer_id,buyer_id=buyer[0],
        rivals=rivals,seconds_left=record["remaining_seconds"]))
    reason=("Buyer agreed to wait up to two more minutes." if accepted else
            "No extra time is available before the overall transfer deadline."
            if not room_available else
            "Buyer refused to extend its original confirmation deadline.")
    conn.execute("""UPDATE world_career_incoming_confirmations
        SET extension_requested=1,extension_granted=?,extension_reason=?,
            deadline_at=?
        WHERE offer_id=? AND extension_requested=0""",
        (int(accepted),reason,_iso(new_end) if accepted else record["deadline_at"],
         offer_id))
    conn.execute("""INSERT INTO world_career_offer_events
        (offer_id,event_type,detail) VALUES(?,?,?)""",
        (offer_id,"ai_buyer_extension_granted" if accepted else
         "ai_buyer_extension_refused",reason))
    from world_live_market import _message
    _message(conn,career_id=career_id,window_id=snap["window_id"],
        key=f"buyer-patience-extension:{offer_id}",
        headline=("Buyer grants more time" if accepted
                  else "Buyer refuses more time"),
        detail=(reason+" The transfer is still unsigned."),
        offer_id=offer_id,when=t)
    conn.commit()
    return {"accepted":accepted,"reason":reason,
            "deadline_at":_iso(new_end) if accepted else record["deadline_at"]}


def require_live_confirmation(conn, *, career_id, offer_id, now=None):
    """Called on sign, never blindly trusts the last rendered countdown."""
    snap=window_snapshot(conn,career_id=career_id,now=now)
    if snap["state"]=="not_started":
        return  # Preserve legacy non-live career behaviour.
    if snap["state"]!="open":
        raise ValueError("The 30-minute transfer window has closed")
    reconcile_confirmations(conn,career_id=career_id,now=now)
    record=confirmation_state(conn,career_id=career_id,offer_id=offer_id,now=now)
    if not record:
        raise ValueError("The buyer has not completed agent terms for confirmation")
    if record["remaining_seconds"]<=0 or record["expired_at"] is not None:
        raise ValueError("The buying club's signing deadline has expired")
    return record
