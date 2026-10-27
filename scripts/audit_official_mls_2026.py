"""Official 2026 MLS competition rules against pinned FC27 starting-year clubs."""
import argparse,csv,json
from pathlib import Path
from world_historical_competition_registry import canonical

OFFICIAL_MLS_ALIASES={
    "Los Angeles Football Club":"LAFC",
    "Orlando City SC":"Orlando City",
}
def clubkey(name):
    return canonical(OFFICIAL_MLS_ALIASES.get(name,name))

def audit(config,source_clubs,output):
    data=json.loads(Path(config).read_text(encoding="utf-8"))
    if data["edition"]!=2027 or data["calendar_season"]!=2026:
        raise ValueError("MLS calendar season does not correspond to 2026 FC27 start")
    if data["competition_code"]!="2027:us.mls":
        raise ValueError("MLS format belongs to wrong competition season")
    if not data["source_url"].startswith("https://www.mlssoccer.com/"):
        raise ValueError("Not supported by an official MLS source")
    conferences=data["club_conferences"]
    if set(conferences)!={"Eastern","Western"}:
        raise ValueError("Missing official MLS East/West conferences")
    if any(len(clubs)!=15 for clubs in conferences.values()):
        raise ValueError("Official MLS conference membership must have 15 teams each")
    original={clubkey(club):group for group,clubs in conferences.items() for club in clubs}
    if len(original)!=30 or any(not k for k in original):
        raise ValueError("Duplicate official MLS club IDs across conferences")
    with open(source_clubs,encoding="utf-8-sig",newline="") as file:
        members=[r for r in csv.DictReader(file) if r["League_Code"]=="us.mls"]
    if len(members)!=30 or any(r["Edition"]!="2027" for r in members):
        raise ValueError("Non-2026 or incomplete MLS snapshot source")
    observed={}
    for row in members:
        if row["Evidence_Status"]!="source_observation_pending_game_identity_review":
            raise ValueError("External MLS sources cannot imply verified EA squads")
        k=clubkey(row["Fixture_Club"])
        if k in observed:raise ValueError("Same MLS snapshot club more than once")
        observed[k]=row["Fixture_Club"]
    missing=set(original)-set(observed)
    extra=set(observed)-set(original)
    if missing or extra:
        raise ValueError("Official MLS 30-team membership disagrees with pinned snapshot: "
                         +str((sorted(missing),sorted(extra))))
    base=data["regular_season"]
    playoffs=data["postseason"]
    pyramid=data["pyramid_movement"]
    if (base["clubs"]!=30 or base["conferences"]!=2 or
        base["matches_per_team"]!=34 or
        base["clubs_per_conference"]!=15 or
        playoffs["qualification_per_conference"]!=9 or
        playoffs["direct_round_one_per_conference"]!=7 or
        playoffs["wildcard_seeds"]!=[8,9] or
        playoffs["round_one_format"]!="best_of_three" or
        any(pyramid.values())):
        raise ValueError("Invalid official MLS closed pyramid or postseason configuration")
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with (output/"MLS_2026_OFFICIAL_MEMBERS.csv").open(
            "w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f)
        w.writerow(("Edition","Competition_Code","Conference","Official_Club",
                    "Snapshot_Club","Source_URL","Verification"))
        for official_group,clubs in conferences.items():
            for club in clubs:
                w.writerow((2027,"2027:us.mls",official_group,club,
                            observed[clubkey(club)],data["source_url"],
                            "official_mls_member_matches_independent_fixture_snapshot"))
    report={"edition":2027,"calendar_year":2026,
        "competition":"2027:us.mls","official_members":30,
        "conferences":2,"clubs_per_conference":15,"regular_season_games_per_club":34,
        "postseason_teams_per_conference":9,"wild_card_per_conference":2,
        "promotion_relegation_slots":0,
        "verified_source_fixture_crosscheck":30,
        "career_ready":False,"no_fabricated_club_roster":True}
    (output/"MLS_2026_OFFICIAL_RULES_AUDIT.json").write_text(
        json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--official",required=True)
    p.add_argument("--fixtures",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(audit(a.official,a.fixtures,a.output),indent=2))
