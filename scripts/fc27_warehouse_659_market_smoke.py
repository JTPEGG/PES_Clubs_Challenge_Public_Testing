"""One REAL autonomous 30-minute window on a disposable 659-club world.

Produces verified 659-club transfer and first-team audit, never writes to
original archive or existing career or deployed Render production.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path

from scripts.fc27_warehouse_world_bridge import DATASET
from world_careers import start_sandbox, wage_budget_breakdown
from world_live_market import (initialise_live_market,start_live_market,
  process_live_market,MARKET_MOMENTS)
from world_preseason_window import window_snapshot
from world_fc27_ai_recruitment import (VERSION as FC27_RECRUITMENT_VERSION,
    read_fc27_profiles)
from world_ai_tactics import preferred_formation,tactical_needs,TACTIC_VERSION
from world_squad_planner import projected_squads, effective_cover,STARTERS,MIN_COVER,lane_of,squad_standard,assign_available_players

def evaluate(full_world_path,output,*,opportunity_scale=1):
    # Scale 1 is the real source club behaviour; scale 3 amplifies every
    # individual club's propensity to scout for comparative QA, but never
    # multiplies any preset number of global transfer opportunities.
    if type(opportunity_scale) is not int or opportunity_scale not in (1,3):
        raise ValueError("Supported QA sampling is 1x or 3x")
    con=sqlite3.connect(full_world_path,isolation_level=None)
    con.row_factory=sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    career="warehouse_fc27_659_qa"
    try:
        source=con.execute("""SELECT COUNT(*) FROM world_dataset_entries
            WHERE dataset_id=?""",(DATASET,)).fetchone()[0]
        rosters=con.execute("""SELECT COUNT(*) FROM world_dataset_rosters
            WHERE dataset_id=?""",(DATASET,)).fetchone()[0]
        leagues=con.execute("""SELECT COUNT(DISTINCT competition_id)
            FROM world_dataset_entries WHERE dataset_id=?""",(DATASET,)).fetchone()[0]
        if (source,rosters,leagues)!=(659,17593,53):
            raise ValueError("Not the approved 659-club warehouse")
        ai_profiles=con.execute("""SELECT COUNT(*) FROM world_fc27_club_ai_context
            WHERE dataset_id=?""",(DATASET,)).fetchone()[0]
        if ai_profiles!=659:
            raise ValueError("Missing independently copied FC27 AI decision context")
        from world_career_transfer_protocol import initialize_transfer_protocol
        from world_career_incoming import initialize_incoming_approaches
        from world_career_management import initialize_career_management
        from world_career_objectives import initialize_board_objectives
        from world_career_board_policy import initialize_career_board_policy
        from world_career_selling import initialize_career_selling
        for setup in (initialize_career_management,initialize_board_objectives,
                      initialize_career_board_policy,initialize_career_selling,
                      initialize_incoming_approaches,initialize_transfer_protocol,
                      initialise_live_market):
            setup(con)
        # Genuine source-bound player with a complete starting club roster.
        # Avoid determining a test club by an unsourced English-name guess.
        manager=con.execute("""SELECT e.club_id FROM world_dataset_entries e
           JOIN world_dataset_rosters r ON r.dataset_id=e.dataset_id
                AND r.club_id=e.club_id
           WHERE e.dataset_id=?
           GROUP BY e.club_id HAVING COUNT(*)>=20
           ORDER BY e.club_id LIMIT 1""",(DATASET,)).fetchone()
        if manager is None:raise ValueError("No club with 20 original source players")
        # Verify full 53-competition season-end mapping separately; an
        # explicitly disposable QA career may bypass *launch readiness* only.
        start_sandbox(con,career_id=career,dataset_id=DATASET,
          title="Disposable FC27 659-club autonomous AI QA",
          manager_club_id=manager[0],pes_lock_date="2026-08-01",
          next_summer_date="2027-07-01",competition_qa_override=True)
        # Start/source money is not a substitute for real club accounts.
        initial=projected_squads(con,career_id=career,dataset=DATASET)
        if len(initial)!=659:raise ValueError("Projected club coverage incomplete")
        now=datetime.now(timezone.utc)
        start=start_live_market(con,career_id=career,now=now)
        if start["duration_seconds"]!=1800:
            raise ValueError("Incorrect preseason duration")
        for index,second in enumerate(MARKET_MOMENTS):
            due=now+timedelta(seconds=second+1)
            response=process_live_market(con,career_id=career,now=due,
                fc27_activity_scale_qa=opportunity_scale)
            if response["state"]!="open":
                raise ValueError("AI window closed early")
            print("source world AI market moment",index+1,
                  "of",len(MARKET_MOMENTS),
                  "QA opportunity scale",opportunity_scale,flush=True)
        finish=process_live_market(con,career_id=career,
           now=now+timedelta(seconds=1801))
        if finish["state"]!="closed":
            raise ValueError("AI window deadline did not finalise")
        actual=con.execute("""SELECT e.offer_id,e.player_id,e.from_club_id,
           e.to_club_id,p.primary_position,x.overall,e.fee_gbp
           FROM world_career_preseason_registration_events e
           JOIN world_players p ON p.player_id=e.player_id
           JOIN world_dataset_ratings x ON x.dataset_id=?
            AND x.player_id=e.player_id
           WHERE e.career_id=?""",(DATASET,career)).fetchall()
        if len({r[1] for r in actual})!=len(actual):
            raise ValueError("Same player registered twice")
        final=projected_squads(con,career_id=career,dataset=DATASET)
        if len(final)!=659:raise ValueError("Final roster club coverage lost")
        clubs=dict(con.execute("""SELECT e.club_id,c.name
          FROM world_dataset_entries e JOIN world_clubs c ON c.club_id=e.club_id
          WHERE e.dataset_id=?""",(DATASET,)))
        position=Counter(lane_of(r[4]) for r in actual)
        source_countries=dict(con.execute("""SELECT c.country,COUNT(*)
             FROM world_dataset_entries e JOIN world_competitions c
               ON c.competition_id=e.competition_id WHERE e.dataset_id=?
             GROUP BY c.country""",(DATASET,)))
        crossing=0;club_comp=dict(con.execute("""SELECT e.club_id,c.competition_id
          FROM world_dataset_entries e JOIN world_competitions c
            ON c.competition_id=e.competition_id WHERE e.dataset_id=?""",
            (DATASET,)))
        club_country=dict(con.execute("""SELECT e.club_id,c.country
          FROM world_dataset_entries e JOIN world_competitions c
            ON c.competition_id=e.competition_id WHERE e.dataset_id=?""",
            (DATASET,)))
        inbound=Counter(r[3] for r in actual)
        outbound=Counter(r[2] for r in actual)
        crossed_country=sum(club_country[r[2]]!=club_country[r[3]]
                            for r in actual)
        buyer_countries=Counter(club_country[r[3]] for r in actual)
        seller_countries=Counter(club_country[r[2]] for r in actual)
        corridors=Counter((club_country[r[2]],club_country[r[3]])
                          for r in actual)
        profiles=read_fc27_profiles(con,dataset=DATASET)
        tactics={cid:preferred_formation(club_id=cid,profile=profile)
                 for cid,profile in profiles.items()}
        formation_counts=dict(Counter(tactics.values()))
        elite={}
        for name in ("Arsenal","Chelsea","Manchester City"):
            candidates=[cid for cid,display in clubs.items()
                        if display.startswith(name+" [WH27:")]
            if len(candidates)!=1:
                raise ValueError("FC27 reviewed elite source club key is ambiguous: "+name)
            cid=candidates[0]
            senior_signings=sum(r[3]==cid and not con.execute("""
                SELECT 1 FROM world_career_offer_events
                WHERE offer_id=? AND event_type='ai_prospect_signed' LIMIT 1
            """,(r[0],)).fetchone() for r in actual)
            # A zero-signing club can be ignored by candidate selection,
            # rejected by sellers or blocked by personal terms. Preserve
            # this evidence rather than declaring all three "no interest".
            attempted=dict(con.execute("""SELECT status,COUNT(*)
                FROM world_career_offers WHERE career_id=?
                AND buying_club_id=? GROUP BY status""",
                (career,cid)).fetchall())
            elite[name]={"modelled_preferred_formation":tactics[cid],
                         "attempted_offers":sum(attempted.values()),
                         "attempted_offer_statuses":attempted,
                         "arrivals":inbound[cid],"departures":outbound[cid],
                         "net_arrivals":inbound[cid]-outbound[cid],
                         "senior_first_team_arrivals":senior_signings,
                         "initial_source_cb_count":len(initial[cid].get("CB",[])),
                         "final_source_cb_count":len(final[cid].get("CB",[]))}
        # Actual FC27 decision-chain audit: eligible clubs -> scouts ->
        # negotiation -> seller/player/agent -> completed deal.
        # This is not a country preference or a newly generated offer.
        evaluation_stages=dict(con.execute("""
            SELECT stage,COUNT(*) FROM world_fc27_market_club_evaluations
            WHERE window_id=? GROUP BY stage""",
            (start["window_id"],)).fetchall())
        negotiation_stages=dict(con.execute("""
            SELECT result_stage,COUNT(*) FROM
              world_fc27_market_negotiation_diagnostics
            WHERE window_id=? GROUP BY result_stage""",
            (start["window_id"],)).fetchall())
        country_pool=con.execute("""SELECT
            COALESCE(SUM(eligible_candidates),0),
            COALESCE(SUM(same_country_candidates),0),
            COALESCE(SUM(foreign_country_candidates),0),
            COALESCE(SUM(affordable_same_country),0),
            COALESCE(SUM(affordable_foreign_country),0)
            FROM world_fc27_market_negotiation_diagnostics
            WHERE window_id=? AND result_stage!='no_eligible_target'""",
            (start["window_id"],)).fetchone()
        elite_funnels={}
        for name in ("Arsenal","Chelsea","Manchester City"):
            matches=[cid for cid,display in clubs.items()
                     if display.startswith(name+" [WH27:")]
            if len(matches)!=1:raise ValueError("Unmapped elite QA club "+name)
            cid=matches[0]
            selections=dict(con.execute("""SELECT stage,COUNT(*)
                FROM world_fc27_market_club_evaluations
                WHERE window_id=? AND club_id=? GROUP BY stage""",
                (start["window_id"],cid)).fetchall())
            negotiation=dict(con.execute("""SELECT result_stage,COUNT(*)
                FROM world_fc27_market_negotiation_diagnostics
                WHERE window_id=? AND club_id=? GROUP BY result_stage""",
                (start["window_id"],cid)).fetchall())
            rows=con.execute("""SELECT d.interval_index,d.search_family,
                d.search_strategy,d.eligible_candidates,
                d.same_country_candidates,d.foreign_country_candidates,
                d.result_stage,d.reason,d.first_eligible_player_id,
                d.chosen_player_id,d.selected_source_country,
                d.contract_phase,d.buyer_offer_fee_gbp,
                d.seller_counter_fee_gbp,d.buyer_sensible_ceiling_gbp,
                d.promised_role,d.player_interest_signal,
                d.player_required_role,d.source_player_wage_gbp,
                d.agent_initial_demand_gbp,d.agent_final_demand_gbp,
                d.buyer_remaining_wage_gbp,
                d.affordable_same_country,d.affordable_foreign_country
                FROM world_fc27_market_negotiation_diagnostics d
                WHERE d.window_id=? AND d.club_id=?
                ORDER BY d.interval_index""",
                (start["window_id"],cid)).fetchall()
            elite_funnels[name]={
                "evaluations":selections,
                "negotiation_outcomes":negotiation,
                "searches":[{
                    "interval":v[0]+1,"position_family":v[1],
                    "search_strategy":v[2],
                    "eligible_targets":v[3],
                    "eligible_same_country":v[4],
                    "eligible_in_other_countries":v[5],
                    "outcome":v[6],
                    "reason":v[7],
                    "top_ranked_player_id":v[8],
                    "negotiated_player_id":v[9],
                    "negotiated_source_country":v[10],
                    "last_negotiation_phase":v[11],
                    "offered_fee_gbp":v[12],
                    "seller_counter_fee_gbp":v[13],
                    "buyer_sensible_fee_ceiling_gbp":v[14],
                    "role_promised":v[15],"player_signal":v[16],
                    "player_required_role":v[17],
                    "source_game_wage_gbp":v[18],
                    "first_agent_wage_demand_gbp":v[19],
                    "final_agreed_or_demanded_wage_gbp":v[20],
                    "buyer_remaining_weekly_wage_headroom_gbp":v[21],
                    "plausible_same_country_targets":v[22],
                    "plausible_overseas_targets":v[23],
                } for v in rows]}
        buyers_with_signings=len(inbound)
        sellers_with_sales=len(outbound)
        active_clubs=len(set(inbound)|set(outbound))
        buyer_quality_change={cid:round(squad_standard(final[cid])-
                                         squad_standard(initial[cid]),2)
                              for cid in initial}
        senior=[];prospects=[]
        for offer,pid,seller,buyer,primary,overall,fee in actual:
            if club_comp[seller]!=club_comp[buyer]:crossing+=1
            young=con.execute("""SELECT 1 FROM world_career_offer_events
             WHERE offer_id=? AND event_type='ai_prospect_signed'
             LIMIT 1""",(offer,)).fetchone()
            (prospects if young else senior).append(overall)
        quality_warnings=[]
        formation_warnings=[]
        tactical_quality_warnings=[]
        for club in initial:
            for lane in MIN_COVER:
                before=effective_cover(initial,club,lane)
                after=effective_cover(final,club,lane)
                if not before and not after:continue
                n=STARTERS[lane]
                old=round(sum(x[1] for x in before[:n])/len(before[:n]),2) if before else 0
                new=round(sum(x[1] for x in after[:n])/len(after[:n]),2) if after else 0
                if len(after)<max(STARTERS[lane],MIN_COVER[lane])<=len(before) or old-new>=3:
                    quality_warnings.append({"club":clubs[club],"lane":lane,
                       "starter_quality_old":old,"starter_quality_new":new,
                       "source_rated_cover_before":len(before),
                       "source_rated_cover_after":len(after)})
        # Source roster may have positions that this modelled coach does
        # not use. An LM leaving a 4-3-3 team is not automatically a hole in
        # its starting XI. Audit the ENTIRE tactical assignment separately.
        for club in initial:
            requested=tactical_needs(tactics[club])["starting_roles"]
            original=assign_available_players(initial,club,requested)
            updated=assign_available_players(final,club,requested)
            if updated["filled"]<original["filled"]:
                formation_warnings.append({
                    "club":clubs[club],"formation":tactics[club],
                    "source_tactical_xi_covered_before":original["filled"],
                    "source_tactical_xi_covered_after":updated["filled"],
                    "source_tactical_xi_slots":11})
            old_ratings={pid:ovr for lane in initial[club].values()
                         for pid,ovr,_pos in lane}
            new_ratings={pid:ovr for lane in final[club].values()
                         for pid,ovr,_pos in lane}
            # Do not confuse "eleven places filled" with a strong eleven.
            # Rates are from actual source overall and the matching
            # assignments; the same footballer cannot fill two positions.
            old_strength=sum(old_ratings[a["player_id"]]
                             for a in original["assignments"])/11
            new_strength=sum(new_ratings[a["player_id"]]
                             for a in updated["assignments"])/11
            if old_strength-new_strength>=1.5:
                tactical_quality_warnings.append({
                    "club":clubs[club],"formation":tactics[club],
                    "initial_tactical_xi_avg_rating":round(old_strength,2),
                    "final_tactical_xi_avg_rating":round(new_strength,2),
                    "avg_rating_loss":round(old_strength-new_strength,2),
                    "initial_filled":original["filled"],
                    "final_filled":updated["filled"]})
        future=con.execute("""SELECT COUNT(*) FROM world_career_offers
          WHERE career_id=? AND status='agreed_future'""",(career,)).fetchone()[0]
        activity=con.execute("""SELECT COALESCE(SUM(eligible_clubs),0),
            COALESCE(SUM(active_clubs),0),COUNT(*) FROM
            world_fc27_market_intervals WHERE window_id=?""",
            (start["window_id"],)).fetchone()
        club_activity=con.execute("""SELECT COUNT(DISTINCT club_id) FROM
            world_fc27_market_club_intents WHERE window_id=?""",
            (start["window_id"],)).fetchone()[0]
        recorded_activities=con.execute("""SELECT COUNT(*) FROM
            world_fc27_market_club_intents WHERE window_id=? AND
            processed=1""",(start["window_id"],)).fetchone()[0]
        events=con.execute("""SELECT event_type,COUNT(*)
          FROM world_career_offer_events ev JOIN world_career_offers o
            ON o.offer_id=ev.offer_id WHERE o.career_id=?
          GROUP BY event_type""",(career,)).fetchall()
        # Full audit of actual completed registrations, never unsourced
        # expected business or fictional contracts presented as source facts.
        deal_cases={offer:category for offer,category in con.execute("""
            SELECT o.offer_id,e.event_type FROM world_career_offer_events e
            JOIN world_career_offers o ON o.offer_id=e.offer_id
            WHERE o.career_id=? AND e.event_type IN
              ('ai_seller_covered_sale','ai_seller_recruitment_required',
               'ai_seller_surplus_sale')""",(career,))}
        prospect_ids={r[0] for r in con.execute("""
            SELECT o.offer_id FROM world_career_offer_events e
            JOIN world_career_offers o ON o.offer_id=e.offer_id
            WHERE o.career_id=? AND e.event_type='ai_prospect_signed'
            """,(career,))}
        player_names=dict(con.execute("SELECT player_id,full_name FROM world_players"))
        source_game_wages=dict(con.execute("""SELECT player_id,weekly_wage_gbp
            FROM world_dataset_contract_snapshots WHERE dataset_id=?""",
            (DATASET,)).fetchall())
        three_season_cases={
            oid:json.loads(detail) for oid,detail in con.execute("""
                SELECT o.offer_id,e.detail FROM world_career_offer_events e
                JOIN world_career_offers o ON o.offer_id=e.offer_id
                WHERE o.career_id=?
                AND e.event_type='ai_fc27_three_season_recruitment'""",
                (career,)).fetchall()}
        final_seller_cases={
            oid:json.loads(detail) for oid,detail in con.execute("""
                SELECT o.offer_id,e.detail FROM world_career_offer_events e
                JOIN world_career_offers o ON o.offer_id=e.offer_id
                WHERE o.career_id=?
                AND e.event_type='ai_fc27_final_seller_rationale'""",
                (career,)).fetchall()}
        signed_contract_wages=dict(con.execute("""SELECT offer_id,
            offered_wage_weekly FROM world_career_offers
            WHERE career_id=? AND status='completed'""",
            (career,)).fetchall())
        senior_rotation_offers={r[0] for r in con.execute("""SELECT o.offer_id
            FROM world_career_offers o
            JOIN world_career_offer_events e ON e.offer_id=o.offer_id
            WHERE o.career_id=? AND e.event_type='ai_fc27_senior_rotation_signed'
            """,(career,))}
        source_wage_shortfalls=[]
        ai_club_rows={row[0]:{"financial_pressure_band":row[1],
                             "ambition_level":row[2]}
            for row in con.execute("""SELECT club_id,financial_pressure_band,
                ambition_level FROM world_fc27_club_ai_context
                WHERE dataset_id=?""",(DATASET,))}
        transfers=[{
            "player":player_names[pid],
            "source_overall":overall,"source_position":primary,
            "source_seller":clubs[seller],"source_buyer":clubs[buyer],
            "source_seller_country":club_country[seller],
            "source_buyer_country":club_country[buyer],
            "agreed_fee_gbp":fee,
            "source_game_weekly_wage_gbp":source_game_wages.get(pid),
            "accepted_simulated_weekly_wage_gbp":signed_contract_wages.get(offer),
            "simulated_recruitment_type":(
                "prospect" if offer in prospect_ids else
                "senior_rotation_or_replacement"
                if offer in senior_rotation_offers else "senior_first_team_upgrade"),
            "simulated_seller_squad_case":deal_cases.get(offer,"unclassified"),
            "three_season_recruitment_plan":three_season_cases.get(offer),
            "selling_club_three_season_strategy":(
                (final_seller_cases.get(offer,{}).get("tactical_impact") or
                 {}).get("three_season_strategy")),
            "seller_final_board_decision":(
                final_seller_cases.get(offer,{ }).get("board_decision")),
            "seller_modelled_financial_state":(
                final_seller_cases.get(offer,{ }).get("seller_financial_state")),
            "seller_tactical_quality_loss_at_approval":(
                (final_seller_cases.get(offer,{ }).get("tactical_impact") or
                  {}).get("formation_quality_loss")),
            "modelled_buyer_context":ai_club_rows.get(buyer),
            "modelled_seller_context":ai_club_rows.get(seller),
            "source_top11_strength_change_buyer":buyer_quality_change[buyer],
            "source_top11_strength_change_seller":buyer_quality_change[seller],
            "provenance":"Source FC27 player/club/OVR; fee, interests, club pressure and transfer are GAME SIMULATION, not historical facts"
        } for offer,pid,seller,buyer,primary,overall,fee in actual]
        source_wage_shortfalls=[
            {"player":item["player"],
             "source_weekly_wage_gbp":item["source_game_weekly_wage_gbp"],
             "accepted_weekly_wage_gbp":item["accepted_simulated_weekly_wage_gbp"]}
            for item in transfers
            if (item["source_game_weekly_wage_gbp"] is not None and
                item["source_game_weekly_wage_gbp"]>=1000 and
                item["accepted_simulated_weekly_wage_gbp"] is not None and
                item["accepted_simulated_weekly_wage_gbp"]<
                    .9*item["source_game_weekly_wage_gbp"])]
        # Original prospect_fit classification remains authoritative.
        # Three-season strategy must not turn youth into current XI signings.
        strategy_prospect_mismatches=[
            item["player"] for item in transfers
            if item["three_season_recruitment_plan"] is None or
               (item["three_season_recruitment_plan"]["recruitment_category"]
                == "prospect") != (
                 item["simulated_recruitment_type"]=="prospect")]
        # Full reason chain for outcomes with meaningful final squad loss.
        # One completed deal is NOT necessarily solely responsible for a
        # whole-window club result: show both its recorded individual cost
        # and the final source-rated aggregate.
        significant_seller_cases=[
            {"player":t["player"],"seller":t["source_seller"],
             "buyer":t["source_buyer"],
             "fee_gbp":t["agreed_fee_gbp"],
             "final_club_top11_rating_change":
                 t["source_top11_strength_change_seller"],
             "seller_decision":final_seller_cases.get(
                 next(oid for oid,pid,se,bu,pos,ov,fee in actual
                      if player_names[pid]==t["player"] and
                         clubs[se]==t["source_seller"] and
                         clubs[bu]==t["source_buyer"]),{} )}
            for t in transfers
            if t["source_top11_strength_change_seller"]<=-.75
        ]
        if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("SQLite integrity failed")
        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Career foreign keys failed")
        report={
          "model":"actual_live_30_minute_autonomous_AI_on_disposable_659_clubs",
          "fc27_context_recruitment_version":FC27_RECRUITMENT_VERSION,
          "dataset_id":DATASET,"source_competitions":leagues,
          "source_clubs":source,"source_players":rosters,
          "modelled_ai_club_contexts_copied":ai_profiles,
          "modelled_manager_tactics_version":TACTIC_VERSION,
          "modelled_tactical_formation_distribution":formation_counts,
          "source_country_counts":source_countries,
          "career_id":career,"window_minutes":30,
          "opportunity_scale_QA_only":opportunity_scale,
          "extra_QA_opportunities_not_forced_transfers":True,
          "fc27_independent_club_market":True,
          "eligible_independent_club_decisions":activity[0],
          "club_led_negotiation_intents":activity[1],
          "club_decision_funnel_stages":evaluation_stages,
          "club_negotiation_funnel_stages":negotiation_stages,
          "eligible_target_country_pool":{
              "all_eligible_target_screenings":country_pool[0],
              "same_country_candidates":country_pool[1],
              "cross_country_candidates":country_pool[2],
              "budget_plausible_same_country_candidates":country_pool[3],
              "budget_plausible_cross_country_candidates":country_pool[4],
              "budget_plausible_candidates":country_pool[3]+country_pool[4],
              "cross_country_share_of_eligible_shortlists":(
                  round(country_pool[2]/(country_pool[1]+country_pool[2]),4)
                  if country_pool[1]+country_pool[2] else None)},
          "elite_club_decision_chains":elite_funnels,
          "independent_intervals_reconciled":activity[2],
          "distinct_clubs_with_negotiation_intent":club_activity,
          "persisted_club_intents_processed":recorded_activities,
          "autonomous_moments_processed":con.execute("""SELECT COUNT(*) FROM
             world_career_ai_world_moments WHERE window_id=?""",
             (start["window_id"],)).fetchone()[0],
          "in_game_final_registrations":len(actual),
          "still_agreed_future":future,
          "cross_competition_moves":crossing,
          "cross_country_moves":crossed_country,
          "domestic_same_source_country_moves":len(actual)-crossed_country,
          "international_source_country_share":(
              round(crossed_country/len(actual),3) if actual else None),
          "buyer_countries_active":dict(buyer_countries),
          "seller_countries_active":dict(seller_countries),
          "top_source_country_corridors":[
              {"seller_country":origin,"buyer_country":destination,"deals":n}
              for (origin,destination),n in corridors.most_common(20)],
          "different_clubs_buying_or_selling":active_clubs,
          "share_clubs_active":round(active_clubs/source,3),
          "clubs_with_source_top11_strength_gain_over_1":sum(
              val>1 for val in buyer_quality_change.values()),
          "clubs_with_source_top11_strength_loss_over_1":sum(
              val< -1 for val in buyer_quality_change.values()),
          "different_buyers":buyers_with_signings,
          "different_sellers":sellers_with_sales,
          "share_clubs_with_arrivals":round(buyers_with_signings/source,3),
          "elite_club_transfer_decisions":elite,
          "top_buyers":[{"club":clubs[cid],"arrivals":n}
              for cid,n in inbound.most_common(10)],
          "top_sellers":[{"club":clubs[cid],"departures":n}
              for cid,n in outbound.most_common(10)],
          "source_ability_position_counts":dict(position),
          "important_seller_case_studies":significant_seller_cases[:50],
          "three_season_recruitment_cases_audited":len(three_season_cases),
          "three_season_prospect_classification_errors":
              strategy_prospect_mismatches,
          "three_season_prospects_signed_unchanged":sum(
              t["simulated_recruitment_type"]=="prospect"
              and t["three_season_recruitment_plan"] is not None
              for t in transfers),
          "three_season_seller_cases_with_source_context":sum(
              t["selling_club_three_season_strategy"] is not None
              for t in transfers),
          "seller_approval_rationales_recorded":len(final_seller_cases),
          "senior_first_team_deals":len(senior),
          "senior_confirmed_xi_upgrades":len(senior)-len(senior_rotation_offers),
          "senior_rotation_or_replacement_deals":len(senior_rotation_offers),
          "source_wage_large_drops":len(source_wage_shortfalls),
          "source_wage_large_drop_examples":source_wage_shortfalls[:30],
          "prospect_deals":len(prospects),
          "senior_overall_mean":round(sum(senior)/len(senior),2) if senior else None,
          "first_team_or_cover_alerts":len(quality_warnings),
          "alerts_sample":quality_warnings[:40],
          "tactical_xi_coverage_alerts":len(formation_warnings),
          "tactical_xi_coverage_samples":formation_warnings[:40],
          "tactical_xi_quality_alerts":len(tactical_quality_warnings),
          "tactical_xi_quality_samples":tactical_quality_warnings[:40],
          "event_type_counts":dict(events),
          "actual_transfer_details":transfers,
          "player_registration_reconciled":True,
          "no_PES_export":True,"no_production_career_modified":True,
          "actual_complete_20_window_comparison_not_yet_run":True
        }
        out=Path(output)
        out.parent.mkdir(parents=True,exist_ok=True)
        if out.exists():raise FileExistsError("Refuse to overwrite prior QA audit")
        out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        return report
    finally:con.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--world",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--opportunity-scale",type=int,default=1,
                        choices=(1,3))
    args=parser.parse_args()
    print(json.dumps(evaluate(args.world,args.output,
       opportunity_scale=args.opportunity_scale),indent=2),flush=True)
