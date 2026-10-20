"""Auditable, non-guessing gap triage for the 22-edition men's competition world.

Input: original FIFA club SQLite + consolidated historical competition register.
Output: source-preserving per-club, per-edition, source-group and alias backlogs.
A competition observation is NEVER a full career-readiness certificate.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from world_historical_competition_registry import YEARS, canonical, cup_group

REASONS = (
    "continental_bucket_needs_home_league",
    "conflicting_domestic_evidence",
    "fixture_name_in_multiple_divisions",
    "unique_external_name_not_crosswalked",
    "game_id_identified_domestic_league_unsourced",
    "unidentified_original_source_group",
    "unlabelled_game_club_without_identity_evidence",
)
RESOLUTION = {
    "continental_bucket_needs_home_league": "source_domestic_membership_for_cup_club",
    "conflicting_domestic_evidence": "review_conflicting_club_identity",
    "fixture_name_in_multiple_divisions": "review_cross_league_name_collision",
    "unique_external_name_not_crosswalked": "inspect_exact_identity_join",
    "game_id_identified_domestic_league_unsourced": "source_home_league_using_verified_game_club_id",
    "unidentified_original_source_group": "identify_original_league_and_source_dated_members",
    "unlabelled_game_club_without_identity_evidence": "source_historical_home_division",
}
KNOWN_LINKS = {
    "fixture_exact": "individual_fixture_name_provisional",
    "alias_review": "alias_identity_review_required",
    "source_group_corroborated": "source_group_only_individual_unproven",
}


def read_only(path):
    return sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)


def classify_unresolved(group_type, confidence, league_key, candidates, identity_known=False):
    """Mutually exclusive, evidence-derived triage. No nation guessing."""
    if group_type == "continental_cup_bucket":
        return "continental_bucket_needs_home_league"
    if confidence == "conflict":
        return "conflicting_domestic_evidence"
    if identity_known:
        return "game_id_identified_domestic_league_unsourced"
    if len({entry[0] for entry in candidates}) > 1:
        return "fixture_name_in_multiple_divisions"
    if candidates:
        return "unique_external_name_not_crosswalked"
    if league_key:
        return "unidentified_original_source_group"
    return "unlabelled_game_club_without_identity_evidence"


def candidate_country(candidates):
    """A country is only a REVIEW HINT when all source names agree."""
    countries = {country for _, _, country in candidates}
    return next(iter(countries)) if len(countries) == 1 else ""


def export_csv(path, columns, data):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def audit(source_database, register_database, output, *, strict=True,
          identity_review_file=None):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    identified={}
    if identity_review_file:
        payload=json.loads(Path(identity_review_file).read_text(encoding="utf-8"))
        if payload.get("version")!="historical-club-identity-disambiguation-v1":
            raise ValueError("Unrecognised historical club identity ledger")
        for row in payload["entries"]:
            if row["domestic_competition_status"]!="requires_independent_uruguayan_home_league_source":
                raise ValueError("Identity ledger cannot assign a domestic league")
            if not str(row["evidence_url"]).startswith("https://"):
                raise ValueError("Identity record has no independently reviewable evidence")
            key=(int(row["edition"]),str(row["game_club_key"]))
            if key in identified:
                raise ValueError("Duplicate game-club identity proof")
            identified[key]=row
    with read_only(source_database) as src, read_only(register_database) as reg:
        if reg.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Invalid historical competition registry SQLite")
        if reg.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Unresolved historical registry foreign keys")
        original = {
            (int(y), str(key)): (name, str(group) if group is not None else "",
                                  label or "", str(source_id) if source_id is not None else "")
            for y, key, name, group, label, source_id in src.execute(
                """SELECT c.edition,c.club_key,c.name,c.league_key,
                          l.league_name,l.source_league_id
                   FROM clubs c LEFT JOIN leagues l ON l.league_key=c.league_key""")
        }
        fixture = {
            (int(y), str(key)): dict(competition=code, fixture_club=external,
                                    method=method, source_url=url, status=status)
            for y, key, code, external, method, url, status in reg.execute(
                """SELECT edition,club_key,competition_code,fixture_club,
                          method,source_url,status FROM fixture_club_evidence""")
        }
        competitions = {
            code: dict(edition=y, country=country, tier=tier, name=name,
                       url=url)
            for code,y,country,tier,name,url in reg.execute(
                """SELECT code,edition,country,tier,name,source_url
                   FROM competition_seasons""")
        }
        group_evidence = {
            (int(y), str(key)): dict(status=status, corroborated=code or "",
                                    exact=exact, aliases=aliases)
            for y,key,code,exact,aliases,status in reg.execute(
                """SELECT edition,league_key,corroborated_competition,
                          exact_clubs,alias_candidates,status
                   FROM source_league_groups""")
        }
        ext_names = defaultdict(set)
        source_counts = Counter()
        for y,code,name in reg.execute(
                """SELECT edition,competition_code,club_name
                   FROM sourced_domestic_league_clubs"""):
            info = competitions[code]
            ext_names[(int(y),canonical(name))].add((code,name,info["country"]))
            source_counts[code] += 1
        registry_rows = list(reg.execute(
            """SELECT edition,club_key,club,original_source_league,group_type,
                      evidence_competition,confidence,career_status
               FROM edition_club_competitions
               ORDER BY edition,club_key"""))
        readiness = list(reg.execute(
            "SELECT edition,total_clubs,clubs_with_evidence,clubs_unresolved,career_ready FROM edition_readiness"))
        career_ready = reg.execute(
            "SELECT COUNT(*) FROM edition_readiness WHERE career_ready!=0").fetchone()[0]
    if career_ready:
        raise ValueError("Gap analyzer must not certify or enable careers")
    if len(original) != len(registry_rows):
        raise ValueError("FIFA source clubs and competition register disagree")
    if strict and (len(registry_rows) != 13104 or
                   {int(r[0]) for r in registry_rows} != YEARS or
                   len(competitions) < 304):
        raise ValueError("Expected original 13,104 men's clubs and full 22-edition source registry")

    details, aliases, groups = [], [], defaultdict(list)
    per_edition = defaultdict(Counter)
    reason_counts = Counter()
    confidence_counts = Counter()
    for y,key,club,label,group_type,code,confidence,career_status in registry_rows:
        y = int(y)
        key = str(key)
        record = original.get((y,key))
        if record is None or record[0] != club or record[2] != (label or ""):
            raise ValueError(f"Source club identity drift: {y}/{key}")
        original_name,league_key,_,source_league_id = record
        if career_status != "blocked":
            raise ValueError("Unverified historical club should remain blocked")
        identity=identified.get((y,key))
        if identity:
            if identity["original_display_name"] != club or (
                "id:"+identity["source_game_club_id"]+"-" not in key):
                raise ValueError("Pinned game ID or game name does not match original")
        matches = sorted(ext_names.get((y,canonical(club)), set()))
        if code is not None and code not in competitions:
            raise ValueError("Club refers to nonexistent competition season")
        if code is not None and competitions[code]["edition"] != y:
            raise ValueError("Club refers to a competition in the wrong edition")
        if identity and code and competitions[code]["country"]!=identity["country"]:
            raise ValueError("Country conflict with pinned historical game-club ID")
        if code is None:
            if confidence in KNOWN_LINKS:
                raise ValueError("Club has linked confidence without source competition")
            reason = classify_unresolved(group_type,confidence,league_key,matches,
                                         identity_known=bool(identity))
            status = "unresolved"
            action = RESOLUTION[reason]
            reason_counts[reason] += 1
        else:
            if confidence not in KNOWN_LINKS:
                raise ValueError(f"Unknown linked confidence {confidence}")
            reason = KNOWN_LINKS[confidence]
            status = "provisional_league_evidence"
            action = ("review_identity_alias" if confidence=="alias_review"
                      else "verify_individual_membership" if confidence=="source_group_corroborated"
                      else "validate_game_identity_and_movement_graph")
        country = competitions[code]["country"] if code else ""
        hint = candidate_country(matches) if not country and not identity else ""
        fixture_record = fixture.get((y,key))
        entry = {
            "Edition": y, "Source_Club_Key": key, "Club": club,
            "Original_Source_League_Key": league_key,
            "Original_Source_League_ID": source_league_id,
            "Original_Source_League_Label": label or "",
            "Original_Group_Type": group_type, "Evidence_Competition": code or "",
            "Evidence_Country": country, "Candidate_Country_Review_Only": hint,
            "Independent_Game_ID_Country": identity["country"] if identity else "",
            "Independent_Game_ID_Identity": identity["resolved_identity"] if identity else "",
            "Independent_Identity_Evidence_URL": identity["evidence_url"] if identity else "",
            "Evidence_Status": confidence, "Triage_Status": status,
            "Triage_Reason": reason, "Recommended_Action": action,
            "Candidate_Fixture_Division_Count": len({v[0] for v in matches}),
            "Candidate_Source_Names": " | ".join(sorted({v[1] for v in matches})[:10]),
            "Fixture_Identity_Method": fixture_record["method"] if fixture_record else "",
            "Fixture_Club": fixture_record["fixture_club"] if fixture_record else "",
            "Fixture_Source_URL": fixture_record["source_url"] if fixture_record else "",
            "Career_Ready": "no",
        }
        details.append(entry)
        per_edition[y][status] += 1
        per_edition[y][reason] += 1
        confidence_counts[confidence] += 1
        grp = (y,league_key or "(no original league key)")
        groups[grp].append(entry)
        if confidence == "alias_review":
            if not fixture_record or fixture_record["method"] != "alias_requires_review":
                raise ValueError("Alias review lost original fixture evidence")
            aliases.append(entry)
    count_by_edition = {int(y): (int(total),int(with_evidence),int(unresolved))
                        for y,total,with_evidence,unresolved,ready in readiness}
    for edition,c in per_edition.items():
        if edition not in count_by_edition:
            raise ValueError("Unregistered historical edition")
        total,linked,unresolved = count_by_edition[edition]
        if (c["unresolved"],c["provisional_league_evidence"],
            c["unresolved"]+c["provisional_league_evidence"]) != (unresolved,linked,total):
            raise ValueError(f"Edition {edition}: audit totals conflict with original register")

    edition_rows = []
    reason_rows = []
    for edition in sorted(per_edition):
        values=per_edition[edition]
        edition_rows.append({
            "Edition": edition, "Starting_Season": f"{edition-1}/{edition%100:02d}",
            "Source_Clubs": count_by_edition[edition][0],
            "Provisional_Evidence": values["provisional_league_evidence"],
            "Unresolved": values["unresolved"],
            "Fixture_Exact": values["individual_fixture_name_provisional"],
            "Alias_Review": values["alias_identity_review_required"],
            "Source_Group_Only": values["source_group_only_individual_unproven"],
            "Source_League_Absent": values["unlabelled_game_club_without_identity_evidence"],
            "Source_Group_Unidentified": values["unidentified_original_source_group"],
            "Continental_Cup_Bucket": values["continental_bucket_needs_home_league"],
            "Name_Collision": values["fixture_name_in_multiple_divisions"],
            "Unique_Uncrosswalked": values["unique_external_name_not_crosswalked"],
            "Conflicting_Evidence": values["conflicting_domestic_evidence"],
            "Career_Ready": "no"})
        for reason in REASONS:
            reason_rows.append({"Edition":edition,"Reason":reason,"Records":values[reason]})

    group_rows = []
    for (year,group_key),entries in groups.items():
        if not any(row["Triage_Status"] == "unresolved" for row in entries):
            continue
        group_record = group_evidence.get((year,group_key),{})
        c = Counter(row["Triage_Reason"] for row in entries if row["Triage_Status"]=="unresolved")
        countries = {row["Evidence_Country"] for row in entries if row["Evidence_Country"]}
        label_set = {row["Original_Source_League_Label"] for row in entries if row["Original_Source_League_Label"]}
        group_rows.append({
            "Edition":year, "Original_League_Key":group_key,
            "Source_League_Label":" | ".join(sorted(label_set)),
            "Source_League_ID":" | ".join(sorted({row["Original_Source_League_ID"] for row in entries
                                                     if row["Original_Source_League_ID"]})),
            "Unresolved_Club_Years":sum(c.values()),
            "Original_Group_Total_Clubs":len(entries),
            "Missing_League_Field":c["unlabelled_game_club_without_identity_evidence"],
            "Unidentified_Original_Group":c["unidentified_original_source_group"],
            "Continental_Cup_Clubs":c["continental_bucket_needs_home_league"],
            "Cross_League_Collisions":c["fixture_name_in_multiple_divisions"],
            "Source_Group_Corroboration":group_record.get("status","not_in_original_group_catalogue"),
            "Verified_Country":" | ".join(sorted(countries)) if len(countries)==1 else "",
            "Country_Status":"independent_source_evidence_only" if len(countries)==1 else "unknown",
            "Next_Action":"identify_historical_division_then_import_membership",
        })
    group_rows.sort(key=lambda x:(-x["Unresolved_Club_Years"], x["Edition"],
                                  x["Original_League_Key"]))
    labelled_groups=[g for g in group_rows
                     if g["Source_League_Label"] and
                        g["Original_League_Key"]!="(no original league key)"]
    # Repeated original source IDs are prioritisation candidates across years,
    # never a proof that two same-named football competitions are identical.
    recurring = defaultdict(list)
    for group in group_rows:
        source_id=group["Source_League_ID"]
        label=group["Source_League_Label"]
        if source_id and label:
            key=("same_source_id_and_label",source_id,label)
        else:
            key=("edition_scoped_original_group",str(group["Edition"]),
                 group["Original_League_Key"])
        recurring[key].append(group)
    recurring_rows=[]
    for key,items in recurring.items():
        recurring_rows.append({
            "Review_Grouping_Method":key[0],
            "Original_League_Source_ID":key[1] if key[0]=="same_source_id_and_label" else "",
            "Original_League_Label":items[0]["Source_League_Label"],
            "Distinct_Editions":len({x["Edition"] for x in items}),
            "Edition_List":" | ".join(str(e) for e in sorted({x["Edition"] for x in items})),
            "Total_Unresolved_Club_Years":sum(x["Unresolved_Club_Years"] for x in items),
            "Source_Group_Count":len(items),
            "Country_Assignment":"not_inferred_from_source_label_or_id",
            "Next_Action":"find_pinned_dated_domestic_source_for_each_edition",
        })
    recurring_rows.sort(key=lambda x:(-x["Total_Unresolved_Club_Years"],
                -x["Distinct_Editions"],x["Original_League_Label"]))

    uncrosswalked=[x for x in details
                   if x["Triage_Reason"]=="unique_external_name_not_crosswalked"]
    uncrosswalked.sort(key=lambda x:(x["Edition"],x["Club"],x["Source_Club_Key"]))

    country_rows=[]
    by_comp=Counter(d["Evidence_Competition"] for d in details if d["Evidence_Competition"])
    for code,info in sorted(competitions.items(),key=lambda kv:(kv[1]["edition"],kv[1]["country"],kv[1]["tier"],kv[0])):
        country_rows.append({
            "Edition":info["edition"],"Country":info["country"],
            "Tier":info["tier"],"Competition_Code":code,"Competition":info["name"],
            "External_Fixture_Teams":source_counts[code],
            "FIFA_Clubs_With_Provisional_Evidence":by_comp[code],
            "Coverage_Comment":"fixture_teams_not_proof_of_playable_squads",
            "Source_URL":info["url"],
        })

    detail_columns=list(details[0])
    export_csv(out/"HISTORICAL_COMPETITION_CLUB_TRIAGE.csv",detail_columns,details)
    export_csv(out/"HISTORICAL_COMPETITION_ALIAS_REVIEW.csv",detail_columns,aliases)
    export_csv(out/"HISTORICAL_COMPETITION_UNCROSSWALKED_NAME_REVIEW.csv",
               detail_columns,uncrosswalked)
    export_csv(out/"HISTORICAL_COMPETITION_EDITION_GAPS.csv",list(edition_rows[0]),edition_rows)
    export_csv(out/"HISTORICAL_COMPETITION_CAUSES_BY_EDITION.csv",list(reason_rows[0]),reason_rows)
    export_csv(out/"HISTORICAL_COMPETITION_SOURCE_GROUP_PRIORITY.csv",list(group_rows[0]),group_rows)
    export_csv(out/"HISTORICAL_COMPETITION_SOURCE_COVERAGE.csv",list(country_rows[0]),country_rows)
    export_csv(out/"HISTORICAL_COMPETITION_RECURRENT_SOURCE_ID_PRIORITIES.csv",
               list(recurring_rows[0]),recurring_rows)
    report = {
        "source_clubs":len(details),
        "editions":len(edition_rows),
        "independent_league_seasons":len(competitions),
        "original_source_group_review_rows":len(group_rows),
        "uncrosswalked_name_candidates":len(uncrosswalked),
        "game_id_disambiguations":len(identified),
        "recurring_group_review_rows":len(recurring_rows),
        "top_recurrent_source_groups":recurring_rows[:20],
        "source_countries":len({p["country"] for p in competitions.values()}),
        "linked_provisional_evidence":sum(x["Triage_Status"]=="provisional_league_evidence" for x in details),
        "unresolved":sum(x["Triage_Status"]=="unresolved" for x in details),
        "alias_identity_review":len(aliases),
        "reasons_unresolved":dict(sorted(reason_counts.items())),
        "all_confidence_categories":dict(sorted(confidence_counts.items())),
        "top_original_source_groups":group_rows[:20],
        "top_labelled_source_groups":labelled_groups[:30],
        "uncrosswalked_name_sample":[
            {k:x[k] for k in ("Edition","Source_Club_Key","Club",
                             "Candidate_Country_Review_Only","Candidate_Source_Names")}
            for x in uncrosswalked[:20]],
        "top_unresolved_editions":sorted(edition_rows,key=lambda x:-x["Unresolved"])[:10],
        "country_inference_policy":"ONLY direct sourced league-country matches are evidence; name-derived countries labelled review hints",
        "club_identity_policy":"unique fixture name is provisional; source-group corroboration does not prove individual club identity",
        "career_ready_editions":[],
        "production_careers_modified":False,
    }
    (out/"HISTORICAL_COMPETITION_GAP_AUDIT.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    md = [
        "# Historical competition evidence gaps — actionable source backlog",
        "",
        f"All {len(edition_rows)} FIFA/FC editions remain blocked; nothing modifies careers.",
        f"Unresolved original club-season records: **{report['unresolved']:,} / {len(details):,}**.",
        f"Linked to SOME source evidence (not certified identities): **{report['linked_provisional_evidence']:,}**.",
        f"Alias review queue (part of linked, NOT part of unresolved): **{len(aliases):,}**.",
        f"Unique external-name/crosswalk discrepancies: **{len(uncrosswalked):,}**.",
        "",
        "## Why the records are blocked",
        "",
        "| Unresolved cause | Count |", "|---|---:|",
    ]
    md += [f"| {reason.replace('_',' ')} | {count:,} |"
           for reason,count in reason_counts.most_common()]
    md += ["", "## Largest original source-group gaps (source identity retained)",
           "", "| Edition | Original league label | Club-years to resolve |",
           "|---|---|---:|"]
    md += [f"| {r['Edition']} | {r['Source_League_Label'] or '(no source league)'}"
           f" | {r['Unresolved_Club_Years']} |" for r in group_rows[:20]]
    md += [
        "", "## Largest labelled FIFA league groups requiring dated sources", "",
        "| Edition | Original league ID | Original league label | Unresolved club-years |",
        "|---|---|---|---:|",
    ]
    md += [f"| {r['Edition']} | {r['Source_League_ID'] or '(unavailable)'}"
           f" | {r['Source_League_Label']} | {r['Unresolved_Club_Years']} |"
           for r in labelled_groups[:30]]
    md += [
        "", "## Source IDs recurring across editions (REVIEW only)", "",
        "| Original FIFA source league ID | Label | Editions | Outstanding club-years |",
        "|---|---|---:|---:|",
    ]
    md += [f"| {r['Original_League_Source_ID'] or '(edition scoped)'} | "
           f"{r['Original_League_Label'] or '(unknown)'} | {r['Distinct_Editions']} "
           f"| {r['Total_Unresolved_Club_Years']} |" for r in recurring_rows[:30]]
    md += ["", "## Largest unresolved editions", "",
           "| Edition | Unresolved | Missing source league | Unidentified source group |",
           "|---|---:|---:|---:|"]
    md += [f"| {r['Edition']} | {r['Unresolved']} | {r['Source_League_Absent']} "
           f"| {r['Source_Group_Unidentified']} |" for r in
           sorted(edition_rows,key=lambda x:-x["Unresolved"])[:22]]
    md += [
        "", "## How to resolve without inventing divisions", "",
        "1. Prioritise original source-group clusters and find a dated independent domestic league membership source.",
        "2. Review the alias queue separately: source name similarity is not an officially verified PES/FIFA game club identity.",
        "3. Preserve ambiguous shared league labels (such as Premier League) using the original league key and source ID.",
        "4. Resolve continental-cup-source clubs from their home association, never the cup bucket.",
        "5. Expand feeder clubs and season-specific promotion/play-off rules independently.",
        "6. Do not issue a career-readiness certificate until the full division graph, licences and external pools are checked.",
    ]
    (out/"HISTORICAL_COMPETITION_GAP_ACTION_PLAN.md").write_text(
        "\n".join(md)+"\n",encoding="utf-8")
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True)
    parser.add_argument("--registry",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--identity-review")
    opts=parser.parse_args()
    outcome=audit(opts.source,opts.registry,opts.output,
                  identity_review_file=opts.identity_review)
    print(json.dumps(outcome,indent=2,ensure_ascii=False))
