"""Auditable pre-season expectation uplift from funds and board ambition.

All budgets in current PES career economy are modelled tier defaults, not
verified club accounts. A distinct board improvement mandate has to be
explicitly chosen and locked; merely holding cash is not proof of ambition.
The season-review penalty applies only if actual results are disappointing
AND resources earmarked for improvements were substantially unused.
"""
from statistics import median
from world_careers import budget_remaining

VERSION="board-resource-expectations-v1"
AMBITIONS=("survival","consolidation","promotion","continental")
MANDATES=("none","optional","expected","required")

SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_resource_expectations (
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 season_key TEXT NOT NULL,
 strength_rank INTEGER NOT NULL,
 expected_rank INTEGER NOT NULL,
 financial_shift INTEGER NOT NULL,
 ambition_shift INTEGER NOT NULL,
 ambition TEXT NOT NULL,
 investment_mandate TEXT NOT NULL,
 investment_pool INTEGER NOT NULL,
 opening_transfer_budget INTEGER NOT NULL,
 opening_committed_fees INTEGER NOT NULL,
 opening_unreserved_funds INTEGER NOT NULL,
 division_median_transfer_budget INTEGER NOT NULL,
 commitment_note TEXT NOT NULL,
 model_version TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,club_id,season_key),
 FOREIGN KEY(career_id,club_id,season_key) REFERENCES
 world_career_season_objectives(career_id,club_id,season_key)
);
CREATE TABLE IF NOT EXISTS world_career_resource_reviews (
 career_id TEXT NOT NULL,
 club_id INTEGER NOT NULL,
 season_key TEXT NOT NULL,
 reported_investment INTEGER NOT NULL,
 unused_mandated_funds INTEGER NOT NULL,
 confidence_delta INTEGER NOT NULL,
 reason TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,club_id,season_key),
 FOREIGN KEY(career_id,club_id,season_key) REFERENCES
 world_career_resource_expectations(career_id,club_id,season_key)
);
"""


def initialize_resource_expectations(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def resource_capacity(conn, *, career_id, club_id, baseline):
    """Return verified-within-career budget fields, never invented real accounts."""
    row=conn.execute("""SELECT transfer_budget,committed_fees FROM world_career_club_ledger
        WHERE career_id=? AND club_id=?""",(career_id,club_id)).fetchone()
    if not row:
        raise ValueError("No career transfer ledger for managed club")
    peers=conn.execute("""SELECT l.transfer_budget FROM world_career_club_ledger l
        JOIN world_dataset_entries e ON e.club_id=l.club_id
        JOIN world_career_saves c ON c.career_id=l.career_id
          AND c.dataset_id=e.dataset_id
        WHERE l.career_id=? AND e.competition_id=?""",
        (career_id,baseline["competition_id"])).fetchall()
    if len(peers)!=baseline["league_size"]:
        raise ValueError("Missing financial ledger for one or more clubs in this division")
    return {"transfer_budget":row[0],"committed_fees":row[1],
        "unreserved":max(0,budget_remaining(conn,career_id,club_id)),
        "median_peer_budget":int(median([p[0] for p in peers])),
        "note":"These budgets come from the game economy; they are not verified real-world club finances."}


def expectation_with_resources(*,squad_rank,league_size,
        ambition,investment_mandate,investment_pool,
        opening_unreserved_funds,division_median_transfer_budget,
        division_tier=1):
    for name,v in (("squad_rank",squad_rank),("league_size",league_size),
                   ("investment_pool",investment_pool),
                   ("opening_unreserved_funds",opening_unreserved_funds),
                   ("division_median_transfer_budget",division_median_transfer_budget)):
        if type(v) is not int or v<0:
            raise ValueError(name+" must be a nonnegative integer")
    if not 10<=league_size<=30 or not 1<=squad_rank<=league_size:
        raise ValueError("Invalid squad rank or division size")
    if ambition not in AMBITIONS or investment_mandate not in MANDATES:
        raise ValueError("Choose an explicit board ambition and investment mandate")
    if investment_pool>opening_unreserved_funds:
        raise ValueError("A board cannot earmark more than its unreserved transfer funds")
    if investment_mandate=="none" and investment_pool!=0:
        raise ValueError("A nonexistent investment mandate cannot have allocated funds")
    if division_tier==1 and ambition=="promotion":
        raise ValueError("Promotion is not a credible Premier League objective")
    if division_tier!=1 and ambition=="continental":
        raise ValueError("Continental qualification is not a league target outside the top flight")
    ambition_shift=2 if ambition in ("promotion","continental") else 0
    # Only a genuine mandate stretches squad-strength expectations.
    # Moderate funding and a credible opportunity to invest: up to 1 rank.
    # Major committed support relative to peers: up to 3 ranks.
    fraction=(investment_pool/opening_unreserved_funds
              if opening_unreserved_funds else 0)
    peer_ratio=(investment_pool/division_median_transfer_budget
                if division_median_transfer_budget else 0)
    investment_shift=0
    if investment_mandate in ("expected","required"):
        if fraction>=0.25 and peer_ratio>=0.25:
            investment_shift=1
        if fraction>=0.60 and peer_ratio>=1.0:
            investment_shift=2
        if investment_mandate=="required" and fraction>=0.75 and peer_ratio>=1.50:
            investment_shift=3
    total_shift=min(4,ambition_shift+investment_shift)
    return {"strength_rank":squad_rank,"expected_rank":max(1,squad_rank-total_shift),
            "ambition_shift":ambition_shift,"financial_shift":investment_shift,
            "total_shift":total_shift,"investment_fraction":round(fraction,4),
            "peer_funding_ratio":round(peer_ratio,4),
            "version":VERSION,
            "explanation":(
                f"Squad-strength rank {squad_rank}; explicit {ambition} ambition "
                f"improves expectation by {ambition_shift} places; "
                f"{investment_mandate} investment mandate of £{investment_pool:,} "
                f"improves it by {investment_shift} more. "
                "Spending does not itself count as performance.")
            }


def review_underinvestment(*,actual_rank,expected_rank,
                           committed_spend,mandated_funds,mandate):
    """Small extra accountability charge only if required support was ignored.

    No extra penalty for outperforming while spending little; no incentive to
    waste money merely to avoid penalty. Source is the game's committed-fee
    ledger, NOT unsigned transfer offers.
    """
    if mandate not in MANDATES:
        raise ValueError("Unknown improvement mandate")
    if any(type(v) is not int or v<0 for v in
           (actual_rank,expected_rank,committed_spend,mandated_funds)):
        raise ValueError("Invalid recorded financial review values")
    unused=max(0,mandated_funds-committed_spend)
    shortfall=(actual_rank>expected_rank+1)
    if mandate=="required" and mandated_funds>0 and (
            unused*100>=mandated_funds*75) and shortfall:
        return {"delta":-3,"unused":unused,
            "reason":"Board-mandated improvement funds largely unused AND final performance below objectives."}
    return {"delta":0,"unused":unused,
        "reason":"No additional underinvestment penalty: either objectives were met, spending was committed, or investment was not compulsory."}
