"""Evidence-gated historical club finances V2 overlay.

Builds next to (never updates) the approved 13,104-club wage/transfer V1.
Observed facts: dated official sporting, takeover and distress events.
Simulated consequences: independently versioned and reversible multipliers.
Critically, the wage ceiling MAY be less than already-committed wages.
No unverifiable revenue, debt, account balance or investor contribution is
invented; such monetary fields stay NULL pending financial filings.
"""
from __future__ import annotations

import argparse,csv,hashlib,json,sqlite3
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path

VERSION="historical-club-financial-circumstances-v2"
EVENT_CATEGORIES={"promotion","relegation","ownership_change","financial_distress"}
CLUB_ALIASES={
 "afcbournemouth":"bournemouth","bournemouth":"bournemouth",
 "wolverhamptonwanderers":"wolves","wolves":"wolves",
 "sheffieldunited":"sheffieldutd","sheffieldutd":"sheffieldutd",
 "westhamunited":"westham","westham":"westham",
 "newcastleunited":"newcastleutd","newcastleutd":"newcastleutd",
 "westbromwichalbion":"westbrom","westbrom":"westbrom",
 "nottinghamforest":"nottmforest","nottmforest":"nottmforest",
 "leicestercity":"leicester","leicester":"leicester",
 "lutontown":"luton","luton":"luton",
 "ipswichtown":"ipswich","ipswich":"ipswich",
 "coventrycity":"coventry","coventry":"coventry",
 "hullcity":"hull","hull":"hull",
 "norwichcity":"norwich","norwich":"norwich",
 "readingfc":"reading","reading":"reading",
 "manchestercity":"mancity","mancity":"mancity",
 "southamptonfc":"southampton","southampton":"southampton",
 "burnleyfc":"burnley","burnley":"burnley",
 "wig an athletic":"wiganathletic",
}
def norm(text):
    import unicodedata
    value="".join(c for c in unicodedata.normalize("NFKD",str(text or "")).casefold()
                  if c.isascii() and c.isalnum())
    return CLUB_ALIASES.get(value,value)


def preseason_date(edition):
    # 2020/21 English season started in September owing to pandemic.
    return date(2020,9,1) if edition==2021 else date(edition-1,8,1)


def load_evidence(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("scope")!="mens_only":raise ValueError("Men-only sources required")
    ids=set();events=[]
    for e in data["events"]:
        if e["id"] in ids:raise ValueError("Duplicate evidence id")
        ids.add(e["id"])
        if e["event_type"] not in EVENT_CATEGORIES:raise ValueError("Unknown event type")
        d=date.fromisoformat(e["event_date"])
        year=int(e["edition"])
        if not 2005<=year<=2027 or year==2025 and e["event_type"]!="ownership_change":
            # FC25 is not in the source archive, but real-world events can
            # still be stored, never forced into a neighbouring FIFA edition.
            pass
        if not e["source_url"].startswith("https://"):raise ValueError("Evidence needs URL")
        if not norm(e["club"]):raise ValueError("Event needs club")
        if e.get("verified_financial_amount_gbp") is not None:
            raise ValueError("Current sporting/event catalogue has NO verified investment amount")
        events.append({**e,"date":d,"normal":norm(e["club"])})
    return events


def impact(effective_events, *, base_wage_budget, base_transfer_budget, pay):
    """Policy factors, NEVER verified real-world changes.

    Ownership announcement changes governance uncertainty/status, but grants
    £0 of proven investment: no automatic free money. Further measured
    investment must enter as a separately verified financial observation.
    """
    types={e["event_type"] for e in effective_events}
    salary_factor=1.0
    transfer_factor=1.0
    if "promotion" in types:
        salary_factor*=1.18
        transfer_factor*=1.45
    if "relegation" in types:
        salary_factor*=.70
        transfer_factor*=.42
    if "financial_distress" in types:
        salary_factor*=.60
        transfer_factor=0.
    ceiling=max(0,round(base_wage_budget*salary_factor/50)*50)
    allowance=max(0,round(base_transfer_budget*transfer_factor/1000)*1000)
    health=("documented_distress" if "financial_distress" in types
            else "model_wages_over_budget" if pay>ceiling
            else "unverified")
    return ceiling,ceiling-pay,allowance,health


SCHEMA="""
CREATE TABLE IF NOT EXISTS circumstance_release(
 model_version TEXT PRIMARY KEY,original_finance_sha256 TEXT NOT NULL,
 events_sha256 TEXT NOT NULL,source_club_count INTEGER NOT NULL,
 observed_revenue_coverage INTEGER NOT NULL,
 policy TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observed_historical_events(
 event_id TEXT PRIMARY KEY,
 edition INTEGER NOT NULL,club_key TEXT,
 stated_club_name TEXT NOT NULL,category TEXT NOT NULL,event_date TEXT NOT NULL,
 source_authority TEXT NOT NULL,source_url TEXT NOT NULL,
 fact_text TEXT NOT NULL,
 source_match_status TEXT NOT NULL,
 active_at_preseason INTEGER NOT NULL CHECK(active_at_preseason IN (0,1)),
 game_effect_policy TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS historical_club_circumstances(
 club_key TEXT PRIMARY KEY,
 edition INTEGER NOT NULL,
 club_name TEXT NOT NULL,
 preseason_as_of TEXT NOT NULL,
 source_annual_payroll_gbp INTEGER NOT NULL,
 prior_model_wage_budget_weekly_gbp INTEGER NOT NULL,
 prior_model_transfer_budget_gbp INTEGER NOT NULL,
 revised_total_wage_budget_weekly_gbp INTEGER NOT NULL,
 signed_wage_headroom_weekly_gbp INTEGER NOT NULL,
 revised_transfer_budget_gbp INTEGER NOT NULL,
 transfer_budget_change_gbp INTEGER NOT NULL,
 revenue_reported_gbp INTEGER,
 reported_financial_year INTEGER,
 verified_cash_balance_gbp INTEGER,
 verified_net_debt_gbp INTEGER,
 verified_owner_capital_injection_gbp INTEGER,
 owner_status TEXT NOT NULL,
 financial_health TEXT NOT NULL,
 active_event_ids_json TEXT NOT NULL,
 finance_evidence_status TEXT NOT NULL,
 source_spending_policy TEXT NOT NULL,
 notes TEXT NOT NULL,
 CHECK(revised_total_wage_budget_weekly_gbp>=0),
 CHECK(revised_transfer_budget_gbp>=0),
 CHECK(signed_wage_headroom_weekly_gbp=
       revised_total_wage_budget_weekly_gbp-source_annual_payroll_gbp)
);
CREATE INDEX IF NOT EXISTS hcc_ed ON historical_club_circumstances(edition);
CREATE INDEX IF NOT EXISTS he_ed ON observed_historical_events(edition);
"""
HEADERS=("Edition","Club","Source_Club_Key","As_Of",
 "Current_Payroll_Weekly_GBP","Previous_Wage_Budget_Weekly_GBP",
 "Revised_Total_Wage_Budget_Weekly_GBP","SIGNED_Wage_Headroom_Weekly_GBP",
 "Previous_Transfer_Budget_GBP","Revised_Transfer_Budget_GBP",
 "Change_In_Transfer_Budget_GBP","Financial_Health_Status",
 "Owner_Status","Active_Evidence_Event_IDs","Verified_Revenue_GBP",
 "Verified_Cash_GBP","Verified_Net_Debt_GBP",
 "Finance_Evidence","Budget_Status","Explanation")

def build(finances_db,evidence_file,outdir):
    out=Path(outdir)
    out.mkdir(parents=True,exist_ok=True)
    target=out/"PES_V2_CLUB_FINANCIAL_CIRCUMSTANCES.sqlite"
    if target.exists():raise FileExistsError("Refusing to overwrite validated overlay")
    events=load_evidence(evidence_file)
    with sqlite3.connect(f"file:{Path(finances_db).resolve()}?mode=ro",uri=True) as source:
        source.execute("PRAGMA query_only=ON")
        records=source.execute("""SELECT club_key,edition,club_name,
          starting_payroll_weekly_gbp,game_wage_budget_weekly_gbp,
          game_transfer_budget_gbp FROM club_financial_profiles
          ORDER BY edition,club_name""").fetchall()
    if len(records)!=13104:raise ValueError("Source finance club parity failure")
    lookup=defaultdict(list)
    for key,ed,name,pay,wage,transfer in records:
        lookup[(ed,norm(name))].append(key)
    event_by_club=defaultdict(list)
    statuses=Counter()
    with sqlite3.connect(target) as db:
        db.executescript(SCHEMA)
        db.execute("""INSERT INTO circumstance_release
           (model_version,original_finance_sha256,events_sha256,source_club_count,
            observed_revenue_coverage,policy)
            VALUES(?,?,?,?,0,?)""",(VERSION,
              hashlib.sha256(Path(finances_db).read_bytes()).hexdigest(),
              hashlib.sha256(Path(evidence_file).read_bytes()).hexdigest(),13104,
              "Only official events are observed; wages/cash/budget effects are explicitly GAME ESTIMATES"))
        events_out=[]
        for e in events:
            matches=lookup.get((e["edition"],e["normal"]),[])
            status=("unique" if len(matches)==1 else
                    "absent_from_source_year" if len(matches)==0 else
                    "ambiguous_name")
            # Do not apply post-preseason events retroactively to game starts.
            active=(status=="unique" and e["date"]<=preseason_date(e["edition"]))
            key=matches[0] if len(matches)==1 else None
            if key:
                event_by_club[key].append(e)
            db.execute("""INSERT INTO observed_historical_events(
              event_id,edition,club_key,stated_club_name,category,event_date,
              source_authority,source_url,fact_text,source_match_status,
              active_at_preseason,game_effect_policy) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
              (e["id"],e["edition"],key,e["club"],e["event_type"],
               e["event_date"],e["source_authority"],e["source_url"],
               e["observed_fact"],status,int(bool(active)),
               "GAME_ESTIMATE_ONLY_IF_CONFIRMED_AND_ACTIVE"))
            statuses[status]+=1
            if active:statuses["active_preseason_evidence"]+=1
            events_out.append(e)
        rows=[]
        for key,edition,name,pay,wage,transfer in records:
            early=preseason_date(edition)
            ev=[e for e in event_by_club[key] if e["date"]<=early]
            # Ownership can be a longer-lived circumstance even if the
            # takeover happened after the prior season started. Never infer
            # additional capital injection as the result of a takeover.
            historical_ownership=[
                e for e in events
                if e["event_type"]=="ownership_change" and
                   e["date"]<=early and e["normal"]==norm(name)]
            owner=("documented_change_at_or_before_preseason"
                   if historical_ownership else "ownership_not_verified")
            neww,headroom,newt,health=impact(
                ev,base_wage_budget=wage,base_transfer_budget=transfer,pay=pay)
            active_ids=[e["id"] for e in ev]
            note=("Model policy only; event statuses are historical facts. "
                  "Current club revenue, cash, debt and injected equity NOT KNOWN. "
                  "A negative wage headroom is allowed and restricts fresh wages.")
            db.execute("""INSERT INTO historical_club_circumstances(
                club_key,edition,club_name,preseason_as_of,source_annual_payroll_gbp,
                prior_model_wage_budget_weekly_gbp,prior_model_transfer_budget_gbp,
                revised_total_wage_budget_weekly_gbp,signed_wage_headroom_weekly_gbp,
                revised_transfer_budget_gbp,transfer_budget_change_gbp,
                revenue_reported_gbp,reported_financial_year,
                verified_cash_balance_gbp,verified_net_debt_gbp,
                verified_owner_capital_injection_gbp,
                owner_status,financial_health,active_event_ids_json,
                finance_evidence_status,source_spending_policy,notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,NULL,?,?,?,?,?,?)""",
                (key,edition,name,early.isoformat(),pay,wage,transfer,
                 neww,headroom,newt,newt-transfer,owner,health,
                 json.dumps(active_ids),"published_events_only_no_individual_accounts",
                 VERSION,note))
            budget=("overcommitted_wages" if headroom<0 else "within_estimated_budget")
            rows.append((edition,name,key,early.isoformat(),pay,wage,neww,headroom,
                         transfer,newt,newt-transfer,health,owner,
                         "|".join(active_ids),"","","",
                         "event_evidence_only",budget,note))
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("Invalid financial circumstances SQLite")
        if db.execute("SELECT COUNT(*) FROM historical_club_circumstances").fetchone()[0]!=13104:
            raise ValueError("Lost historical club profiles")
        db.commit()
    def write_csv(filename,rows_,header=HEADERS):
        with (out/filename).open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f);w.writerow(header);w.writerows(rows_)
    write_csv("ALL_22_EDITIONS_FINANCIAL_CIRCUMSTANCES.csv",rows)
    write_csv("FC27_FINANCIAL_CIRCUMSTANCES.csv",
              (r for r in rows if r[0]==2027))
    write_csv("EVENT_AFFECTED_CLUB_FINANCES.csv",
              (r for r in rows if r[13]))
    write_csv("OVER_BUDGET_CLUBS.csv",(r for r in rows if r[7]<0))
    write_csv("VERIFIED_FINANCIAL_AND_SPORTING_EVENTS.csv",(
        (e["id"],e["edition"],e["club"],e["event_date"],e["event_type"],
         e["source_authority"],e["source_url"],e["observed_fact"],
         "observed_event_only_not_a_documented_cash_flow")
        for e in events),("Event_ID","Edition","Club","Date","Category",
                          "Source","URL","Observed_Fact","Value_Provenance"))
    result=dict(model=VERSION,total_clubs=len(rows),editions=22,
        linked_evidence=dict(statuses),
        clubs_with_signed_negative_headroom=sum(r[7]<0 for r in rows),
        clubs_with_active_events=sum(bool(r[13]) for r in rows),
        clubs_with_verifiable_cash_or_debt=0,
        original_player_wages_and_source_loans_unchanged=True,
        sources_not_found_in_source_edition=[e["id"] for e in events
            if not lookup.get((e["edition"],e["normal"]))],
        policy_parameters=dict(promotion_wage_factor=1.18,
           promotion_transfer_factor=1.45,relegation_wage_factor=.70,
           relegation_transfer_factor=.42,distress_wage_factor=.60,
           distress_transfer_factor=0.,
           ownership_money_injection_gbp=0),
        warning="All policy multipliers are provisional GAME RULES; source events are real. No club accounts or real takeover funding parsed yet.")
    (out/"FINANCIAL_CIRCUMSTANCES_AUDIT.json").write_text(
        json.dumps(result,indent=2),encoding="utf-8")
    (out/"README.txt").write_text(
      "MEN'S ONLY. Verified, URL-backed dated promotion/relegation/ownership/distress "
      "events vs estimated financial policy in separate fields. NO claimed "
      "verified club cash, net debt, operating revenue or takeover investment. "
      "Original V1 finances, FIFA player wages, loans, squads and career saves "
      "unchanged. Negative signed wage headroom is intentional. "
      "Unmatched team labels are retained for review, NOT forced matched.\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--finances",required=True)
    p.add_argument("--evidence",default="data/warehouse/historical_club_financial_events_v1.json")
    p.add_argument("--output",required=True)
    opts=p.parse_args()
    print(json.dumps(build(opts.finances,opts.evidence,opts.output),indent=2),flush=True)
