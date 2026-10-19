"""Offline, reproducible checks for the no-user-input player data source pilot."""
import unittest

from qa_player_source_pilot import (
    sample_players, create_report, normalized_name, parse_openfootball_players,
    reference_age, CLUB_SAMPLE, FIELDS, OPENFOOTBALL_SHA,
)

class SourcePilotTests(unittest.TestCase):
    def test_exactly_100_from_6_clubs(self):
        players=sample_players()
        self.assertEqual(len(players),100)
        self.assertEqual(len({p[0] for p in players}),100)
        self.assertEqual(
            {club:sum(p[6]==club for p in players) for club,_ in CLUB_SAMPLE},
            dict(CLUB_SAMPLE),
        )

    def test_reference_date_not_current_date(self):
        self.assertEqual(reference_age("14-01-1999"),27)

    def test_unicode_and_exact_birth_identity_join(self):
        src="Marc Guehi, D, 1.82 m,  b. 13 Jul 2000 @ Abidjan\n"
        report,rows=create_report(src)
        guehi=[r for r in rows if r["player"]=="Marc Guéhi"][0]
        self.assertEqual(guehi["cc0_england_identity_match"],1)
        self.assertEqual(guehi["cc0_height_present"],1)
        self.assertEqual(guehi["identity_match_method"],
                         "exact normalised name + DOB")
        self.assertEqual(report["matched_cc0_english_ids"],1)

    def test_wrong_birth_date_never_matches(self):
        src="Marc Guehi, D, 1.82 m,  b. 14 Jul 2000 @ Abidjan\n"
        summary,rows=create_report(src)
        guehi=[r for r in rows if r["player"]=="Marc Guéhi"][0]
        self.assertEqual(guehi["cc0_england_identity_match"],0)
        self.assertEqual(summary["matched_cc0_english_ids"],0)

    def test_ambiguous_external_identity_is_not_auto_matched(self):
        line="Marc Guehi, D, 1.82 m,  b. 13 Jul 2000\n"
        summary,rows=create_report(line*2)
        self.assertEqual(summary["matched_cc0_english_ids"],0)

    def test_reference_coverage_and_unknowns_explicit(self):
        summary,rows=create_report()
        self.assertEqual(summary["sample_size"],100)
        self.assertEqual(summary["completeness"]["primary_position"]["available"],100)
        self.assertEqual(summary["completeness"]["age_at_snapshot"]["available"],100)
        self.assertEqual(summary["completeness"]["overall_present"]["available"],100)
        self.assertEqual(summary["completeness"]["six_categories_present"]["available"],100)
        for unknown in (
            "alternative_suitability_present","detailed_attributes_present",
            "potential_present","contract_end_present","weekly_wage_present",
            "transfer_status_present","personality_profile_present",
        ):
            self.assertEqual(summary["completeness"][unknown]["available"],0,unknown)
        white=[r for r in rows if r["player"] in ("Benjamin White","Ben White")]
        self.assertEqual(len(white),1)
        self.assertEqual(white[0]["alternative_roles_operator_confirmed"],1)

    def test_offline_cannot_claim_external_matches(self):
        summary,_=create_report()
        self.assertEqual(summary["source_availability"]["openfootball_england"]["status"],
                         "unavailable")
        self.assertEqual(summary["matched_cc0_english_ids"],0)

    def test_field_coverage_schema_complete(self):
        _,rows=create_report()
        self.assertEqual(len(rows),100)
        self.assertTrue(all(set(row)==set(FIELDS) for row in rows))
        self.assertEqual(len(OPENFOOTBALL_SHA),40)
        self.assertEqual(normalized_name("Joško Gvardiol"),"joskogvardiol")

    def test_openfootball_parser_rejects_non_player_content(self):
        records=parse_openfootball_players("= England\nThis is not a player\n")
        self.assertEqual(records,{})


if __name__=="__main__":
    unittest.main()
