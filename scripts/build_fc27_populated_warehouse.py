"""Build FC27's first *populated* immutable reference warehouse; no PES export.

Three separately versioned inputs: sourced world/competition registry,
historical men's salary/contract/loan archive, modelled club finance overlay.
Stable edition-scoped player_key and club_key are preserved without fuzzy joins.
Original input SQLite files are opened query-only and are never modified.
Career-specific transfers belong in a *separate* overlay, not this warehouse.
"""
from __future__ import annotations
import argparse,hashlib,json,sqlite3
from pathlib import Path

EDITION=2027
CORE=(
 "offensive_awareness","ball_control","dribbling","tight_possession",
 "low_pass","lofted_pass","finishing","heading","place_kicking","curl",
 "speed","acceleration","kicking_power","jump","physical_contact",
 "balance","stamina","defensive_awareness","ball_winning","aggression",
 "gk_awareness","gk_catching","gk_clearing","gk_reflexes","gk_reach")
AUX=("weak_foot_usage","weak_foot_accuracy","form","injury_resistance")
EXPECTED={"clubs":659,"leagues":53,"players":17593,"original_players":17849,
          "playable_clubs":344,"playable_players":9269,"routes":16}
GAPS=(
 ("managers","not_populated","Manager IDs, appointments, histories, philosophies and attributes need a canonical sourced/explicitly modelled enrichment."),
 ("stadiums_and_facilities","not_populated","No complete source-dated stadium tenancy, capacities, training and youth facility coverage."),
 ("player_personality","not_populated","Do not misrepresent hypothetical ambition, loyalty and temperament as observations of real people."),
 ("position_suitability","partial_source","Primary and alternative role labels retained; position-specific suitability scores are not certified uniformly."),
 ("financial_reliability","model_estimate","Historical wages, game contracts and club budgets contain openly labelled simulations, not audited real statements."),
 ("career_engine_binding","not_activated","Immutable 2027 warehouse is independent of mutable world_career_* saves; production unchanged."),
 ("historical_editions","fc27_only","FC26 and other historical editions are not populated into this new warehouse yet."),
)

def open_ro(path):
    path=Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    con=sqlite3.connect(f"file:{path.as_posix()}?mode=ro",uri=True)
    con.execute("PRAGMA query_only=ON")
    return con

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        while block:=f.read(1024*1024):h.update(block)
    return h.hexdigest()

def _stats(core,aux):
    a=json.loads(core);b=json.loads(aux)
    if not isinstance(a,dict) or set(a)!=set(CORE) or any(type(v)!=int or not 40<=v<=99 for v in a.values()):
        raise ValueError("Historical PES conversion has incomplete or unexpected 25 core attributes")
    if not isinstance(b,dict) or set(b)!=set(AUX) or any(type(v)!=int for v in b.values()):
        raise ValueError("Historical PES conversion has incomplete 4 auxiliary attributes")
    for k in ("weak_foot_usage","weak_foot_accuracy"):
        if not 1<=b[k]<=4:raise ValueError("Weak-foot estimate outside 1-4")
    if not 1<=b["form"]<=8 or not 1<=b["injury_resistance"]<=3:
        raise ValueError("Auxiliary game estimate outside valid PES scale")
    return a,b

def build(world_db,contracts_db,finances_db,output,*,strict=True):
    files=[Path(x) for x in (world_db,contracts_db,finances_db)]
    output=Path(output)
    if output.exists():
        raise FileExistsError("Immutable reference build must not overwrite an existing warehouse")
    output.parent.mkdir(parents=True,exist_ok=True)
    schema=(Path(__file__).resolve().parents[1]/"warehouse/fc27_populated_reference_v1.sql").read_text()
    world=open_ro(files[0]);men=open_ro(files[1]);finance=open_ro(files[2])
    out=sqlite3.connect(output)
    out.execute("PRAGMA foreign_keys=ON")
    out.execute("PRAGMA journal_mode=DELETE")
    report={}
    try:
        out.executescript(schema)
        out.execute("""
          INSERT INTO wh_fc27_snapshot(edition,season,state,immutable_source_clubs,
             source_mens_players,source_active_players)
          VALUES(2027,'2026/27','frozen_reference_not_live_career',659,17849,17593)
        """)
        manifest=(
          ("fc27_game_world",files[0].name,digest(files[0]),"competition_source_and_game_scope","mixed",2027),
          ("historical_men_contracts",files[1].name,digest(files[1]),"male_player_contracts_and_loans","mixed",2027),
          ("historical_club_finances",files[2].name,digest(files[2]),"source_backed_game_finance_model","game_model",2027)
        )
        out.executemany("INSERT INTO wh_fc27_source_manifest VALUES(?,?,?,?,?,?)",manifest)
        leagues=list(world.execute("""
          SELECT s.competition_code,s.country,s.name,s.tier,s.movement_policy,
                 s.original_game_source_clubs,c.membership_basis,
                 CASE WHEN p.competition_code IS NULL THEN 0 ELSE 1 END
          FROM fc27_effective_world_league_movement_scope s
          JOIN fc27_2026_27_active_domestic_competitions c
            ON c.competition_code=s.competition_code
          LEFT JOIN fc27_effective_manager_selectable_competitions p
            ON p.competition_code=s.competition_code AND p.edition=s.edition
          WHERE s.edition=2027
          ORDER BY s.competition_code
        """))
        if strict and len(leagues)!=EXPECTED["leagues"]:
            raise ValueError("Expected 53 original FC27 domestic divisions")
        out.executemany("""
         INSERT INTO wh_fc27_competitions VALUES(2027,?,?,?,?,?,?,?,?)
        """,[(code,country,name,tier,policy,playable,n,source)
             for code,country,name,tier,policy,n,source,playable in leagues])
        clubs=list(world.execute("""
          SELECT c.club_key,c.original_club,c.competition_code,c.competition_mode
          FROM fc27_career_world_clubs c WHERE c.edition=2027
          ORDER BY c.club_key
        """))
        if strict and (len(clubs)!=659 or
          sum(c[3]!="closed_background_world" for c in clubs)!=344):
            raise ValueError("Original source club identity or playable career scope changed")
        out.executemany("""
           INSERT INTO wh_fc27_clubs VALUES(2027,?,?,?,?)
        """,clubs)
        active={c[0] for c in clubs}
        nsource=men.execute("SELECT COUNT(*) FROM players WHERE edition=2027").fetchone()[0]
        if strict and nsource!=EXPECTED["original_players"]:
            raise ValueError("2027 men's source archive changed")
        sourcekeys={k for (k,) in men.execute("SELECT club_key FROM clubs WHERE edition=2027")}
        if not active.issubset(sourcekeys):
            raise ValueError("Some FC27 career clubs lack original player source club IDs")
        contracts={}
        for r in men.execute("""
          SELECT f.player_key,f.model_weekly_wage_gbp,f.source_wage_weekly_gbp,
            f.wage_provenance,f.game_contract_expires_on,f.expiry_provenance,
            f.estimated_squad_tier,f.wage_quality_warning,f.model_version
          FROM starting_player_finances f WHERE f.edition=2027
        """):
            if r[0] in contracts:raise ValueError("Duplicate contract ID")
            contracts[r[0]]=r
        player_records=[];rosters=[];positions=[];all_attrs=[];contract_rows=[];excluded=0
        for (key,source_id,provider_key,name,birth,nationality,foot,height,weight,overall,
             primary,alts,fit,club_key,assignment,provider,core,aux) in men.execute("""
          SELECT player_key,source_player_id,namespaced_source_player_key,player_name,
             date_of_birth,nationality,preferred_foot,height_cm,weight_kg,
             source_overall,primary_position,alternative_positions,position_fit_indices,
             club_key,assignment,source_provider,pes_abilities_json,pes_additional_json
          FROM players WHERE edition=2027 ORDER BY source_row_number
        """):
            if club_key not in active:
                excluded+=1
                continue
            if assignment!="at_club" or not key or not primary or key not in contracts:
                raise ValueError("Unassigned or salary-unmatched active FC27 source player")
            a,b=_stats(core,aux)
            player_records.append((2027,key,source_id,provider_key,name,birth,nationality,
                foot,height,weight,overall,primary,alts,fit,provider))
            rosters.append((2027,key,club_key,"at_club"))
            positions.append((2027,key,primary,"primary",None,"source_unknown"))
            all_attrs.extend((2027,key,attr,"pes2020_core_estimate",a[attr],"fifa_pes_v2_converted_model")
                             for attr in CORE)
            all_attrs.extend((2027,key,attr,"pes2020_auxiliary_estimate",b[attr],"fifa_pes_v2_converted_model")
                             for attr in AUX)
            f=contracts[key]
            contract_rows.append((2027,key,f[1],f[2],f[3],f[4],f[5],f[6],f[7] or "",f[8]))
        if strict and (len(player_records)!=EXPECTED["players"] or excluded!=256):
            raise ValueError("FC27 17,593/256 original player source selection changed")
        out.executemany("""
          INSERT INTO wh_fc27_players VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,player_records)
        out.executemany("INSERT INTO wh_fc27_starting_rosters VALUES(?,?,?,?)",rosters)
        out.executemany("INSERT INTO wh_fc27_player_positions VALUES(?,?,?,?,?,?)",positions)
        # Normalized ratings are stored individually; flush in batches to cap memory.
        for start in range(0,len(all_attrs),25000):
            out.executemany("INSERT INTO wh_fc27_player_attributes VALUES(?,?,?,?,?,?)",
                            all_attrs[start:start+25000])
        out.executemany("""
          INSERT INTO wh_fc27_starting_contracts VALUES(?,?,?,?,?,?,?,?,?,?)
        """,contract_rows)
        loans=[]
        for r in men.execute("""
          SELECT l.player_key,l.borrower_club_key,l.resolved_parent_club_key,
              l.parent_status,l.game_return_date,l.simulated_borrower_wage_share_pct
          FROM starting_source_loans l WHERE l.edition=2027
        """):
            if r[1] not in active:continue
            if r[2] is not None and r[2] not in active:
                r=(r[0],r[1],None,"parent_outside_2027_active_clubs",r[4],r[5])
            loans.append((2027,)+tuple(r))
        out.executemany("INSERT INTO wh_fc27_starting_loans VALUES(?,?,?,?,?,?,?)",loans)
        model=finance.execute("SELECT model_version FROM model_metadata").fetchone()
        if model is None:raise ValueError("Club finance source model provenance missing")
        finrows=[]
        for key,pay,budget,transfer,headroom,score,band,origin,reliability in finance.execute("""
          SELECT club_key,starting_payroll_weekly_gbp,game_wage_budget_weekly_gbp,
                 game_transfer_budget_gbp,starting_wage_headroom_weekly_gbp,
                 financial_capacity_percentile,financial_capacity_band,
                 finance_source,reliability_flag
          FROM club_financial_profiles WHERE edition=2027
        """):
            if key not in active:continue
            finrows.append((2027,key,pay,budget,transfer,headroom,score,band,origin,reliability,model[0]))
        if strict and len(finrows)!=659:
            raise ValueError("Financial model missing exact FC27 659 source clubs")
        out.executemany("INSERT INTO wh_fc27_club_financials VALUES(?,?,?,?,?,?,?,?,?,?,?)",finrows)
        routes=list(world.execute("""
          SELECT upper_code,lower_code,route_type,direct_promotions,
            lower_playoff_promotions,upper_direct_relegations,
            upper_conditional_survival_places,rule_notes,executable_career_movement
          FROM fc27_effective_playable_season_end_routes WHERE edition=2027
        """))
        if strict and len(routes)!=16:raise ValueError("Effective 16 FC27 movement rules incomplete")
        out.executemany("""
          INSERT INTO wh_fc27_movement_routes VALUES(2027,?,?,?,?,?,?,?,?,?)
        """,routes)
        out.executemany("INSERT INTO wh_fc27_coverage_gaps VALUES(2027,?,?,?)",GAPS)
        playable=out.execute("SELECT COUNT(*) FROM wh_fc27_playable_starting_squads").fetchone()[0]
        if strict and playable!=9269:
            raise ValueError("FC27 reference playable-club player assignments do not reconcile")
        if out.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Unified warehouse contains orphan player, club or competition ID")
        counts={
          "edition":2027,"reference_clubs":len(clubs),
          "reference_competitions":len(leagues),
          "intended_playable_competitions":sum(row[-1] for row in leagues),
          "intended_playable_clubs":sum(c[3]!="closed_background_world" for c in clubs),
          "source_mens_player_records":nsource,
          "unified_registered_players":len(player_records),
          "out_of_scope_source_player_rows_retained_only_in_archive":excluded,
          "normalized_player_attributes":len(all_attrs),
          "starting_player_contracts":len(contract_rows),
          "starting_club_finance_profiles":len(finrows),
          "starting_source_loans":len(loans),
          "playable_starting_roster_players":playable,
          "sourced_season_end_routes":len(routes),
          "known_coverage_gap_domains":len(GAPS),
          "all_native_PES_and_production_career_exports_deferred":True,
          "historical_sources_read_only":True,
          "snapshot_lifecycle":"frozen_reference_not_live_career"
        }
        out.commit()
        if out.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("Warehouse SQLite integrity check failed")
        report=counts
    except Exception:
        out.close()
        if output.exists():output.unlink()
        raise
    finally:
        world.close();men.close();finance.close()
    out.close()
    manifest_path=output.with_suffix(".audit.json")
    manifest_path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--world",required=True)
    parser.add_argument("--contracts",required=True)
    parser.add_argument("--club-finances",required=True)
    parser.add_argument("--output",required=True)
    x=parser.parse_args()
    print(json.dumps(build(x.world,x.contracts,x.club_finances,x.output),indent=2))
if __name__=="__main__":main()
