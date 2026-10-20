"""Build a men-only 22-edition club financial overlay from approved FIFA/PES wages.

Only committed salaries and 50/50 existing-loan obligations are source/model
inputs. Wage *budgets*, transfer *budgets*, and planning squad sizes are
gameplay estimates, NOT verified actual club accounts. No source rows altered.
"""
import argparse,bisect,csv,hashlib,json,sqlite3,statistics
from collections import Counter,defaultdict
from pathlib import Path

VERSION="PES-V2-historical-club-finances-v1"
SOURCE_MODEL="historical-wage-and-loan-v4-fc27-quality-reviewed"
YEARS=set(range(2005,2028))-{2025}
HEADERS=("Edition","Club","Source_Club_Key","Source_Club_ID","Source_League",
 "League_Source_Status","Registered_Players","Assigned_Player_Wages_Weekly_GBP",
 "Committed_Payroll_Weekly_GBP","Incoming_Source_Loans","Outgoing_Source_Loans",
 "Loans_Unresolved","Largest_Player_Wage_Weekly_GBP",
 "Largest_Player_Payroll_Share_Percent","Financial_Planning_Squad_Size",
 "Projected_Planning_Payroll_Weekly_GBP","Financial_Capacity_Percentile",
 "Financial_Capacity_Band","Estimated_Total_Weekly_Wage_Budget_GBP",
 "Remaining_Weekly_Wage_Headroom_GBP","Estimated_Starting_Transfer_Budget_GBP",
 "Wage_Budget_to_Current_Payroll_Multiple","Review_Flags","Budget_Provenance")
SCHEMA="""
CREATE TABLE model_metadata(
 model_version TEXT PRIMARY KEY,source_database_sha256 TEXT NOT NULL,
 provenance TEXT NOT NULL, initial_club_rows INTEGER NOT NULL,
 original_player_rows INTEGER NOT NULL,
 transfer_budget_source TEXT NOT NULL DEFAULT 'simulation_estimate',
 wage_budget_source TEXT NOT NULL DEFAULT 'simulation_estimate');
CREATE TABLE club_financial_profiles(
 club_key TEXT PRIMARY KEY,
 edition INTEGER NOT NULL,
 club_name TEXT NOT NULL,
 source_club_id TEXT,
 source_league_name TEXT,
 source_league_status TEXT NOT NULL,
 registered_squad_players INTEGER NOT NULL,
 assigned_player_wages_weekly_gbp INTEGER NOT NULL,
 starting_payroll_weekly_gbp INTEGER NOT NULL,
 incoming_loans INTEGER NOT NULL,
 outgoing_loans INTEGER NOT NULL,
 unresolved_parent_loans INTEGER NOT NULL,
 largest_player_wage_weekly_gbp INTEGER NOT NULL,
 largest_player_share_of_club_payroll_pct REAL NOT NULL,
 minimum_planning_squad_players INTEGER NOT NULL,
 projected_squad_payroll_weekly_gbp INTEGER NOT NULL,
 financial_capacity_percentile REAL NOT NULL,
 financial_capacity_band TEXT NOT NULL,
 game_wage_budget_weekly_gbp INTEGER NOT NULL,
 starting_wage_headroom_weekly_gbp INTEGER NOT NULL,
 game_transfer_budget_gbp INTEGER NOT NULL,
 wage_budget_coverage_multiple REAL NOT NULL,
 finance_source TEXT NOT NULL DEFAULT 'game_model_estimate',
 reliability_flag TEXT NOT NULL,
 rationale TEXT NOT NULL,
 CHECK(game_wage_budget_weekly_gbp>=starting_payroll_weekly_gbp),
 CHECK(game_transfer_budget_gbp>=0));
CREATE INDEX club_finance_edition ON club_financial_profiles(edition);
CREATE INDEX club_finance_name ON club_financial_profiles(edition,club_name);
"""
def round_budget(value):
    if value<100000:return max(2500,round(value/1000)*1000)
    if value<1000000:return round(value/5000)*5000
    return round(value/50000)*50000

def capacity_band(score):
    if score>=.97:return "elite_financial_proxy"
    if score>=.85:return "strong_financial_proxy"
    if score>=.50:return "established_financial_proxy"
    if score>=.20:return "modest_financial_proxy"
    return "small_financial_proxy"

def estimate_finances(*,starting_payroll,projected_payroll,capacity_score,
                      max_player_wage,roster_count):
    if min(starting_payroll,projected_payroll,max_player_wage,roster_count)<0:
        raise ValueError("Negative finance source inputs")
    if projected_payroll<starting_payroll or not 0<=capacity_score<=1:
        raise ValueError("Invalid financial capacity or payroll projection")
    total=round(max(starting_payroll+max(1000,round(starting_payroll*.10)),
                    projected_payroll*(1.14+.12*capacity_score))/50)*50
    concentration=max_player_wage/starting_payroll if starting_payroll else 0
    penalty=max(.65,1-max(0,concentration-.25)*.55)
    budget=round_budget(projected_payroll*52*(.075+.325*capacity_score**1.8)*penalty)
    return total,total-starting_payroll,budget

def rows_from_source(source):
    with sqlite3.connect(f"file:{Path(source).resolve()}?mode=ro",uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        if {y for y, in db.execute("SELECT edition FROM editions")}!=YEARS:
            raise ValueError("Expected 22 approved men-only editions")
        if db.execute("SELECT COUNT(*) FROM players").fetchone()[0]!=317449:
            raise ValueError("Unexpected source player count")
        model=db.execute("SELECT model_version FROM starting_finance_model").fetchone()
        if not model or model[0]!=SOURCE_MODEL:
            raise ValueError("Must use approved FC27 v4 wage/loan archive")
        clubs=db.execute("""SELECT c.club_key,c.edition,c.name,c.source_club_id,
          l.league_name,c.league_status,c.squad_size,
          f.model_payroll_weekly_gbp
          FROM clubs c JOIN starting_club_finances f ON c.club_key=f.club_key
          LEFT JOIN leagues l ON l.league_key=c.league_key
          ORDER BY c.edition,c.name,c.club_key""").fetchall()
        if len(clubs)!=13104:raise ValueError("Unexpected source club count")
        assigned=defaultdict(list)
        obligated=defaultdict(list)
        year_wages=defaultdict(list)
        loans={k:(p,b,pct) for k,p,b,pct in db.execute("""SELECT player_key,
           resolved_parent_club_key,borrower_club_key,simulated_borrower_wage_share_pct
           FROM starting_source_loans WHERE parent_status='resolved'""")}
        for key,club,year,w in db.execute("""SELECT p.player_key,p.club_key,p.edition,
           f.model_weekly_wage_gbp FROM players p JOIN starting_player_finances f
           ON p.player_key=f.player_key WHERE p.club_key IS NOT NULL"""):
            assigned[club].append(w)
            year_wages[year].append(w)
            loan=loans.get(key)
            if loan:
                parent,borrower,pct=loan
                if club!=borrower:raise ValueError("Borrower registration mismatch")
                borrower_cost=round(w*pct/100)
                obligated[borrower].append(borrower_cost)
                obligated[parent].append(w-borrower_cost)
            else:obligated[club].append(w)
        incoming=Counter();outgoing=Counter();unresolved=Counter()
        for borrower,parent,status in db.execute("""SELECT borrower_club_key,
            resolved_parent_club_key,parent_status FROM starting_source_loans"""):
            if status=="resolved":
                incoming[borrower]+=1;outgoing[parent]+=1
            elif borrower:unresolved[borrower]+=1
        medians={y:statistics.median(w) for y,w in year_wages.items()}
        result=[]
        for key,year,name,sid,league,status,n,pay in clubs:
            player_wages=assigned[key]
            if len(player_wages)!=n:
                raise ValueError("Club source squad size differs from salaries")
            burdens=obligated[key]
            if sum(burdens)!=pay:
                raise ValueError("Borrower/parent commitments differ from prior payroll")
            typical=statistics.median(player_wages) if player_wages else medians[year]
            typical=max(medians[year]*.4,min(typical,medians[year]*8))
            projected=round(pay+max(0,18-n)*typical)
            largest=max(burdens) if burdens else 0
            share=round(100*largest/pay,2) if pay else 0
            result.append(dict(key=key,year=year,name=name,sid=sid,league=league,
                status=status,n=n,player_wages=sum(player_wages),pay=pay,
                incoming=incoming[key],outgoing=outgoing[key],unresolved=unresolved[key],
                largest=largest,share=share,projected=projected))
    yearly=defaultdict(list)
    for row in result:yearly[row["year"]].append(row["projected"])
    for xs in yearly.values():xs.sort()
    earlier_club=defaultdict(list)
    for r in result:
        year=r["year"];values=yearly[year];n=len(values)
        left=bisect.bisect_left(values,r["projected"])
        right=bisect.bisect_right(values,r["projected"])
        percentile=(left+right-1)/(2*(n-1)) if n>1 else .5
        history_key="".join(c for c in r["name"].casefold() if c.isalnum())
        recent=[p for y,p in earlier_club[history_key] if 0<year-y<=5]
        strength=.8*percentile+.2*sum(recent)/len(recent) if recent else percentile
        earlier_club[history_key].append((year,percentile))
        r["score"]=round(strength,6)
        r["band"]=capacity_band(strength)
        wage,headroom,transfer=estimate_finances(
            starting_payroll=r["pay"],projected_payroll=r["projected"],
            capacity_score=strength,max_player_wage=r["largest"],roster_count=r["n"])
        r["wb"]=wage;r["headroom"]=headroom;r["transfer"]=transfer
        flags=[]
        if r["n"]<16:flags.append("sparse_source_squad")
        if r["share"]>=25:flags.append("concentrated_wage_bill")
        if r["unresolved"]:flags.append("unresolved_source_loan_parent")
        r["flags"]="|".join(flags) if flags else "standard_source_coverage"
        r["multiple"]=round(wage/max(1,r["pay"]),3)
    return result

def output_row(r):
    return (r["year"],r["name"],r["key"],r["sid"],r["league"],r["status"],
            r["n"],r["player_wages"],r["pay"],r["incoming"],r["outgoing"],
            r["unresolved"],r["largest"],r["share"],18,r["projected"],
            r["score"],r["band"],r["wb"],r["headroom"],r["transfer"],
            r["multiple"],r["flags"],"game_model_estimate")

def build(source,output):
    dest=Path(output);dest.mkdir(parents=True,exist_ok=True)
    dbfile=dest/"PES_V2_HISTORICAL_CLUB_FINANCIALS.sqlite"
    if dbfile.exists():raise FileExistsError("An immutable finance release already exists")
    rows=rows_from_source(source)
    with sqlite3.connect(dbfile) as db:
        db.executescript(SCHEMA)
        db.execute("""INSERT INTO model_metadata
           (model_version,source_database_sha256,provenance,initial_club_rows,
            original_player_rows) VALUES(?,?,?,?,?)""",
           (VERSION,hashlib.sha256(Path(source).read_bytes()).hexdigest(),
            "Club budgets estimated; payroll sourced from approved V4 wages and loans",
            13104,317449))
        db.executemany("""INSERT INTO club_financial_profiles
         (club_key,edition,club_name,source_club_id,source_league_name,
          source_league_status,registered_squad_players,
          assigned_player_wages_weekly_gbp,starting_payroll_weekly_gbp,
          incoming_loans,outgoing_loans,unresolved_parent_loans,
          largest_player_wage_weekly_gbp,largest_player_share_of_club_payroll_pct,
          minimum_planning_squad_players,projected_squad_payroll_weekly_gbp,
          financial_capacity_percentile,financial_capacity_band,
          game_wage_budget_weekly_gbp,starting_wage_headroom_weekly_gbp,
          game_transfer_budget_gbp,wage_budget_coverage_multiple,
          reliability_flag,rationale) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
         ((*output_row(r)[:22],r["flags"],
           "22-year relative payroll proxy; 18-player planning when sparse; "
           "7.5%-40% annualized projected wage payroll for discretionary game "
           "transfer budget, reduced for wage concentration") for r in rows))
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("SQL integrity failure")
        if db.execute("SELECT COUNT(*) FROM club_financial_profiles").fetchone()[0]!=13104:
            raise ValueError("Lost club profiles")
        if db.execute("SELECT COUNT(*) FROM club_financial_profiles WHERE game_wage_budget_weekly_gbp<starting_payroll_weekly_gbp").fetchone()[0]:
            raise ValueError("Club budget cannot fund initial payroll")
        db.commit()
    def export(name,records):
        with (dest/name).open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f);w.writerow(HEADERS);w.writerows(output_row(r) for r in records)
    export("ALL_22_EDITIONS_CLUB_FINANCES.csv",rows)
    export("FC27_CLUB_FINANCES.csv",sorted((r for r in rows if r["year"]==2027),
                                         key=lambda x:-x["transfer"]))
    flagged=[r for r in rows if r["flags"]!="standard_source_coverage"]
    export("CLUB_FINANCE_REVIEW_FLAGS.csv",flagged)
    years={}
    for y in sorted(YEARS):
        group=[r for r in rows if r["year"]==y]
        years[str(y)]=dict(clubs=len(group),
            committed_payroll_weekly_gbp=sum(r["pay"] for r in group),
            wage_budget_weekly_gbp=sum(r["wb"] for r in group),
            transfer_budget_gbp=sum(r["transfer"] for r in group),
            sparse_source_squads=sum(r["n"]<16 for r in group),
            source_league_unknown=sum(not r["league"] for r in group),
            largest_player_at_least_25pct=sum(r["share"]>=25 for r in group))
    result=dict(version=VERSION,source_wage_model=SOURCE_MODEL,
      scope="MENS_ONLY_ESTIMATED_CLUB_FINANCES",club_count=len(rows),
      edition_count=len(years),original_player_count=317449,
      source_budget_evidence="NO_VERIFIED_BUDGETS_IN_THIS_SOURCE",
      no_source_salaries_or_loans_modified=True,
      all_transfer_and_total_wage_budgets="GAME_MODEL_ESTIMATES_NOT_REAL_HISTORICAL_FACTS",
      planning_squad_minimum=18,review_flagged_clubs=len(flagged),years=years)
    (dest/"CLUB_FINANCE_AUDIT.json").write_text(json.dumps(result,indent=2))
    (dest/"README.txt").write_text(
      "Men-only FIFA/PES V2 club financial planning. All 22 editions, FC25 absent. "
      "Transfer budgets and total salary budgets are game estimates. "
      "No independently source-verified cash or debt. Current committed payroll "
      "includes approved player salaries and parent/borrower source-loan split. "
      "Missing leagues and sparse historical source squads remain explicitly flagged. "
      "No careers or original records are changed.\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    result=build(a.input,a.output)
    print(json.dumps({k:v for k,v in result.items() if k!="years"},indent=2),flush=True)
    for y in (2005,2012,2020,2026,2027):
        print(y,result["years"][str(y)],flush=True)
