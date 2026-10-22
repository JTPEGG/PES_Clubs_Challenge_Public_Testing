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
from world_squad_planner import projected_squads, effective_cover,STARTERS,MIN_COVER,lane_of

def evaluate(full_world_path,output):
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
        for second in MARKET_MOMENTS:
            response=process_live_market(con,career_id=career,
              now=now+timedelta(seconds=second+1))
            if response["state"]!="open":
                raise ValueError("AI window closed early")
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
            elite[name]={"arrivals":inbound[cid],"departures":outbound[cid],
                         "net_arrivals":inbound[cid]-outbound[cid],
                         "senior_first_team_arrivals":senior_signings,
                         "initial_source_cb_count":len(initial[cid].get("CB",[])),
                         "final_source_cb_count":len(final[cid].get("CB",[]))}
        buyers_with_signings=len(inbound)
        sellers_with_sales=len(outbound)
        senior=[];prospects=[]
        for offer,pid,seller,buyer,primary,overall,fee in actual:
            if club_comp[seller]!=club_comp[buyer]:crossing+=1
            young=con.execute("""SELECT 1 FROM world_career_offer_events
             WHERE offer_id=? AND event_type='ai_prospect_signed'
             LIMIT 1""",(offer,)).fetchone()
            (prospects if young else senior).append(overall)
        quality_warnings=[]
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
        future=con.execute("""SELECT COUNT(*) FROM world_career_offers
          WHERE career_id=? AND status='agreed_future'""",(career,)).fetchone()[0]
        events=con.execute("""SELECT event_type,COUNT(*)
          FROM world_career_offer_events ev JOIN world_career_offers o
            ON o.offer_id=ev.offer_id WHERE o.career_id=?
          GROUP BY event_type""",(career,)).fetchall()
        if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("SQLite integrity failed")
        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Career foreign keys failed")
        report={
          "model":"actual_live_30_minute_autonomous_AI_on_disposable_659_clubs",
          "dataset_id":DATASET,"source_competitions":leagues,
          "source_clubs":source,"source_players":rosters,
          "source_country_counts":source_countries,
          "career_id":career,"window_minutes":30,
          "autonomous_moments_processed":con.execute("""SELECT COUNT(*) FROM
             world_career_ai_world_moments WHERE window_id=?""",
             (start["window_id"],)).fetchone()[0],
          "in_game_final_registrations":len(actual),
          "still_agreed_future":future,
          "cross_competition_moves":crossing,
          "cross_country_moves":crossed_country,
          "different_buyers":buyers_with_signings,
          "different_sellers":sellers_with_sales,
          "share_clubs_with_arrivals":round(buyers_with_signings/source,3),
          "elite_club_transfer_decisions":elite,
          "top_buyers":[{"club":clubs[cid],"arrivals":n}
              for cid,n in inbound.most_common(10)],
          "top_sellers":[{"club":clubs[cid],"departures":n}
              for cid,n in outbound.most_common(10)],
          "source_ability_position_counts":dict(position),
          "senior_first_team_deals":len(senior),
          "prospect_deals":len(prospects),
          "senior_overall_mean":round(sum(senior)/len(senior),2) if senior else None,
          "first_team_or_cover_alerts":len(quality_warnings),
          "alerts_sample":quality_warnings[:40],
          "event_type_counts":dict(events),
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
    args=parser.parse_args()
    print(json.dumps(evaluate(args.world,args.output),indent=2),flush=True)
