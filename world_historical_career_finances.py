"""Optional historical financial and initial-loan seeding for NEW career saves.

Requires an existing immutable world_dataset whose player and club references
have been explicitly mapped to the men's historical SQLite source. Never
guesses a club crosswalk, and never backfills older career saves. Creates
initial loans as ACTIVE, not fresh negotiable offers, and commits only as part
of world_careers.start_sandbox's enclosing transaction.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

SCHEMA="""
CREATE TABLE IF NOT EXISTS world_dataset_historical_finance_policy(
 dataset_id TEXT PRIMARY KEY REFERENCES world_datasets(dataset_id),
 model_version TEXT NOT NULL,
 provenance TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS world_dataset_initial_loans(
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 borrower_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 parent_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 return_date TEXT NOT NULL,
 borrower_wage_share_pct INTEGER NOT NULL
    CHECK(borrower_wage_share_pct BETWEEN 0 AND 100),
 model_provenance TEXT NOT NULL,
 PRIMARY KEY(dataset_id,player_id),
 CHECK(borrower_club_id<>parent_club_id)
);
CREATE TABLE IF NOT EXISTS world_career_historical_finance_policy(
 career_id TEXT PRIMARY KEY REFERENCES world_career_saves(career_id),
 model_version TEXT NOT NULL,
 provenance TEXT NOT NULL
);
"""


def initialize_historical_finances(conn):
    conn.executescript(SCHEMA)


def seed_existing_loans_and_payroll(conn, *, career_id,dataset_id,
                                    pes_lock_date,next_summer_date):
    """Seed newly created career only; caller holds BEGIN IMMEDIATE.

    If dataset has NOT opted into a historical financial model, do nothing.
    Strictly require all registered players to have an evidenced/estimated
    starting contract; no fake zero wage or duplicated initial loan.
    """
    info=conn.execute("""SELECT model_version,provenance
        FROM world_dataset_historical_finance_policy
        WHERE dataset_id=?""",(dataset_id,)).fetchone()
    if info is None:
        return {"initial_loans":0,"starting_payroll_weekly":0,"opted_in":False}
    lock=date.fromisoformat(pes_lock_date)
    next_summer=date.fromisoformat(next_summer_date)
    reg=dict(conn.execute("""SELECT player_id,club_id FROM
        world_career_registrations WHERE career_id=?""",(career_id,)).fetchall())
    contract={}
    for pid,parent,wage,expires in conn.execute("""SELECT player_id,
        parent_club_id,weekly_wage_gbp,expires_on FROM
        world_career_contract_snapshots WHERE career_id=?""",(career_id,)):
        if wage is None or type(wage) is not int or not 0<=wage<=1_000_000:
            raise ValueError("A historical career requires known, bounded initial game wages")
        contract[pid]=(parent,wage,expires)
    if set(reg)!=set(contract):
        raise ValueError("Historical player registration / contract count mismatch")
    loans={}
    for pid,borrower,parent,ret,pct,source in conn.execute("""SELECT
        player_id,borrower_club_id,parent_club_id,return_date,
        borrower_wage_share_pct,model_provenance
        FROM world_dataset_initial_loans WHERE dataset_id=?""",(dataset_id,)):
        if pid not in reg or reg[pid]!=borrower:
            raise ValueError("Historical source loan borrower does not hold initial registration")
        if pid not in contract or contract[pid][0]!=parent:
            raise ValueError("Historical source loan parent differs from contract owner")
        if not lock<date.fromisoformat(ret)<=next_summer:
            raise ValueError("Source loan return not within starting PES season")
        if contract[pid][2] and contract[pid][2]<ret:
            raise ValueError("Loan outlasts the parent contract; review expiry first")
        if pid in loans:
            raise ValueError("Duplicate initial source loan")
        loans[pid]=(borrower,parent,ret,pct,source)
    payroll=Counter()
    for pid,club in reg.items():
        parent,wage,_=contract[pid]
        if pid in loans:
            borrower,parent,ret,pct,source=loans[pid]
            borrowed=round(wage*pct/100)
            payroll[borrower]+=borrowed
            payroll[parent]+=wage-borrowed
        else:
            if club!=parent:
                raise ValueError("Non-loaned source player registration mismatches contract owner")
            payroll[parent]+=wage
    ledgers=dict(conn.execute("""SELECT club_id,weekly_wage_budget
        FROM world_career_club_ledger WHERE career_id=?""",(career_id,)).fetchall())
    for club,cost in payroll.items():
        if club not in ledgers:
            raise ValueError("Source-loan parent is outside career financial world")
        if cost>ledgers[club]:
            raise ValueError(f"Starting payroll exceeds budget for club id {club}: "
                             f"£{cost:,} > £{ledgers[club]:,} / week")
    for club,cost in payroll.items():
        conn.execute("""UPDATE world_career_club_ledger SET committed_wages=?
            WHERE career_id=? AND club_id=?""",(cost,career_id,club))
    for pid,(borrower,parent,ret,pct,source) in loans.items():
        gross=contract[pid][1]
        weekly=round(gross*pct/100)
        conn.execute("""INSERT INTO world_career_loan_agreements
           (career_id,player_id,parent_club_id,borrower_club_id,start_date,
            return_date,loan_fee_gbp,borrower_wage_share_pct,
            wage_commitment_gbp,status,source_kind)
           VALUES (?,?,?,?,?,?,0,?,?,'active',?)""",
           (career_id,pid,parent,borrower,lock.isoformat(),ret,pct,weekly,
            "historical_initial_source_loan:"+source))
    conn.execute("""INSERT INTO world_career_historical_finance_policy
        (career_id,model_version,provenance) VALUES (?,?,?)""",
        (career_id,info[0],info[1]))
    return {
        "initial_loans":len(loans),
        "starting_payroll_weekly":sum(payroll.values()),
        "opted_in":True,
        "model_version":info[0],
    }


def is_historical_finance_career(conn,career_id):
    if not conn.execute("""SELECT 1 FROM sqlite_master WHERE
        type='table' AND name='world_career_historical_finance_policy'""").fetchone():
        return False
    return conn.execute("""SELECT 1 FROM world_career_historical_finance_policy
        WHERE career_id=?""",(career_id,)).fetchone() is not None
