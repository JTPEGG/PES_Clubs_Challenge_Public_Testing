"""Career loan and contract lifecycle, tied to verified PES season boundaries.

This is a career-desk ledger, not a PES save editor. Morale cannot affect Xbox
match performance. Player refusal is handled separately by world_player_morale.
Unknown salary/expiry never silently receives a fabricated value.
"""
from datetime import date

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_career_contract_snapshots(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 parent_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 weekly_wage_gbp INTEGER CHECK(weekly_wage_gbp>=0),
 expires_on TEXT,
 renewal_status TEXT NOT NULL CHECK(renewal_status IN
 ('unknown','open','unwilling','negotiating','agreed')),
 source_kind TEXT NOT NULL,
 PRIMARY KEY(career_id,player_id)
);
CREATE TABLE IF NOT EXISTS world_career_loan_agreements(
 loan_id INTEGER PRIMARY KEY,
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 parent_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 borrower_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 start_date TEXT NOT NULL,
 return_date TEXT NOT NULL,
 loan_fee_gbp INTEGER NOT NULL CHECK(loan_fee_gbp>=0),
 borrower_wage_share_pct INTEGER NOT NULL CHECK(borrower_wage_share_pct BETWEEN 0 AND 100),
 wage_commitment_gbp INTEGER NOT NULL CHECK(wage_commitment_gbp>=0),
 status TEXT NOT NULL CHECK(status IN ('agreed','active','returned','cancelled')),
 source_kind TEXT NOT NULL,
 agreed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(parent_club_id<>borrower_club_id),
 CHECK(return_date>start_date)
);
CREATE UNIQUE INDEX IF NOT EXISTS world_active_loan_once
 ON world_career_loan_agreements(career_id,player_id)
 WHERE status IN ('agreed','active');
CREATE TABLE IF NOT EXISTS world_career_free_agents(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 former_club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 available_from TEXT NOT NULL,
 reason TEXT NOT NULL,
 PRIMARY KEY(career_id,player_id)
);
CREATE TABLE IF NOT EXISTS world_career_lifecycle_events(
 event_id INTEGER PRIMARY KEY,
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 event_kind TEXT NOT NULL,
 effective_date TEXT NOT NULL,
 details TEXT NOT NULL,
 UNIQUE(career_id,player_id,event_kind,effective_date)
);
"""

def initialize_career_lifecycle(conn):
    conn.executescript(SCHEMA)
    from world_historical_career_finances import initialize_historical_finances
    initialize_historical_finances(conn)
    conn.commit()


def seed_career_contracts(conn, *, career_id, dataset_id):
    """Called inside initial career creation transaction, no auto commits."""
    if not conn.execute("""SELECT 1 FROM sqlite_master WHERE
        type='table' AND name='world_dataset_contract_snapshots'""").fetchone():
        return 0
    before=conn.total_changes
    conn.execute("""INSERT OR IGNORE INTO world_career_contract_snapshots
        (career_id,player_id,parent_club_id,weekly_wage_gbp,expires_on,
         renewal_status,source_kind)
        SELECT ?,d.player_id,d.club_id,d.weekly_wage_gbp,d.expires_on,
               d.renewal_status,d.source_name
        FROM world_dataset_contract_snapshots d
        JOIN world_career_registrations r ON r.player_id=d.player_id
            AND r.career_id=?
        WHERE d.dataset_id=? AND (r.club_id=d.club_id OR EXISTS (
             SELECT 1 FROM world_dataset_initial_loans l
             WHERE l.dataset_id=d.dataset_id AND l.player_id=d.player_id
               AND l.parent_club_id=d.club_id AND l.borrower_club_id=r.club_id
        ))""",(career_id,career_id,dataset_id))
    return conn.total_changes-before


def agree_loan(conn, *, career_id, player_id, borrower_club_id,
               loan_fee_gbp=0, borrower_wage_share_pct=100,
               lender_approved=False, borrower_approved=False,
               player_approved=False, board_approved=False, now=None):
    """Agree a real, consented one-season loan, pending deadline registration.

    This engine primitive is NOT a manager-screen button or AI offer generator.
    The future market negotiator must obtain all four consents independently.
    """
    from world_preseason_window import assert_window_allows_negotiation
    if not all(x is True for x in
               (lender_approved,borrower_approved,player_approved,board_approved)):
        raise ValueError("Lender, borrower, player and board consent all required")
    if type(loan_fee_gbp) is not int or loan_fee_gbp<0:
        raise ValueError("Loan fee must be whole nonnegative GBP")
    if (type(borrower_wage_share_pct) is not int or
            not 0<=borrower_wage_share_pct<=100):
        raise ValueError("Wage contribution must be 0-100 percent")
    snap=assert_window_allows_negotiation(conn,career_id=career_id,now=now)
    if snap is None:raise ValueError("Start the 30-minute pre-season window first")
    career=conn.execute("""SELECT pes_lock_date,next_summer_date FROM world_career_saves
        WHERE career_id=? AND state='sandbox'""",(career_id,)).fetchone()
    if career is None:raise ValueError("No active development career")
    original=conn.execute("""SELECT club_id FROM world_career_registrations
        WHERE career_id=? AND player_id=?""",(career_id,player_id)).fetchone()
    if original is None or original[0]==borrower_club_id:
        raise ValueError("Player must belong to a different parent club")
    parent=original[0]
    if conn.execute("""SELECT 1 FROM world_career_offers
        WHERE career_id=? AND player_id=? AND status='agreed_future'""",
        (career_id,player_id)).fetchone():
        raise ValueError("Player already agreed a permanent transfer")
    if not conn.execute("""SELECT 1 FROM world_career_club_ledger
        WHERE career_id=? AND club_id=?""",(career_id,borrower_club_id)).fetchone():
        raise ValueError("Borrower not a club in this career")
    contract=conn.execute("""SELECT weekly_wage_gbp,expires_on
        FROM world_career_contract_snapshots WHERE career_id=? AND player_id=?
        AND parent_club_id=?""",(career_id,player_id,parent)).fetchone()
    if contract is None or contract[0] is None:
        raise ValueError("Source-backed parent wage is required to fund the loan")
    if contract[1] and contract[1]<career[1]:
        raise ValueError("Parent contract expires before the loan's return date")
    weekly=(contract[0]*borrower_wage_share_pct+99)//100
    budget=conn.execute("""SELECT transfer_budget,weekly_wage_budget,
        committed_fees,committed_wages FROM world_career_club_ledger
        WHERE career_id=? AND club_id=?""",(career_id,borrower_club_id)).fetchone()
    if (budget[0]-budget[2]<loan_fee_gbp or
            budget[1]-budget[3]<weekly):
        raise ValueError("Borrower cannot afford the proposed loan")
    from world_preseason_window import _utc,_iso
    conn.execute("BEGIN IMMEDIATE")
    try:
        cur=conn.execute("""INSERT INTO world_career_loan_agreements
            (career_id,player_id,parent_club_id,borrower_club_id,start_date,
             return_date,loan_fee_gbp,borrower_wage_share_pct,
             wage_commitment_gbp,status,source_kind)
             VALUES(?,?,?,?,?,?,?,?,?,'agreed','consented-development-loan-v1')""",
            (career_id,player_id,parent,borrower_club_id,career[0],career[1],
             loan_fee_gbp,borrower_wage_share_pct,weekly))
        conn.commit()
        return cur.lastrowid
    except Exception:
        conn.rollback()
        raise


def activate_agreed_loans(conn, *, career_id, effective_date):
    """Caller holds the same transaction as permanent transfer registration."""
    # Standalone legacy tests and pre-migration careers may not have opted
    # into this additive module; an empty loan ledger is a no-op.
    if not conn.execute("""SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='world_career_loan_agreements'""").fetchone():
        return 0
    loans=conn.execute("""SELECT loan_id,player_id,parent_club_id,
        borrower_club_id,loan_fee_gbp,wage_commitment_gbp FROM
        world_career_loan_agreements WHERE career_id=? AND status='agreed'
        ORDER BY loan_id""",(career_id,)).fetchall()
    count=0
    for lid,pid,parent,buyer,fee,wage in loans:
        source=conn.execute("""SELECT club_id FROM world_career_registrations
            WHERE career_id=? AND player_id=?""",(career_id,pid)).fetchone()
        if source is None or source[0]!=parent:
            raise ValueError("Loan parent no longer holds player registration")
        budget=conn.execute("""SELECT transfer_budget,weekly_wage_budget,
            committed_fees,committed_wages FROM world_career_club_ledger
            WHERE career_id=? AND club_id=?""",(career_id,buyer)).fetchone()
        if (budget is None or budget[2]+fee>budget[0] or
                budget[3]+wage>budget[1]):
            raise ValueError("Loan cannot be registered within borrower budget")
        conn.execute("""UPDATE world_career_club_ledger
            SET committed_fees=committed_fees+?,
                committed_wages=committed_wages+?
            WHERE career_id=? AND club_id=?""",(fee,wage,career_id,buyer))
        conn.execute("""UPDATE world_career_registrations SET club_id=?
            WHERE career_id=? AND player_id=? AND club_id=?""",
            (buyer,career_id,pid,parent))
        conn.execute("""UPDATE world_career_loan_agreements SET status='active'
            WHERE loan_id=? AND status='agreed'""",(lid,))
        conn.execute("""INSERT INTO world_career_lifecycle_events
            (career_id,player_id,event_kind,effective_date,details)
            VALUES(?,?,?,?,?)""",
            (career_id,pid,"loan_started",effective_date,
             "Loan registered in PES career ledger; game file unchanged"))
        count+=1
    return count


def reconcile_verified_season_end(conn, *, career_id, season_index, as_of):
    """Return loans/expire contracts only after an attested completed season.

    Never advances from elapsed wall clock or a simulated match. The existing
    reputation season ledger is used as proof of verified season completion.
    """
    date.fromisoformat(as_of)
    if type(season_index) is not int or season_index<1:
        raise ValueError("Verified season index required")
    if not conn.execute("""SELECT 1 FROM sqlite_master
        WHERE name='world_career_reputation_seasons' AND type='table'""").fetchone():
        raise ValueError("Season completion evidence is unavailable")
    if not conn.execute("""SELECT 1 FROM world_career_reputation_seasons
        WHERE career_id=? AND season_index=? LIMIT 1""",
        (career_id,season_index)).fetchone():
        raise ValueError("No recorded season completion for this career")
    from world_preseason_window import window_snapshot
    snap=window_snapshot(conn,career_id=career_id)
    if snap["state"]!="closed":
        raise ValueError("Pre-season registration must close first")
    season=conn.execute("""SELECT next_summer_date FROM world_career_saves
        WHERE career_id=?""",(career_id,)).fetchone()
    if season is None or as_of<season[0]:
        raise ValueError("Do not mature contracts before next summer")
    from world_historical_career_finances import is_historical_finance_career
    payroll_tracking=is_historical_finance_career(conn,career_id)
    conn.execute("BEGIN IMMEDIATE")
    try:
        returned=0
        expired=0
        for lid,pid,parent,borrower,wage,return_date in conn.execute(
            """SELECT loan_id,player_id,parent_club_id,borrower_club_id,
                wage_commitment_gbp,return_date FROM world_career_loan_agreements
                WHERE career_id=? AND status='active' AND return_date<=?""",
            (career_id,as_of)).fetchall():
            current=conn.execute("""SELECT club_id FROM world_career_registrations
                WHERE career_id=? AND player_id=?""",(career_id,pid)).fetchone()
            if current is None or current[0]!=borrower:
                raise ValueError("Loan return conflicts with player ownership")
            conn.execute("""UPDATE world_career_registrations SET club_id=?
                WHERE career_id=? AND player_id=?""",(parent,career_id,pid))
            changed=conn.execute("""UPDATE world_career_club_ledger SET
                committed_wages=committed_wages-? WHERE career_id=? AND club_id=?
                AND committed_wages>=?""",(wage,career_id,borrower,wage))
            if changed.rowcount!=1:
                raise ValueError("Borrower payroll underflow at loan return")
            if payroll_tracking:
                # The initial-loan parent originally paid the remaining wage.
                # Returning the player increases parent liability to 100%.
                changed=conn.execute("""UPDATE world_career_club_ledger SET
                    committed_wages=committed_wages+?
                    WHERE career_id=? AND club_id=?""",(wage,career_id,parent))
                if changed.rowcount!=1:
                    raise ValueError("Loan parent missing from financial career")
            conn.execute("""UPDATE world_career_loan_agreements
                SET status='returned' WHERE loan_id=?""",(lid,))
            conn.execute("""INSERT OR IGNORE INTO world_career_lifecycle_events
                (career_id,player_id,event_kind,effective_date,details)
                VALUES(?,?,?,?,?)""",
                (career_id,pid,"loan_returned",return_date,"Returned to parent after verified season"))
            returned+=1
        for pid,parent,expires in conn.execute("""SELECT player_id,parent_club_id,expires_on
            FROM world_career_contract_snapshots
            WHERE career_id=? AND expires_on IS NOT NULL AND expires_on<=?
              AND renewal_status!='agreed'""",
            (career_id,as_of)).fetchall():
            current=conn.execute("""SELECT club_id FROM world_career_registrations
                WHERE career_id=? AND player_id=?""",(career_id,pid)).fetchone()
            if not current or current[0]!=parent:continue
            conn.execute("""INSERT OR IGNORE INTO world_career_free_agents
                (career_id,player_id,former_club_id,available_from,reason)
                VALUES(?,?,?,?,'contract_expired')""",(career_id,pid,parent,expires))
            if payroll_tracking:
                record=conn.execute("""SELECT weekly_wage_gbp FROM
                   world_career_contract_snapshots WHERE career_id=?
                   AND player_id=?""",(career_id,pid)).fetchone()
                if record and record[0] is not None:
                    changed=conn.execute("""UPDATE world_career_club_ledger SET
                        committed_wages=committed_wages-?
                        WHERE career_id=? AND club_id=?
                        AND committed_wages>=?""",
                        (record[0],career_id,parent,record[0]))
                    if changed.rowcount!=1:
                        raise ValueError("Parent payroll underflow on contract expiry")
            conn.execute("""DELETE FROM world_career_registrations
                WHERE career_id=? AND player_id=?""",(career_id,pid))
            conn.execute("""INSERT OR IGNORE INTO world_career_lifecycle_events
                (career_id,player_id,event_kind,effective_date,details)
                VALUES(?,?,?,?,?)""",
                (career_id,pid,"contract_expired",expires,
                 "Contract expired without a recorded renewal; player becomes free agent"))
            expired+=1
        conn.commit()
        return {"loans_returned":returned,"contracts_expired":expired}
    except Exception:
        conn.rollback()
        raise
