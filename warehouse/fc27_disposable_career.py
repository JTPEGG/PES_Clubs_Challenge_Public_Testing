"""Disposable FC27 career seed from immutable unified warehouse (no production writes)."""
from __future__ import annotations
import hashlib,sqlite3
from pathlib import Path
from warehouse.fc27_reference_reader import FC27WarehouseReader

SQL=(Path(__file__).resolve().parent/"fc27_disposable_career_overlay.sql").read_text()

def _sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        while data:=f.read(1024*1024):h.update(data)
    return h.hexdigest()

def seed_test_career(reference_path,career_path,*,career_id="fc27-isolated-qa"):
    source=Path(reference_path).resolve()
    target=Path(career_path)
    if target.exists():raise FileExistsError("Never overwrite an existing career or test database")
    target.parent.mkdir(parents=True,exist_ok=True)
    with FC27WarehouseReader(source) as src,sqlite3.connect(target) as career:
        career.execute("PRAGMA foreign_keys=ON")
        career.executescript(SQL)
        career.execute("""
          INSERT INTO fc27_demo_career_metadata(career_id,edition,source_sha256,simulation_status)
          VALUES(?,2027,?,'isolated_test_only')
        """,(career_id,_sha(source)))
        clubs=src.conn.execute("""
          SELECT c.club_key,c.competition_code,
            CASE WHEN c.career_scope='closed_background_world' THEN 0 ELSE 1 END
          FROM wh_fc27_clubs c WHERE edition=2027
        """).fetchall()
        career.executemany("""
          INSERT INTO fc27_demo_career_clubs VALUES(?,?,?,?)
        """,[(career_id,*tuple(r)) for r in clubs])
        players=src.conn.execute("""
          SELECT player_key,club_key
          FROM wh_fc27_starting_rosters WHERE edition=2027
        """).fetchall()
        career.executemany("""
          INSERT INTO fc27_demo_career_registrations VALUES(?,?,?,?,0)
        """,[(career_id,k,c,c) for k,c in players])
        career.executemany("""
          INSERT INTO fc27_demo_career_starting_contracts VALUES(?,?,?,?,?,?)
        """,[(career_id,*tuple(r)) for r in src.conn.execute("""
            SELECT player_key,weekly_game_wage_gbp,wage_provenance,
              contract_expires_on,expiry_provenance
            FROM wh_fc27_starting_contracts WHERE edition=2027
          """)])
        career.executemany("""
          INSERT INTO fc27_demo_career_starting_finances VALUES(?,?,?,?,?,?)
        """,[(career_id,*tuple(r)) for r in src.conn.execute("""
            SELECT club_key,starting_payroll_weekly_gbp,
              game_wage_budget_weekly_gbp,game_transfer_budget_gbp,finance_provenance
            FROM wh_fc27_club_financials WHERE edition=2027
          """)])
        totals={
         "clubs":career.execute("SELECT COUNT(*) FROM fc27_demo_career_clubs").fetchone()[0],
         "players":career.execute("SELECT COUNT(*) FROM fc27_demo_career_registrations").fetchone()[0],
         "contracts":career.execute("SELECT COUNT(*) FROM fc27_demo_career_starting_contracts").fetchone()[0],
         "club_finances":career.execute("SELECT COUNT(*) FROM fc27_demo_career_starting_finances").fetchone()[0],
         "intended_selectable_clubs":career.execute("""
            SELECT COUNT(*) FROM fc27_demo_career_clubs
            WHERE intended_manager_selectable=1
         """).fetchone()[0]
        }
        if totals!={"clubs":659,"players":17593,"contracts":17593,
                   "club_finances":659,"intended_selectable_clubs":344}:
            raise ValueError("Career seed does not match frozen reference snapshot")
        if career.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Career overlay contains orphan keys")
        career.commit()
        return dict(totals,source_checksum=_sha(source),career_id=career_id,
                    mutable_career_only=True)

def apply_test_registration_change(db,*,career_id,player_key,from_club,to_club,transaction_key):
    """Proof-only event, no contract/fee/transfer-engine finalisation represented."""
    if not transaction_key or from_club==to_club:
        raise ValueError("A distinct transaction and target club are required")
    prior=db.execute("""
      SELECT player_key,selling_club_key,buying_club_key FROM fc27_demo_registration_events
      WHERE career_id=? AND transaction_key=?
    """,(career_id,transaction_key)).fetchone()
    if prior:
        if prior!=(player_key,from_club,to_club):
            raise ValueError("Duplicate event key cannot represent two moves")
        return "already_applied"
    row=db.execute("""
      SELECT current_club_key,revision
      FROM fc27_demo_career_registrations
      WHERE career_id=? AND player_key=?
    """,(career_id,player_key)).fetchone()
    if row is None or row[0]!=from_club:
        raise ValueError("Player is not registered at nominated club")
    if not db.execute("""
       SELECT 1 FROM fc27_demo_career_clubs WHERE career_id=? AND club_key=?
    """,(career_id,to_club)).fetchone():
        raise ValueError("Buying club does not exist in frozen 659-club world")
    with db:
        updated=db.execute("""
          UPDATE fc27_demo_career_registrations
          SET current_club_key=?,revision=?
          WHERE career_id=? AND player_key=? AND revision=? AND current_club_key=?
        """,(to_club,row[1]+1,career_id,player_key,row[1],from_club))
        if updated.rowcount!=1:raise ValueError("Conflicting registration revision")
        db.execute("""
          INSERT INTO fc27_demo_registration_events VALUES(?,?,?,?,?,?,?,
            'verified_test_simulation_not_a_real_transfer')
        """,(career_id,transaction_key,player_key,from_club,to_club,row[1],row[1]+1))
    return "applied"
