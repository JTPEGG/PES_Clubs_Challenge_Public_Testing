"""FC27-only board allocation of signed sales to the transfer budget.

A sale is only bankable after a binding agreement; the actual PES registration
is still deferred to the immutable pre-season deadline. Allocations are scoped
to one career, one offer and one seller, and are never inferred from real-world
club accounts. SQLite transactions make the credit and signing atomic.
"""
from __future__ import annotations

FC27_DATASET = "fc27-warehouse-659-mens-2026-27"

SALE_BUDGET_SCHEMA = """
CREATE TABLE IF NOT EXISTS world_career_sale_budget_credits (
 offer_id INTEGER PRIMARY KEY,
 career_id TEXT NOT NULL,
 seller_club_id INTEGER NOT NULL,
 gross_fee_gbp INTEGER NOT NULL CHECK(gross_fee_gbp>=0),
 allocated_gbp INTEGER NOT NULL CHECK(allocated_gbp>=0),
 withheld_gbp INTEGER NOT NULL CHECK(withheld_gbp>=0),
 allocation_basis_points INTEGER NOT NULL CHECK(allocation_basis_points BETWEEN 0 AND 10000),
 financial_pressure_index INTEGER NOT NULL CHECK(financial_pressure_index BETWEEN 0 AND 100),
 financial_pressure_band TEXT NOT NULL,
 policy_version TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(allocated_gbp + withheld_gbp = gross_fee_gbp),
 UNIQUE(career_id,offer_id)
);
CREATE INDEX IF NOT EXISTS world_sale_budget_career_club
 ON world_career_sale_budget_credits(career_id,seller_club_id);
"""

POLICY_VERSION = "fc27-game-board-sale-allocation-v1"

def allocation_basis_points(*,pressure_index,financial_pressure_band,
                             operating_approach):
    """Continuous model from existing source-labelled club financial pressure.

    At pressure 0 a well-funded board can reinvest 100%; severe pressure
    approaches 50%, with a narrower ceiling where labelled financial
    distress or overcommitment warrants cash retention by the club.
    This is a *game* policy, not a factual claim about a board.
    """
    if type(pressure_index) is not int or not 0 <= pressure_index <= 100:
        raise ValueError("FC27 sale allocation requires a valid 0–100 club financial-pressure index")
    if not isinstance(financial_pressure_band,str) or not financial_pressure_band:
        raise ValueError("FC27 sale allocation requires an identified financial-pressure band")
    share = 1.0 - 0.50 * (pressure_index / 100.0) ** 1.35
    if financial_pressure_band == "distress":
        share = min(share,0.55)
    elif financial_pressure_band == "over_committed":
        share = min(share,0.75)
    elif financial_pressure_band == "tight":
        share = min(share,0.90)
    if operating_approach == "high_ambition" and financial_pressure_band != "distress":
        share += 0.025
    return max(0,min(10000,round(share*10000)))


def credit_signed_sale(conn,*,career_id,offer_id,seller_club_id,gross_fee):
    """Credit *only* a fully signed FC27 sale, exactly once in its signing TX.

    The caller is the deal-signature transaction. Never call this on a merely
    accepted fee, unsigned personal terms or withdrawn/expired bid.
    """
    if type(gross_fee) is not int or gross_fee < 0:
        raise ValueError("Transfer fee must be a nonnegative GBP integer")
    career=conn.execute("""SELECT dataset_id FROM world_career_saves
        WHERE career_id=?""",(career_id,)).fetchone()
    if not career:raise ValueError("Unknown career for sale allocation")
    if career[0] != FC27_DATASET:
        return None
    row=conn.execute("""SELECT financial_pressure_index,
            financial_pressure_band,operating_approach
        FROM world_fc27_club_ai_context
        WHERE dataset_id=? AND club_id=?""",
        (career[0],seller_club_id)).fetchone()
    if not row:
        raise ValueError("Missing FC27 source-labelled financial profile for selling club")
    bps=allocation_basis_points(pressure_index=row[0],
        financial_pressure_band=row[1],operating_approach=row[2])
    allocated=gross_fee*bps//10000
    withheld=gross_fee-allocated
    # This DDL creates no commit and can safely execute inside BEGIN IMMEDIATE.
    conn.execute("""CREATE TABLE IF NOT EXISTS world_career_sale_budget_credits (
        offer_id INTEGER PRIMARY KEY,career_id TEXT NOT NULL,
        seller_club_id INTEGER NOT NULL,
        gross_fee_gbp INTEGER NOT NULL CHECK(gross_fee_gbp>=0),
        allocated_gbp INTEGER NOT NULL CHECK(allocated_gbp>=0),
        withheld_gbp INTEGER NOT NULL CHECK(withheld_gbp>=0),
        allocation_basis_points INTEGER NOT NULL CHECK(allocation_basis_points BETWEEN 0 AND 10000),
        financial_pressure_index INTEGER NOT NULL CHECK(financial_pressure_index BETWEEN 0 AND 100),
        financial_pressure_band TEXT NOT NULL,policy_version TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK(allocated_gbp + withheld_gbp = gross_fee_gbp),
        UNIQUE(career_id,offer_id)
    )""")
    inserted=conn.execute("""INSERT OR IGNORE INTO world_career_sale_budget_credits
        (offer_id,career_id,seller_club_id,gross_fee_gbp,allocated_gbp,
         withheld_gbp,allocation_basis_points,financial_pressure_index,
         financial_pressure_band,policy_version)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (offer_id,career_id,seller_club_id,gross_fee,allocated,withheld,
         bps,row[0],row[1],POLICY_VERSION))
    if inserted.rowcount:
        credited=conn.execute("""UPDATE world_career_club_ledger
            SET transfer_budget=transfer_budget+?
            WHERE career_id=? AND club_id=?""",
            (allocated,career_id,seller_club_id))
        if credited.rowcount!=1:
            raise ValueError("Selling club's career transfer ledger is missing")
    else:
        existing=conn.execute("""SELECT gross_fee_gbp,allocated_gbp,
            seller_club_id FROM world_career_sale_budget_credits
            WHERE offer_id=? AND career_id=?""",(offer_id,career_id)).fetchone()
        if (not existing or tuple(existing)!=(gross_fee,allocated,seller_club_id)):
            raise ValueError("Inconsistent repeated sale-budget allocation")
    return dict(offer_id=offer_id,gross_fee=gross_fee,allocated=allocated,
        withheld=withheld,basis_points=bps,credited_now=bool(inserted.rowcount),
        policy=POLICY_VERSION)
