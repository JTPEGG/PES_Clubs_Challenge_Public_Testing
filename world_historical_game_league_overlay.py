"""Non-destructive consolidated historic FIFA in-game league assignment overlay.

Enriches the 447-division independent fixture registry with exact same-game
FIFA15-23 club home leagues. Game league IDs are scoped to each GAME edition,
not assumed to be independently sourced fixture competition IDs. A unified
read-only VIEW returns source fixture evidence if available, else original
game league identity; neither source alone activates a historical career.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from collections import Counter,defaultdict
from pathlib import Path

VERSION="historical-fifa-direct-game-league-overlay-v1"
SOURCE_SHA256="22b7d55ba67c8e07c5f496386ce0a9a0cccb00f40cea42d2be62a71563af2a71"
SOURCE_URL="https://huggingface.co/datasets/jsulz/FIFA23/resolve/80076aed77a08db5cfad31bfdfa2cebc579e9500/male_teams.csv"
SCHEMA="""
CREATE TABLE game_source_domestic_competitions(
  edition INTEGER NOT NULL,game_league_id TEXT NOT NULL,
  game_league_name TEXT NOT NULL,tier INTEGER NOT NULL,
  source_sha256 TEXT NOT NULL,
  PRIMARY KEY(edition,game_league_id));
CREATE TABLE game_source_club_home_leagues(
  edition INTEGER NOT NULL,club_key TEXT NOT NULL,
  game_league_id TEXT NOT NULL,ea_team_id TEXT NOT NULL,ea_team_name TEXT NOT NULL,
  team_nationality TEXT NOT NULL,source_observations INTEGER NOT NULL,
  original_game_name_match TEXT NOT NULL
    CHECK(original_game_name_match='unique_same_edition_exact_name'),
  source_sha256 TEXT NOT NULL,
  FOREIGN KEY(edition,club_key)
    REFERENCES edition_club_competitions(edition,club_key),
  FOREIGN KEY(edition,game_league_id)
    REFERENCES game_source_domestic_competitions(edition,game_league_id),
  PRIMARY KEY(edition,club_key));
CREATE TABLE game_source_to_fixture_competition_review(
  edition INTEGER NOT NULL,game_league_id TEXT NOT NULL,
  fixture_competition_code TEXT,distinct_clubs_corrob INTEGER NOT NULL,
  competing_division_count INTEGER NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY(edition,game_league_id));
CREATE VIEW historical_club_starting_leagues AS
 SELECT e.edition,e.club_key,e.club,
   CASE WHEN e.evidence_competition IS NOT NULL THEN e.evidence_competition
        WHEN g.game_league_id IS NOT NULL THEN
             'GAME:'||g.edition||':'||g.game_league_id ELSE NULL END AS starting_competition,
   CASE WHEN e.evidence_competition IS NOT NULL THEN 'independent_fixture_evidence'
        WHEN g.game_league_id IS NOT NULL THEN 'original_fifa_game_source'
        ELSE 'unresolved' END AS evidence_origin,
   g.game_league_id,gc.game_league_name,gc.tier AS game_source_tier,
   e.career_status
 FROM edition_club_competitions e
 LEFT JOIN game_source_club_home_leagues g
   ON e.edition=g.edition AND e.club_key=g.club_key
 LEFT JOIN game_source_domestic_competitions gc
   ON g.edition=gc.edition AND g.game_league_id=gc.game_league_id;
"""

def build(registry,game_csv,outdir,*,strict=True):
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True)
    target=out/"HISTORICAL_COMPETITION_REGISTER_WITH_ORIGINAL_FIFA_LEAGUES.sqlite"
    if target.exists():raise FileExistsError("Preserve old historical overlays")
    with sqlite3.connect(f"file:{Path(registry).resolve()}?mode=ro",uri=True) as src:
        with sqlite3.connect(target) as dst:
            src.backup(dst)
    with open(game_csv,encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    expected={"Edition","FIFA_Club_Key","Original_FIFA_Club","EA_Team_ID",
              "EA_Team_Name","Game_League_ID","Game_League_Name",
              "Game_League_Level","Game_Club_Country","EA_Observation_Count",
              "Name_Method","Evidence_Status"}
    if not rows or not expected.issubset(rows[0]):
        raise ValueError("Not a supported independently audited original-game team source")
    source_groups=defaultdict(set)
    for x in rows:
        y=int(x["Edition"]);ident=x["Game_League_ID"]
        if y not in range(2015,2024) or not ident.isdigit():
            raise ValueError("Invalid same-edition FIFA league ID")
        if (x["Name_Method"]!="unique_same_edition_exact_name"
            or x["Evidence_Status"] not in
              {"game_edition_home_league_identified","previous_fixture_evidence_corroborated"}
            or not x["EA_Team_ID"].isdigit()):
            raise ValueError("Source original FIFA club evidence unverified")
        source_groups[(y,ident)].add((x["Game_League_Name"],
                                     int(x["Game_League_Level"])))
    ambiguous_groups={key:choices for key,choices in source_groups.items()
                      if len(choices)!=1}
    usable={key:next(iter(options)) for key,options in source_groups.items()
            if key not in ambiguous_groups}
    accepted=[];blocked=[];duplicate=set()
    with sqlite3.connect(target) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        original={ (int(y),str(k)):(name,code) for y,k,name,code in db.execute(
            "SELECT edition,club_key,club,evidence_competition FROM edition_club_competitions")}
        for x in rows:
            y=int(x["Edition"]);k=x["FIFA_Club_Key"];lid=x["Game_League_ID"]
            if (y,k) in duplicate:raise ValueError("Duplicate game home league")
            duplicate.add((y,k))
            orig=original.get((y,k))
            if not orig or orig[0]!=x["Original_FIFA_Club"]:
                raise ValueError("Original club identity differs from immutable FIFA archive")
            if (y,lid) in ambiguous_groups:
                blocked.append((y,k,x["Original_FIFA_Club"],lid,
                                "game_id_appears_with_multiple_league_names_or_tiers"))
                continue
            accepted.append((y,k,lid,x["EA_Team_ID"],x["EA_Team_Name"],
                x["Game_Club_Country"],int(x["EA_Observation_Count"]),
                x["Name_Method"],SOURCE_SHA256))
        db.executemany("INSERT INTO game_source_domestic_competitions VALUES (?,?,?,?,?)",
            ((y,lid,name,tier,SOURCE_SHA256) for (y,lid),(name,tier) in sorted(usable.items())))
        db.executemany("INSERT INTO game_source_club_home_leagues VALUES (?,?,?,?,?,?,?,?,?)",accepted)
        counts=defaultdict(Counter)
        for y,lid,comp,n in db.execute("""
            SELECT g.edition,g.game_league_id,e.evidence_competition,COUNT(*)
            FROM game_source_club_home_leagues g
            JOIN edition_club_competitions e ON e.edition=g.edition AND e.club_key=g.club_key
            WHERE e.evidence_competition IS NOT NULL
            GROUP BY g.edition,g.game_league_id,e.evidence_competition"""):
            counts[(y,lid)][comp]+=n
        review=[]
        for (y,lid),(_,_) in sorted(usable.items()):
            votes=counts[(y,lid)]
            winner=sorted(votes.items(),key=lambda item:(-item[1],item[0]))
            best,count=winner[0] if winner else (None,0)
            corroborated=(best is not None and count>=3 and
                          count/sum(votes.values())>=0.90)
            review.append((y,lid,best if corroborated else None,count,
                 len(votes),"three_or_more_same_league_fixture_clubs" if corroborated
                 else "needs_independent_competition_crosswalk"))
        db.executemany(
             "INSERT INTO game_source_to_fixture_competition_review VALUES (?,?,?,?,?,?)",review)
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("Historical game overlay failed SQLite integrity check")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Foreign-key mismatch in historic game league assignments")
        before=db.execute("""SELECT COUNT(*) FROM edition_club_competitions
                           WHERE evidence_competition IS NOT NULL""").fetchone()[0]
        after=db.execute("""SELECT COUNT(*) FROM historical_club_starting_leagues
                           WHERE starting_competition IS NOT NULL""").fetchone()[0]
        original_rows=db.execute("SELECT COUNT(*) FROM edition_club_competitions").fetchone()[0]
        game_only=db.execute("""SELECT COUNT(*) FROM historical_club_starting_leagues
                  WHERE evidence_origin='original_fifa_game_source'""").fetchone()[0]
        careers=db.execute("SELECT COUNT(*) FROM edition_readiness WHERE career_ready!=0").fetchone()[0]
        if careers:raise ValueError("Overlay cannot activate unverified careers")
        if before+game_only!=after:raise ValueError("Overlay evidence count unexpectedly overlaps")
        if strict and (original_rows!=13104 or before!=5941):
            raise ValueError("Wrong 22-edition source registry")
        db.commit()
    with (out/"ORIGINAL_FIFA_GAME_LEAGUE_AMBIGUITIES.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(("Edition","FIFA_Club_Key","Club","Game_League_ID","Reason"))
        w.writerows(blocked)
    with (out/"FIFA_GAME_LEAGUE_COMPETITION_CROSSWALK_REVIEW.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(("Edition","Game_League_ID","Corroborated_Competition",
            "Fixture_Clubs_For_Best","Distinct_Fixture_Competitions","Crosswalk_Status"))
        w.writerows(review)
    summary=dict(version=VERSION,original_club_seasons=original_rows,
        source_fixture_club_seasons_with_evidence=before,
        direct_fifa_game_club_league_records=len(accepted),
        game_source_unique_league_groups=len(usable),
        inconsistent_game_league_group_club_records=len(blocked),
        game_home_leagues_filling_prior_gaps=game_only,
        club_seasons_with_starting_league_evidence=after,
        remaining_without_any_starting_league_evidence=original_rows-after,
        direct_game_groups_corroborated_against_source_fixtures=sum(
          v[5]=="three_or_more_same_league_fixture_clubs" for v in review),
        career_ready_editions=0,squads_modified=False,source_fixture_data_overwritten=False,
        notes="GAME:season:league_id is a genuine original FIFA game league, not yet a canonical independent fixture league. Competitions needing a formal promotion/relegation graph remain blocked.")
    (out/"CONSOLIDATED_GAME_HOME_LEAGUE_OVERLAY_AUDIT.json").write_text(
         json.dumps(summary,indent=2),encoding="utf-8")
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True);p.add_argument("--game-leagues",required=True)
    p.add_argument("--output",required=True);p.add_argument("--no-strict",action="store_true")
    a=p.parse_args()
    print(json.dumps(build(a.registry,a.game_leagues,a.output,
        strict=not a.no_strict),indent=2))
