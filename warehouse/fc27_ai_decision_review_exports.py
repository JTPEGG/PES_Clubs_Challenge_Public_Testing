"""Human-reviewable FC27 AI decision model snapshots, explicitly labelled estimates.

These CSVs are diagnostics, not evidence that real football personalities,
prestige or manager appointments have been independently verified.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from pathlib import Path

def save_csv(folder,name,fields,rows):
    with (folder/name).open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.writer(f)
        writer.writerow(fields)
        writer.writerows(rows)

def export(source_path,outdir):
    source=Path(source_path).resolve()
    folder=Path(outdir);folder.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f"file:{source.as_posix()}?mode=ro",uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        club=db.execute("""
          SELECT c.name,c.competition_code,c.career_scope,
             d.sporting_appeal,d.institutional_prestige,
             d.squad_top16_source_overall_avg,d.sampled_overall_players,
             d.league_squad_strength_rank,d.league_club_count,
             d.expected_competitive_band,d.ambition_level,
             d.pressure_to_improve,d.operating_approach,d.confidence,
             d.game_reputation_origin,d.ambition_origin
          FROM wh_fc27_clubs c JOIN wh_fc27_club_decision_profile d
            ON d.edition=c.edition AND d.club_key=c.club_key
          WHERE c.edition=2027 ORDER BY c.competition_code,d.sporting_appeal DESC,c.name
        """).fetchall()
        save_csv(folder,"FC27_CLUB_SPORTING_APPEAL_AND_AMBITION_GAME_MODEL.csv",
          ("Club","Competition","Career_Scope","Sporting_Appeal_GAME_PROXY",
           "Verified_Institutional_Prestige_UNKNOWN","Top16_Source_Overall",
           "Players_Rated","Source_Squad_Rank_In_Competition",
           "Competition_Clubs","Expected_Game_Competitive_Band",
           "Ambition_GAME_ESTIMATE","Pressure_To_Improve_GAME_ESTIMATE",
           "Operating_Approach_GAME_POLICY","Quality_Flag",
           "Reputation_Provenance","Ambition_Provenance"),club)
        finance=db.execute("""
          SELECT c.name,c.competition_code,
            f.model_weekly_wage_ceiling_gbp,f.committed_payroll_weekly_gbp,
            f.signed_wage_headroom_weekly_gbp,f.model_transfer_allowance_gbp,
            f.financial_health,f.pressure_band,f.pressure_index,
            f.ownership_status,f.active_evidence_event_ids_json,
            f.verified_revenue_gbp,f.verified_cash_balance_gbp,
            f.verified_net_debt_gbp,f.verified_owner_capital_injection_gbp,
            f.model_source
          FROM wh_fc27_clubs c JOIN wh_fc27_club_financial_circumstances f
            ON f.edition=c.edition AND f.club_key=c.club_key
          WHERE c.edition=2027 ORDER BY f.pressure_index DESC,c.name
        """).fetchall()
        save_csv(folder,"FC27_CLUB_FINANCIAL_PRESSURE_SOURCE_VS_MODEL.csv",
         ("Club","Competition","Wage_Ceiling_GAME_MODEL_GBPpw",
          "Committed_Payroll_MODEL_GBPpw","Signed_Wage_Headroom_GAME_MODEL_GBPpw",
          "Transfer_Allowance_GAME_MODEL_GBP","Financial_Status_GAME_MODEL",
          "Pressure_Band_GAME_MODEL","Pressure_Index_GAME_MODEL",
          "Ownership_Source_Status","Confirmed_Preseason_Source_Event_IDs",
          "Verified_Revenue_UNKNOWN_GBP","Verified_Cash_UNKNOWN_GBP",
          "Verified_Net_Debt_UNKNOWN_GBP",
          "Verified_Owner_Investment_UNKNOWN_GBP","Model_Provenance"),finance)
        coaches=db.execute("""
          SELECT c.name,s.game_manager_key,s.display_role,
                 s.real_manager_name,s.game_coaching_ability,
                 s.youth_development_bias,s.tactical_flexibility,
                 s.recruitment_risk_appetite,s.financial_discipline,s.playing_style,
                 b.required_manager_reputation,b.preferred_game_management_style,
                 s.provenance
          FROM wh_fc27_simulated_manager_agents s
          JOIN wh_fc27_clubs c ON c.edition=s.edition AND c.club_key=s.starting_club_key
          JOIN wh_fc27_manager_recruitment_policy b
            ON b.edition=s.edition AND b.club_key=s.starting_club_key
          ORDER BY c.name
        """).fetchall()
        save_csv(folder,"FC27_ANONYMOUS_SIMULATED_MANAGER_PROFILES.csv",
         ("Club","Simulation_Only_Manager_Key","Display_Role",
          "Real_Manager_Name_UNKNOWN","Coaching_Ability_GAME_ONLY",
          "Youth_Development_Bias_GAME_ONLY","Tactical_Flexibility_GAME_ONLY",
          "Recruitment_Risk_Appetite_GAME_ONLY","Financial_Discipline_GAME_ONLY",
          "Fictional_Tactical_Preference","Board_Min_Manager_Reputation_GAME_RULE",
          "Board_Fictional_Preferred_Style","Model_Provenance"),coaches)
        players=db.execute("""
          SELECT p.player_key,p.name,
            x.ambition_prior,x.loyalty_prior,x.professionalism_prior,
            x.temperament_prior,x.adaptability_prior,x.wage_motivation_prior,
            x.observed_real_personality_json,x.origin
          FROM wh_fc27_player_game_personality x
          JOIN wh_fc27_players p ON p.edition=x.edition AND p.player_key=x.player_key
          ORDER BY p.player_key
        """).fetchall()
        save_csv(folder,"FC27_PLAYER_PERSONALITY_FICTIONAL_GAME_PRIORS.csv",
         ("Source_Player_Key","Player_Name",
          "Ambition_Fictional_Game_Seed","Loyalty_Fictional_Game_Seed",
          "Professionalism_Fictional_Game_Seed","Temperament_Fictional_Game_Seed",
          "Adaptability_Fictional_Game_Seed","Wage_Motivation_Fictional_Game_Seed",
          "Verified_Real_Personality_UNKNOWN","Model_Provenance"),players)
        evidence=db.execute("""
          SELECT e.event_id,c.name,e.event_date,e.event_category,
            e.source_authority,e.source_url,e.observed_fact
          FROM wh_fc27_financial_evidence_events e
          JOIN wh_fc27_clubs c ON c.edition=e.edition AND c.club_key=e.club_key
          ORDER BY e.event_date,e.event_id
        """).fetchall()
        save_csv(folder,"FC27_VERIFIED_AS_OF_PRESEASON_FINANCIAL_EVENTS.csv",
         ("Original_Source_Event_ID","Club","Date","Category",
          "Source_Authority","Published_Url","Observed_Fact"),evidence)
    result={
      "league_and_club_game_profiles":len(club),
      "club_financial_circumstances":len(finance),
      "fictional_anonymous_manager_agents":len(coaches),
      "fictional_player_personality_game_priors":len(players),
      "real_sourced_preseason_club_events":len(evidence),
      "unknown_real_manager_names":sum(r[3] is None for r in coaches),
      "unknown_verified_institutional_prestige":sum(r[4] is None for r in club),
      "unknown_real_personalities":sum(r[-2] is None for r in players),
      "no_individual_real_cash_or_ownership_amounts_claimed":True,
      "no_PES_or_live_career_mutation":True
    }
    (folder/"FC27_AI_REFERENCE_REVIEW_COUNTS.json").write_text(
        json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    print(json.dumps(export(args.source,args.output),indent=2))
if __name__=="__main__":main()
