"""FC27-only controlled domestic source league group -> real competition association.

For FC27 original imported player-source club groups, link clearly reviewed
labels to their domestic association and tier without alleging that the
independent official 2026/27 club register or original EA game IDs are proved.
Keep all 40 CONMEBOL continental groups unresolved. No other edition altered.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3
from collections import Counter,defaultdict
from pathlib import Path
from world_historical_competition_registry import canonical,cup_group
from world_competition_exclusions import excluded_source_league

VERSION="fc27-one-edition-source-association-overlay-v1"
EDITION=2027
SCHEMA="""
CREATE TABLE fc27_reviewed_domestic_competitions(
 edition INTEGER NOT NULL CHECK(edition=2027),
 source_group TEXT NOT NULL,canonical_code TEXT NOT NULL,
 country TEXT NOT NULL,competition TEXT NOT NULL,tier INTEGER NOT NULL,
 source_clubs INTEGER NOT NULL,calendar TEXT NOT NULL,
 registration_scope TEXT NOT NULL,
 original_EA_ids_verified INTEGER NOT NULL CHECK(original_EA_ids_verified=0),
 official_roster_verified INTEGER NOT NULL CHECK(official_roster_verified=0),
 PRIMARY KEY(edition,source_group),UNIQUE(edition,canonical_code));
CREATE TABLE fc27_reviewed_source_club_assignments(
 edition INTEGER NOT NULL CHECK(edition=2027),
 club_key TEXT NOT NULL,original_club TEXT NOT NULL,
 source_group TEXT NOT NULL,canonical_code TEXT NOT NULL,
 source_status TEXT NOT NULL CHECK(source_status='original_imported_club_source_label'),
 PRIMARY KEY(edition,club_key),
 FOREIGN KEY(edition,club_key) REFERENCES edition_club_competitions(edition,club_key),
 FOREIGN KEY(edition,source_group) REFERENCES fc27_reviewed_domestic_competitions(edition,source_group));
CREATE VIEW fc27_one_year_club_competition_alignment AS
 SELECT old.edition,old.club_key,old.club,
   COALESCE(old.starting_competition,x.canonical_code) AS starting_competition,
   CASE WHEN old.starting_competition IS NOT NULL THEN old.evidence_origin
        WHEN x.canonical_code IS NOT NULL THEN 'original_imported_source_group_country_tier_review'
        ELSE 'unresolved' END AS evidence_origin,
   CASE WHEN old.starting_competition IS NOT NULL THEN 'existing_independent_evidence'
        WHEN x.canonical_code IS NOT NULL THEN c.registration_scope
        ELSE 'no_domestic_league_identity' END AS registration_scope,
   c.country,c.competition,c.tier
 FROM edition_career_starting_league_candidates old
 LEFT JOIN fc27_reviewed_source_club_assignments x
   ON x.edition=old.edition AND x.club_key=old.club_key
 LEFT JOIN fc27_reviewed_domestic_competitions c
   ON c.edition=x.edition AND c.source_group=x.source_group
 WHERE old.edition=2027 AND NOT EXISTS (
   SELECT 1 FROM edition_club_competitions o
   WHERE o.edition=old.edition AND o.club_key=old.club_key
     AND o.original_source_league IN ('ISL','Indian Super League'));
"""

def export(path,headers,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as out:
        writer=csv.writer(out);writer.writerow(headers);writer.writerows(rows)

def build(registry,config_path,outdir,strict=True):
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads(Path(config_path).read_text(encoding="utf-8"))
    if cfg.get("version")!="fc27-imported-league-group-association-v1" or cfg.get("edition")!=2027:
        raise ValueError("Wrong season or unaudited manual league mapping file")
    entries=cfg["groups"]
    if len({x["source_group"] for x in entries})!=len(entries) or len(
         {x["code"] for x in entries})!=len(entries):
        raise ValueError("Multiple groups mapping to the same competition or overlapping original source label")
    if any(excluded_source_league(x['source_group']) for x in entries):
        raise ValueError('An excluded competition was reintroduced into the playable scope')
    if strict and (len(entries)!=27 or sum(x["expected_original_clubs"] for x in entries)!=242):
        raise ValueError("Expected original FC27 domestic labels not present")
    result=out/"FC27_2026_27_CLUB_COMPETITION_SOURCE_ASSOCIATION.sqlite"
    if result.exists():raise FileExistsError("Never mutate prior original league releases")
    with sqlite3.connect(f"file:{Path(registry).resolve()}?mode=ro",uri=True) as source,\
         sqlite3.connect(result) as dest:
        source.backup(dest)
    with sqlite3.connect(result) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        originals=db.execute("""SELECT o.club_key,o.club,o.original_source_league,
                 o.group_type,p.starting_competition,p.evidence_origin
                 FROM edition_club_competitions o
                 JOIN edition_career_starting_league_candidates p
                   ON o.edition=p.edition AND o.club_key=p.club_key
                 WHERE o.edition=2027""").fetchall()
        if strict and len(originals)!=670:raise ValueError("Wrong source edition club count")
        old_original_count=db.execute("SELECT COUNT(*) FROM edition_club_competitions").fetchone()[0]
        if old_original_count!=13104 and strict:raise ValueError("22-edition original registry drift")
        official_code={code:(country,tier) for code,country,tier in
            db.execute("SELECT code,country,tier FROM competition_seasons WHERE edition=2027")}
        excluded=[(key,name,label) for key,name,label,kind,code,origin in originals
                  if excluded_source_league(label)]
        if strict and len(excluded)!=11:
            raise ValueError('Exclusion rule no longer covers exactly 11 original FC27 club records')
        original_groups=defaultdict(list)
        for club_key,name,label,kind,code,origin in originals:
            if excluded_source_league(label) or cup_group(label) or kind=="continental_cup_bucket":
                continue
            if code is None:
                original_groups[label].append((club_key,name,kind))
        mapped=[];registered=[];warnings=[]
        for cfgrow in entries:
            label=cfgrow["source_group"]
            identity=f"2027:{cfgrow['code']}"
            if label not in original_groups:
                raise ValueError(f"Missing original FC27 source group {label}")
            members=original_groups[label]
            expected=int(cfgrow["expected_original_clubs"])
            if len(members)!=expected:
                raise ValueError(f"Incorrect original-group members for {label}: {len(members)} vs {expected}")
            if any(kind!="domestic_source_group" for _,_,kind in members):
                raise ValueError("Cup or unsupported group cannot become a domestic league")
            if len({canonical(name) for _,name,_ in members})!=len(members):
                raise ValueError(f"Duplicate actual club identities in {label}")
            if not identity.startswith("2027:") or not cfgrow["country"] or cfgrow["tier"] not in (1,2):
                raise ValueError("Invalid edition-specific country/tier")
            if identity in official_code:
                if official_code[identity]!=(cfgrow["country"],cfgrow["tier"]):
                    raise ValueError(f"Original source conflicts with independent league tier/country {identity}")
                warnings.append((label,identity,"same_code_as_independent_fixture_competition_membership_not_yet_proven"))
            db.execute("INSERT INTO fc27_reviewed_domestic_competitions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (2027,label,identity,cfgrow["country"],cfgrow["competition"],cfgrow["tier"],
                 expected,cfgrow["calendar"],cfgrow["registration_scope"],0,0))
            registered.append((label,identity,cfgrow["country"],cfgrow["tier"],expected,
                 cfgrow["registration_scope"],"source_group_country_tier_review_not_official_roster"))
            for key,name,kind in members:
                mapped.append((2027,key,name,label,identity,"original_imported_club_source_label"))
        db.executemany("INSERT INTO fc27_reviewed_source_club_assignments VALUES (?,?,?,?,?,?)",mapped)
        previous=db.execute("""SELECT COUNT(*) FROM edition_career_starting_league_candidates
            WHERE edition=2027 AND starting_competition IS NOT NULL""").fetchone()[0]
        combined=db.execute("""SELECT COUNT(*) FROM fc27_one_year_club_competition_alignment
            WHERE starting_competition IS NOT NULL""").fetchone()[0]
        unresolved=db.execute("""SELECT club_key,club FROM fc27_one_year_club_competition_alignment
            WHERE starting_competition IS NULL ORDER BY club""").fetchall()
        if combined!=previous+len(mapped) or len(unresolved)!=len(originals)-len(excluded)-combined:
            raise ValueError("Original FC27 club evidence lost, duplicated or silently reassigned")
        for key,name in unresolved:
            group=next(x[2] for x in originals if x[0]==key)
            if not cup_group(group):
                raise ValueError(f"Unmapped original non-cup FC27 source club {name} {group}")
        if strict and (previous!=377 or len(mapped)!=242 or combined!=619 or len(unresolved)!=40):
            raise ValueError("FC27 source group mapping changed; audit exact clubs instead")
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Final FC27 source association has broken SQLite identity")
        if db.execute("SELECT COUNT(*) FROM edition_readiness WHERE career_ready!=0").fetchone()[0]:
            raise ValueError("Uncertified historical career accidentally enabled")
        db.commit()
    export(out/"FC27_REVIEWED_SOURCE_COMPETITION_CROSSWALK.csv",
           ("Imported_Source_Group","Competition_Code","Country","Tier",
            "Source_Game_Group_Clubs","Registration_Scope","Identity_Status"),registered)
    export(out/"FC27_242_DOMESTIC_CLUB_SOURCE_ASSOCIATIONS.csv",
           ("Edition","Club_Key","Imported_Source_Club","Imported_Source_League",
            "Named_Home_Competition_Code","Source_Status"),mapped)
    export(out/"FC27_EXCLUDED_GAME_SOURCE_CLUBS_AUDIT.csv",
           ("Original_Club_Key","Archived_Club","Original_League","Disposition"),
           [(key,name,label,'excluded_from_playable_game_world') for key,name,label in excluded])
    export(out/"FC27_40_CONMEBOL_HOME_LEAGUE_REVIEW.csv",
           ("Original_Club_Key","Club","Source_Group"),[
              (key,name,next(x[2] for x in originals if x[0]==key))
              for key,name in unresolved])
    export(out/"FC27_ORIGINAL_COMPETITION_CODE_OVERLAPS_REVIEW.csv",
           ("Original_Source_League","Dated_Fixture_Competition","Warning"),warnings)
    report={"version":VERSION,"edition":2027,"original_FC27_club_records":len(originals),
      "previously_linked_to_league_evidence":previous,
      "excluded_original_source_clubs":len(excluded),
      "active_FC27_clubs_in_game":len(originals)-len(excluded),
      "new_source_domestic_league_associations":len(mapped),
      "new_competition_names_country_tier_scoped":len(registered),
      "total_clubs_with_stated_domestic_competition":combined,
      "still_unresolved_continental_competition_bucket":len(unresolved),
      "competition_codes_already_in_independent_fixture_registry":len(warnings),
      "source_only_leagues_missing_2026_27_roster_validation":len(registered),
      "external_fixture_teams_not_fabricated":True,
      "original_EA_team_ids_not_verified":True,
      "historic_2027_career_ready":False,
      "other_21_editions_not_modified":True,
      "original_squads_not_modified":True,
      "notes":"Excluded source groups are withheld from every game-facing FC27 view. All other mapped groups still require verified actual memberships and one-hop movement; source originals unchanged."}
    (out/"FC27_CLUB_DOMESTIC_LEAGUE_ASSOCIATION_RESULT.json").write_text(
      json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--registry",required=True)
    a.add_argument("--associations",required=True);a.add_argument("--output",required=True)
    a.add_argument("--no-strict",action="store_true")
    opts=a.parse_args()
    print(json.dumps(build(opts.registry,opts.associations,opts.output,
           strict=not opts.no_strict),indent=2))
