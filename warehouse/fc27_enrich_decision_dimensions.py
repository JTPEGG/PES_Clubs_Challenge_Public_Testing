"""FC27 reference decision dimensions: deterministic gameplay priors, NOT facts.

Extend a *copy* of the approved frozen FC27 warehouse with 659 sourced
financial-circumstance overlays, 659 club sporting/ambition gameplay proxies,
17,593 synthetic neutral-range player behaviour seeds and 659 anonymous
manager-hiring *policies*. Real manager people require ID/source/date evidence
and are not invented by this workflow.

All outputs preserve immutability of the originals and explicitly distinguish
source facts, game models and unknown personal/institutional traits.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean

EDITION=2027
VERSION="fc27-ai-decision-dimensions-v1"
SEED="fc27-personality-neutral-priors-v1-never-real-person-assertions"
EXPECTED_CLUBS=659
EXPECTED_PLAYERS=17593

def _digest(path):
    hash=hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block:=stream.read(1048576):
            hash.update(block)
    return hash.hexdigest()

def _open_ro(path):
    source=Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    conn=sqlite3.connect(f"file:{source.as_posix()}?mode=ro",uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn

def clamp(value,low=0,high=100):
    return int(min(high,max(low,round(value))))

def seed_personality(player_key):
    """Six gameplay priors, deterministic but independent of real identity traits.

    We use the source *identifier*, NOT name, ethnicity, age, nationality,
    perceived behaviour, transfer history or a claim about the person.
    Different careers may update behaviour state separately.
    """
    if not isinstance(player_key,str) or not player_key:
        raise ValueError("Stable original player identity required")
    values=[]
    for label in ("ambition","loyalty","professionalism","temperament",
                  "adaptability","wage_motivation"):
        digest=hashlib.sha256(f"{SEED}|{label}|{player_key}".encode()).digest()
        values.append(35+int.from_bytes(digest[:4],"big")%31)
    return tuple(values)

def model_sporting_appeal(top16_source_overall,tier):
    if top16_source_overall is not None:
        return clamp(42+1.4*(top16_source_overall-60),15,95),"derived_squad"
    # Ranking missing: use neutral *gameplay* context only, never club prestige.
    return clamp(53-5*(tier-1),18,68),"league_tier_fallback"

def model_finance_pressure(*,headroom,payroll,distress):
    if distress=="documented_distress":
        return "distress",96
    if headroom<0:
        return "over_committed",clamp(72+abs(headroom)/max(payroll,1)*25,72,95)
    if payroll>0 and headroom/max(payroll,1)<.10:
        return "tight",55
    return "normal",25

def model_club_game_plan(*,appeal,standing_rank,standing_count,pressure_index,
                         tier):
    if standing_rank is None or standing_count<3:
        band="unassessed"
        score=clamp(42+.55*(appeal-40),20,90)
        urgency=clamp(35+pressure_index*.35,20,90)
    else:
        strength_percentile=(standing_count-standing_rank)/max(standing_count-1,1)
        band=("upper_end" if strength_percentile>=.70 else
              "lower_end" if strength_percentile<=.30 else "mid_table")
        score=clamp(41+appeal*.45+strength_percentile*15,25,95)
        urgency=clamp(28+strength_percentile*28+pressure_index*.25,20,95)
    # Ambition measures aspiration in this game model, not reported board intent.
    if pressure_index>=72:approach="survival"
    elif band=="upper_end" and score>=69:approach="high_ambition"
    elif band=="lower_end":approach="consolidate"
    elif band=="unassessed":approach="unassessed"
    else:approach="balanced"
    return band,score,urgency,approach

def model_manager_hiring(*,sporting_appeal,ambition,financial_pressure,
                          competitive_band):
    if financial_pressure>=72:
        style="financial_rebuild"
    elif ambition>=73 and competitive_band=="upper_end":
        style="results_first"
    elif competitive_band=="lower_end":
        style="development"
    else:style="balanced"
    required=clamp(.54*sporting_appeal+.35*ambition,12,94)
    risk=clamp(66-financial_pressure*.35+(ambition-50)*.25,10,90)
    rebuild=clamp(40+financial_pressure*.44+(65-ambition)*.18,15,94)
    return required,style,risk,rebuild

def build(reference_db,circumstances_db,output,*,strict=True):
    reference=Path(reference_db).resolve()
    output=Path(output)
    if not reference.is_file():
        raise FileNotFoundError(reference)
    if output.exists():
        raise FileExistsError("Never overwrite reference datasets or existing careers")
    output.parent.mkdir(parents=True,exist_ok=True)
    circumstances=_open_ro(circumstances_db)
    with _open_ro(reference) as src:
        row=src.execute("SELECT edition,state FROM wh_fc27_snapshot").fetchone()
        if row!=(2027,"frozen_reference_not_live_career"):
            raise ValueError("Must enrich approved immutable FC27 snapshot")
        clubs=list(src.execute("""
          SELECT c.club_key,c.name,c.competition_code,l.tier
          FROM wh_fc27_clubs c JOIN wh_fc27_competitions l
          ON l.edition=c.edition AND l.competition_code=c.competition_code
          WHERE c.edition=2027 ORDER BY c.club_key
        """))
        if strict and len(clubs)!=EXPECTED_CLUBS:
            raise ValueError("FC27 club snapshot drift")
        source_players=src.execute("""
          SELECT COUNT(*) FROM wh_fc27_players WHERE edition=2027
        """).fetchone()[0]
        if strict and source_players!=EXPECTED_PLAYERS:
            raise ValueError("FC27 source player snapshot drift")
        ratings=defaultdict(list)
        for club_key,overall in src.execute("""
          SELECT r.club_key,p.source_overall
          FROM wh_fc27_starting_rosters r JOIN wh_fc27_players p
            ON p.edition=r.edition AND p.player_key=r.player_key
          WHERE r.edition=2027
        """):
            if type(overall) is int and 1<=overall<=99:
                ratings[club_key].append(overall)
        averages={}
        for club_key,name,competition,tier in clubs:
            top=sorted(ratings.get(club_key,[]),reverse=True)[:16]
            averages[club_key]=(round(mean(top),3) if len(top)>=8 else None,len(top))
        by_league=defaultdict(list)
        for club_key,name,comp,tier in clubs:
            if averages[club_key][0] is not None:
                by_league[comp].append((club_key,averages[club_key][0]))
        ranks={}
        for comp,values in by_league.items():
            # Stable tie breaking by existing source key.
            for idx,(key,value) in enumerate(
                sorted(values,key=lambda x:(-x[1],x[0])),1):
                ranks[key]=idx
    profiles=dict(circumstances.execute("""
      SELECT club_key,edition,preseason_as_of,source_annual_payroll_gbp,
         revised_total_wage_budget_weekly_gbp,signed_wage_headroom_weekly_gbp,
         revised_transfer_budget_gbp,financial_health,owner_status,
         active_event_ids_json,revenue_reported_gbp,
         verified_cash_balance_gbp,verified_net_debt_gbp,
         verified_owner_capital_injection_gbp
      FROM historical_club_circumstances WHERE edition=2027
    """).fetchall() and ((r[0],r) for r in circumstances.execute("""
      SELECT club_key,edition,preseason_as_of,source_annual_payroll_gbp,
         revised_total_wage_budget_weekly_gbp,signed_wage_headroom_weekly_gbp,
         revised_transfer_budget_gbp,financial_health,owner_status,
         active_event_ids_json,revenue_reported_gbp,
         verified_cash_balance_gbp,verified_net_debt_gbp,
         verified_owner_capital_injection_gbp
      FROM historical_club_circumstances WHERE edition=2027
    """)))
    if strict and not set(k for k,_,_,_ in clubs).issubset(profiles):
        raise ValueError("Sourced financial circumstances do not cover every FC27 club")
    observed=list(circumstances.execute("""
      SELECT event_id,club_key,event_date,category,source_authority,
             source_url,fact_text
      FROM observed_historical_events
      WHERE edition=2027 AND active_at_preseason=1 AND source_match_status='unique'
    """))
    finances={key:(payroll,headroom) for key,payroll,headroom in _open_ro(reference).execute("""
      SELECT club_key,starting_payroll_weekly_gbp,remaining_wage_headroom_weekly_gbp
      FROM wh_fc27_club_financials WHERE edition=2027
    """)}
    try:
        shutil.copy2(reference,output)
        with sqlite3.connect(output) as target:
            target.execute("PRAGMA foreign_keys=ON")
            target.executescript((Path(__file__).resolve().parent/
                                 "fc27_decision_dimensions_v1.sql").read_text())
            target.executemany("""
              INSERT INTO wh_fc27_decision_model_versions VALUES(?,?,?,?,0)
            """,[
               ("club_reputation",VERSION,
                "Source top-sixteen overall proxy and same-competition rankings; "
                "institutional historical prestige stays NULL.",
                None),
               ("club_financial_health",VERSION,
                "Historical officially observed events as of the preseason, "
                "but fiscal multiplier is only simulation; unverified cash/debt/ownership money stays NULL.",
                _digest(circumstances_db)),
               ("player_personality",VERSION,
                "Deterministic neutral-range fictional behaviour priors per source "
                "player ID, not source-observed statements about any person.",None),
               ("manager_hiring",VERSION,
                "Anonymous club recruitment preferences inferred by explicit game policy; "
                "zero sourced real manager identities, manager identities stay unknown.",None)
            ])
            games=[];circ=[];board=[];sim_agents=[]
            for key,name,comp,tier in clubs:
                r=profiles[key]
                (fkey,edition,preseason,pay,ceiling,headroom,transfer,health,
                 owner,eventids,revenue,cash,debt,injection)=r
                if (edition!=2027 or
                    (revenue,cash,debt,injection)!=(None,None,None,None)):
                    raise ValueError("Source financial overlay has unexpected invented actual money")
                if key not in finances or pay!=finances[key][0] or headroom!=ceiling-pay:
                    raise ValueError("Original wage payroll and signed overcommitment mismatch")
                if not isinstance(json.loads(eventids),list):
                    raise ValueError("Source dated event ID list malformed")
                pressure,pressure_idx=model_finance_pressure(
                    headroom=headroom,payroll=pay,distress=health)
                avg,sample=averages[key]
                appeal,source=model_sporting_appeal(avg,tier)
                rank=ranks.get(key)
                band,ambition,urgency,approach=model_club_game_plan(
                    appeal=appeal,standing_rank=rank,
                    standing_count=len(by_league[comp]),pressure_index=pressure_idx,
                    tier=tier)
                confidence=("sufficient_squad_evidence" if sample>=16
                            else "limited_squad_evidence" if sample>=8
                            else "tier_proxy_only")
                games.append((2027,key,appeal,None,avg,sample,rank,
                    len([c for c in clubs if c[2]==comp]),band,ambition,urgency,
                    approach,"derived_source_squad_game_proxy",
                    "explicit_gameplay_simulation_not_verified_board_intent",
                    "institutional_prestige_not_verified",confidence,VERSION))
                circ.append((2027,key,preseason,ceiling,pay,headroom,transfer,
                   health,pressure,pressure_idx,owner,eventids,
                   revenue,cash,debt,injection,
                   "historical-club-financial-circumstances-v2",0))
                need,style,risk,rebuild=model_manager_hiring(
                    sporting_appeal=appeal,ambition=ambition,
                    financial_pressure=pressure_idx,competitive_band=band)
                board.append((2027,key,None,"real_manager_unverified",
                    need,style,risk,rebuild,
                    "fictional_club_hiring_archetype_not_real_person",VERSION))
                # This is an ANONYMOUS fictional game coaching agent, not the
                # club's real-world manager or a claim about any human.
                generated=seed_personality("synthetic-manager-agent|"+key)
                sim_agents.append((
                    2027,"simulation-manager:2027:"+key,key,None,None,
                    "Anonymous simulated coaching agent",
                    clamp(22+.68*appeal+generated[0]*.08,15,95),
                    clamp(generated[1]+(60-appeal)*.18,15,95),
                    clamp(generated[2]+(appeal-55)*.10,15,95),
                    clamp(risk*.60+generated[3]*.40,15,95),
                    clamp(30+pressure_idx*.38+generated[4]*.15,15,95),
                    style,
                    "fictional_game_ai_agent_not_a_real_person_or_appointment",
                    VERSION
                ))
            target.executemany("""
              INSERT INTO wh_fc27_club_decision_profile VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,games)
            target.executemany("""
              INSERT INTO wh_fc27_club_financial_circumstances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,circ)
            target.executemany("""
              INSERT INTO wh_fc27_manager_recruitment_policy VALUES(?,?,?,?,?,?,?,?,?,?)
            """,board)
            target.executemany("""
              INSERT INTO wh_fc27_simulated_manager_agents
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,sim_agents)
            keys=[r[0] for r in target.execute("""
              SELECT player_key FROM wh_fc27_players WHERE edition=2027
              ORDER BY player_key
            """)]
            target.executemany("""
              INSERT INTO wh_fc27_player_game_personality
              VALUES(2027,?,?,?,?,?,?,?,NULL,?,?,?)
            """,[(k,*seed_personality(k),
                  "fictional_stable_game_seed_not_real_player_claim",
                  "unverified",VERSION) for k in keys])
            whitelist={r[0] for r in target.execute("""
              SELECT club_key FROM wh_fc27_clubs WHERE edition=2027
            """)}
            if any(ev[1] not in whitelist for ev in observed):
                raise ValueError("Financial observed event references unmapped club")
            target.executemany("""
              INSERT INTO wh_fc27_financial_evidence_events VALUES(
               2027,?,?,?,?,?,?,?,1,1,0)
            """,observed)
            target.execute("""
               UPDATE wh_fc27_coverage_gaps
               SET coverage_status='simulation_game_priors_only',
                   outstanding_reason='17,593 stable synthetic gameplay priors available; '
                    || 'zero observed real personality claims.'
               WHERE edition=2027 AND domain='player_personality'
            """)
            target.execute("""
               UPDATE wh_fc27_coverage_gaps
               SET coverage_status='board_hiring_policy_only',
                   outstanding_reason='659 simulated club board hiring templates. '
                    || 'No verified manager source IDs, appointments or actual coaching styles.'
               WHERE edition=2027 AND domain='managers'
            """)
            target.execute("""
              INSERT INTO wh_fc27_coverage_gaps(edition,domain,coverage_status,outstanding_reason)
              VALUES(2027,'club_institutional_prestige','unknown',
                '659 club sporting appeal gameplay proxies exist; independently observed institutional stature not sourced.')
            """)
            if target.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("AI reference dimension source ID foreign-key mismatch")
            if target.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("AI warehouse SQLite integrity failure")
            counts={
                "club_profiles":target.execute("SELECT COUNT(*) FROM wh_fc27_club_decision_profile").fetchone()[0],
                "club_financial_circumstances":target.execute("SELECT COUNT(*) FROM wh_fc27_club_financial_circumstances").fetchone()[0],
                "financial_source_events_as_of_preseason":target.execute("SELECT COUNT(*) FROM wh_fc27_financial_evidence_events").fetchone()[0],
                "personality_priors":target.execute("SELECT COUNT(*) FROM wh_fc27_player_game_personality").fetchone()[0],
                "real_verified_manager_profiles":target.execute("SELECT COUNT(*) FROM wh_fc27_manager_profiles").fetchone()[0],
                "fictional_manager_recruitment_policies":target.execute("SELECT COUNT(*) FROM wh_fc27_manager_recruitment_policy").fetchone()[0],
                "anonymous_simulated_manager_agent_profiles":target.execute("SELECT COUNT(*) FROM wh_fc27_simulated_manager_agents").fetchone()[0],
                "ai_club_joined_contexts":target.execute("SELECT COUNT(*) FROM wh_fc27_ai_club_decision_context").fetchone()[0],
                "financially_stressed_clubs":target.execute("""
                    SELECT COUNT(*) FROM wh_fc27_club_financial_circumstances
                    WHERE pressure_band IN ('over_committed','distress')
                """).fetchone()[0],
                "estimated_club_reputations_without_real_prestige":target.execute("""
                   SELECT COUNT(*) FROM wh_fc27_club_decision_profile
                   WHERE institutional_prestige IS NULL
                """).fetchone()[0]
            }
            if strict and (counts["club_profiles"],counts["personality_priors"],
                            counts["fictional_manager_recruitment_policies"],
                            counts["anonymous_simulated_manager_agent_profiles"],
                            counts["ai_club_joined_contexts"],
                            counts["real_verified_manager_profiles"])!=(
                                659,17593,659,659,659,0):
                raise ValueError("FC27 complete-game-dimension model coverage drift")
            target.commit()
    except Exception:
        if output.exists():output.unlink()
        raise
    finally:
        circumstances.close()
    result={
       "edition":2027,"game_model_version":VERSION,
       "frozen_prior_warehouse_sha256":_digest(reference),
       "financial_event_overlay_sha256":_digest(circumstances_db),
       "enriched_warehouse_sha256":_digest(output),
       "all_values_origin_traceable":True,
       "actual_institutional_reputation_claims":0,
       "real_personality_claims":0,
       "verified_club_cash_debt_or_owner_injection_values":0,
       "current_live_manager_appointment_claims":0,
       "PES_exports_unchanged":True,
       "production_careers_unchanged":True,
       **counts}
    output.with_suffix(".decision_audit.json").write_text(json.dumps(result,indent=2)+"\n")
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--reference",required=True)
    parser.add_argument("--circumstances",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.reference,args.circumstances,args.output),indent=2))
if __name__=="__main__":main()
