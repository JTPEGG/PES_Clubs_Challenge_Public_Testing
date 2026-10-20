"""First safe PES V2 historical career importer: FIFA 26 and FC 27.

Uses only source-labelled competitions; no guessed historical league membership.
Creates a fresh, edition-scoped immutable dataset with salaries, contracts,
source loans and modelled club budgets. Does not touch production careers.
"""
import argparse,hashlib,json,sqlite3
from pathlib import Path
from datetime import date

SUPPORTED=(2026,2027)
SCHEMA="""
CREATE TABLE IF NOT EXISTS world_dataset_pes_v2_metadata(
 dataset_id TEXT PRIMARY KEY REFERENCES world_datasets(dataset_id),
 edition INTEGER NOT NULL, unknown_source_player_rows INTEGER NOT NULL,
 source_sha256 TEXT NOT NULL, model_finance_sha256 TEXT NOT NULL,
 circumstances_sha256 TEXT NOT NULL,source_provenance TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS world_dataset_pes_v2_club_map(
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 source_key TEXT NOT NULL,world_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 PRIMARY KEY(dataset_id,source_key),UNIQUE(dataset_id,world_id));
CREATE TABLE IF NOT EXISTS world_dataset_pes_v2_player_map(
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 source_key TEXT NOT NULL,world_id INTEGER NOT NULL REFERENCES world_players(player_id),
 PRIMARY KEY(dataset_id,source_key),UNIQUE(dataset_id,world_id));
"""
def checksum(path):
    h=hashlib.sha256()
    with open(path,"rb") as stream:
        for block in iter(lambda:stream.read(1048576),b""):h.update(block)
    return h.hexdigest()

def season(year):return f"{year-1}/{year%100:02d}"

def edition_options(conn):
    return [dict(edition=y,season=s,players=p,clubs=c,
        ready_to_import=(y in SUPPORTED and missing==0),
        reason="source league membership incomplete" if y not in SUPPORTED or missing else "")
        for y,s,p,c,missing in conn.execute("""SELECT edition,season,
         imported_player_rows,club_count,missing_league_clubs
         FROM editions ORDER BY edition""")]

def initialize_target(conn):
    from world_v2 import initialize_world
    from world_explorer import initialize_catalog
    from world_careers import initialize_career_engine
    from world_historical_profiles import initialize_historical_profiles
    from world_import import install_import_schema
    initialize_world(conn)
    initialize_catalog(conn)
    initialize_career_engine(conn)
    initialize_historical_profiles(conn)
    install_import_schema(conn)
    conn.executescript(SCHEMA)
    conn.commit()

def load_new_world(conn,*,source,finances,circumstances,edition):
    if edition not in SUPPORTED:
        raise ValueError("This edition has no verified complete source league map")
    ds=f"pes-v2-{edition}-mens-01"
    if conn.execute("SELECT 1 FROM world_datasets WHERE dataset_id=?",(ds,)).fetchone():
        raise ValueError("Immutable dataset exists already")
    source=Path(source).resolve();finances=Path(finances).resolve()
    circumstances=Path(circumstances).resolve()
    if len({str(source),str(finances),str(circumstances)})!=3:
        raise ValueError("Source file inputs must be distinct")
    conn.execute("ATTACH DATABASE ? AS hist",(f"file:{source}?mode=ro",))
    conn.execute("ATTACH DATABASE ? AS money",(f"file:{finances}?mode=ro",))
    conn.execute("ATTACH DATABASE ? AS policy",(f"file:{circumstances}?mode=ro",))
    try:
        meta=conn.execute("""SELECT imported_player_rows,club_count,missing_league_clubs
              FROM hist.editions WHERE edition=?""",(edition,)).fetchone()
        if not meta or meta[2]:
            raise ValueError("Incomplete historical source league membership")
        leagues=conn.execute("""SELECT league_key,league_name,source_league_level
          FROM hist.leagues WHERE edition=?""",(edition,)).fetchall()
        clubs=conn.execute("""SELECT club_key,name,league_key,league_conflicts FROM
          hist.clubs WHERE edition=? ORDER BY club_key""",(edition,)).fetchall()
        if len(clubs)!=meta[1] or any(not c[2] or c[3] for c in clubs):
            raise ValueError("Historical club references are incomplete or conflicting")
        league_ids={l[0] for l in leagues}
        if not all(c[2] in league_ids for c in clubs):
            raise ValueError("Historical club references an unknown source league")
        budgets={k:(tb,wb) for k,tb,wb in conn.execute("""SELECT club_key,
             revised_transfer_budget_gbp,revised_total_wage_budget_weekly_gbp
             FROM policy.historical_club_circumstances WHERE edition=?""",(edition,))}
        if len(budgets)!=len(clubs):raise ValueError("Missing club financial profiles")
        players=conn.execute("""SELECT p.player_key,p.player_name,p.date_of_birth,
             p.nationality,p.primary_position,p.source_overall,p.source_player_id,
             p.club_key,p.assignment,f.model_weekly_wage_gbp,
             f.game_contract_expires_on,f.wage_provenance
             FROM hist.players p JOIN hist.starting_player_finances f
             ON f.player_key=p.player_key WHERE p.edition=?
             ORDER BY p.source_row_number""",(edition,)).fetchall()
        if len(players)!=meta[0]:raise ValueError("Incomplete player roster")
        loans=conn.execute("""SELECT player_key,borrower_club_key,
            resolved_parent_club_key,game_return_date,
            simulated_borrower_wage_share_pct,parent_status
            FROM hist.starting_source_loans WHERE edition=?""",(edition,)).fetchall()
        if any(x[5]!="resolved" for x in loans):
            raise ValueError("Unresolved source loan parent must be reconciled")
        loanmap={r[0]:r for r in loans}
        clubset={c[0] for c in clubs}
        if any(x[1] not in clubset or x[2] not in clubset for x in loans):
            raise ValueError("Source loan parent or borrower outside selected edition")
        expect=sum(p[8]=="at_club" for p in players)
        if any(p[8]=="at_club" and p[7] not in clubset for p in players):
            raise ValueError("Unresolved source squad club")
        start=f"{edition-1}-08-01"
        following=f"{edition}-07-01"
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("""INSERT OR IGNORE INTO world_seasons
                 (season_id,label,start_date,registration_lock)
                 VALUES(?,?,?,?)""",(season(edition),season(edition),start,start))
            conn.execute("""INSERT INTO world_datasets
              (dataset_id,season_id,title,source_label,source_date,status)
              VALUES(?,?,?,?,?,'review')""",(ds,season(edition),
                f"Men's FIFA {edition} PES V2 squads", "FIFA edition source; wages/finances are game estimates",start))
            league_map={}
            for ix,(key,name,source_tier) in enumerate(sorted(leagues),start=1):
                code=f"P{edition}-{ix:03d}"
                try:
                    tier=int(float(source_tier)) if source_tier else None
                except ValueError:
                    tier=None
                if tier is not None and not 1<=tier<=20:tier=None
                size=sum(c[2]==key for c in clubs)
                conn.execute("""INSERT INTO world_competitions
                  (competition_id,name,country,tier,expected_clubs)
                  VALUES(?,?,?,?,?)""",(code,f"{name} ({season(edition)})",
                  "Country not verified by source",tier,size))
                league_map[key]=code
            clubmap={}
            for key,name,lkey,conflict in clubs:
                # Source-row-scoped identity avoids false same-name mergers.
                display=f"{name} [{edition}:{hashlib.sha256(key.encode()).hexdigest()[:8]}]"
                cid=conn.execute("""INSERT INTO world_clubs
                   (name,nation,finances_source) VALUES(?,?,?)""",
                   (display,"Unknown", "modelled historical finance")).lastrowid
                clubmap[key]=cid
                conn.execute("""INSERT INTO world_dataset_entries
                  (dataset_id,competition_id,club_id) VALUES(?,?,?)""",
                  (ds,league_map[lkey],cid))
                conn.execute("""INSERT INTO world_dataset_pes_v2_club_map
                  VALUES(?,?,?)""",(ds,key,cid))
                conn.execute("""INSERT INTO world_dataset_club_finances
                  (dataset_id,club_id,transfer_budget_gbp,weekly_wage_budget_gbp,source_name)
                  VALUES(?,?,?,?,?)""",(ds,cid,*budgets[key],"GAME_MODEL:historical_financial_circumstances_v2"))
            registered=0
            for key,name,dob,nation,position,overall,srcid,club,assignment,wage,expires,provenance in players:
                if assignment!="at_club":continue
                registered+=1
                pid=conn.execute("""INSERT INTO world_players
                     (full_name,birth_date,nationality,primary_position,source_url)
                     VALUES(?,?,?,?,?)""",
                     (name,dob,nation,position,"PES V2 pinned historical FIFA archive")).lastrowid
                conn.execute("""INSERT INTO world_player_source_refs
                     (player_id,source_name,external_id,source_url,identity_status)
                     VALUES(?,?,?,?,?)""",(pid,f"PESV2-{edition}",key,
                       "PES V2 source row", "edition_scoped_source"))
                conn.execute("""INSERT INTO world_dataset_pes_v2_player_map
                     VALUES(?,?,?)""",(ds,key,pid))
                conn.execute("""INSERT INTO world_dataset_rosters
                     (dataset_id,player_id,club_id,evidence,verification_status)
                     VALUES(?,?,?,?,?)""",(ds,pid,clubmap[club],"source listed borrowing/owning club",
                           "source_snapshot"))
                if overall is not None and 1<=int(overall)<=99:
                    conn.execute("""INSERT INTO world_dataset_ratings
                        (dataset_id,player_id,source_name,source_edition,source_date,
                         external_player_id,overall) VALUES(?,?,?,?,?,?,?)""",
                         (ds,pid,"FIFA annual source",str(edition),start,srcid,int(overall)))
                parent=loanmap[key][2] if key in loanmap else club
                if parent not in clubmap:raise ValueError("Parent club not mapped")
                if key in loanmap:
                    lo=loanmap[key]
                    if not (date.fromisoformat(start)<date.fromisoformat(lo[3])<
                            date.fromisoformat(following)):
                        raise ValueError("Invalid simulated historical loan date")
                    if expires<lo[3]:raise ValueError("Loan outlasts contract")
                    conn.execute("""INSERT INTO world_dataset_initial_loans
                         (dataset_id,player_id,borrower_club_id,parent_club_id,
                          return_date,borrower_wage_share_pct,model_provenance)
                         VALUES(?,?,?,?,?,?,?)""",(ds,pid,clubmap[club],
                          clubmap[parent],lo[3],lo[4],"sourced_parent_loan_modelled_terms"))
                conn.execute("""INSERT INTO world_dataset_contract_snapshots
                    (dataset_id,player_id,club_id,weekly_wage_gbp,expires_on,
                     renewal_status,source_name) VALUES(?,?,?,?,?,'unknown',?)""",
                    (ds,pid,clubmap[parent],wage,expires,provenance))
            if registered!=expect:raise ValueError("Player registration loss")
            conn.execute("""INSERT INTO world_dataset_historical_finance_policy
                (dataset_id,model_version,provenance) VALUES(?,?,?)""",
                (ds,"historical-finance-events-v2","loan and wages sourced or game-estimated"))
            conn.execute("""INSERT INTO world_dataset_pes_v2_metadata
              VALUES(?,?,?,?,?,?,?)""",
              (ds,edition,len(players)-registered,checksum(source),checksum(finances),
               checksum(circumstances),"Source league labels; separate source-owned loans and financial estimates"))
            counts=dict(clubs=len(clubmap),registered_players=registered,
                contracts=conn.execute("SELECT COUNT(*) FROM world_dataset_contract_snapshots WHERE dataset_id=?",(ds,)).fetchone()[0],
                loans=conn.execute("SELECT COUNT(*) FROM world_dataset_initial_loans WHERE dataset_id=?",(ds,)).fetchone()[0],
                unknown_unregistered=len(players)-registered)
            if counts["contracts"]!=registered or counts["loans"]!=len(loans):
                raise ValueError("Historical career count reconciliation failed")
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Historical import created orphan FK")
            conn.commit()
            return dict(dataset_id=ds,edition=edition,season=season(edition),
              source_date=start,career_summer=f"{edition}-07-01",
              status="new_immutable_review_not_production",**counts)
        except Exception:
            conn.rollback()
            raise
    finally:
        for name in ("hist","money","policy"):
            conn.execute(f"DETACH DATABASE {name}")


if __name__=="__main__":
    args=argparse.ArgumentParser()
    args.add_argument("--source",required=True)
    args.add_argument("--finances",required=True)
    args.add_argument("--circumstances",required=True)
    args.add_argument("--target",required=True)
    args.add_argument("--edition",type=int,required=True,choices=SUPPORTED)
    o=args.parse_args()
    dest=Path(o.target)
    if dest.exists():raise SystemExit("Refuse to overwrite existing career database")
    dest.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(dest) as db:
        db.execute("PRAGMA foreign_keys=ON")
        initialize_target(db)
        print(json.dumps(load_new_world(db,source=o.source,finances=o.finances,
             circumstances=o.circumstances,edition=o.edition),indent=2),flush=True)
