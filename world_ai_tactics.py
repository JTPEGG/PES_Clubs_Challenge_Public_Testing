"""FC27 career-only tactical recruitment preferences.

Never claim a real manager uses a formation: absent verified tactics we model a
deterministic preference for the anonymous simulated manager. Tactical plans
stay stable through a transfer window, and existing career rules stay intact.
LM/RM are specialist midfield-wide roles, not synonyms for LW/RW.
"""
from hashlib import sha256

TACTIC_VERSION="fc27-anonymous-tactics-v1"
# Eleven simultaneously occupied roles in a conventional starting shape.
FORMATION_STARTERS={
    "4-3-3":{"GK":1,"CB":2,"LB":1,"RB":1,"DM":1,"CM":2,"LW":1,"RW":1,"ST":1},
    "4-2-3-1":{"GK":1,"CB":2,"LB":1,"RB":1,"DM":2,"AM":1,"LW":1,"RW":1,"ST":1},
    "4-4-2":{"GK":1,"CB":2,"LB":1,"RB":1,"CM":2,"LM":1,"RM":1,"ST":2},
    "4-1-4-1":{"GK":1,"CB":2,"LB":1,"RB":1,"DM":1,"CM":2,"LM":1,"RM":1,"ST":1},
    "3-5-2":{"GK":1,"CB":3,"LB":1,"RB":1,"DM":1,"CM":2,"ST":2},
    "3-4-3":{"GK":1,"CB":3,"CM":2,"LM":1,"RM":1,"LW":1,"RW":1,"ST":1},
    "4-3-1-2":{"GK":1,"CB":2,"LB":1,"RB":1,"DM":1,"CM":2,"AM":1,"ST":2},
}
if any(sum(spec.values())!=11 for spec in FORMATION_STARTERS.values()):
    raise RuntimeError("Invalid formation: expected eleven independent roles")

def preferred_formation(*,club_id,profile=None):
    """Stable game-generated coach plan; not an asserted real-world tactic."""
    if type(club_id) is not int or club_id<=0:
        raise ValueError("Club ID must be positive integer")
    stated=(profile or {}).get("preferred_formation")
    if stated is not None:
        if stated not in FORMATION_STARTERS:
            raise ValueError("Unknown manager formation")
        return stated
    keys=tuple(FORMATION_STARTERS)
    entropy=int.from_bytes(sha256(
        f"{TACTIC_VERSION}|{club_id}".encode("utf8")).digest()[:8],"big")
    return keys[entropy%len(keys)]

def tactical_needs(formation):
    """Required XI roles and non-binding depth aims, with no hard squad quota."""
    if formation not in FORMATION_STARTERS:
        raise ValueError("Unsupported tactical shape")
    starters=dict(FORMATION_STARTERS[formation])
    # One starter needs at least one plausible reserve, but a manager may
    # reasonably cover several positions with one genuinely multi-role player.
    depth={role:max(n,n+1 if role!="GK" else 2)
           for role,n in starters.items()}
    return {"formation":formation,"starting_roles":starters,
            "soft_cover_aims":depth,
            "provenance":"anonymous manager GAME tactic, not historical formation"}
