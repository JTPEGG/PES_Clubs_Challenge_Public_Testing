"""Regression tests for the immutable V2 historical wage/contract/loan audit."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.audit_fifa_pes_v2_contract_sources import (
    _columns, audit, column_category, parse_amount, present, YEARS
)


class ContractCoverageTests(unittest.TestCase):
    def test_amount_parsing_preserves_currency_and_does_not_infer_weekly(self):
        self.assertEqual(parse_amount("€120K"),120000)
        self.assertEqual(parse_amount("£2,500"),2500)
        self.assertEqual(parse_amount("900"),900)
        self.assertEqual(parse_amount("$1.5M"),1500000)
        self.assertIsNone(parse_amount("N/A"))
        self.assertIsNone(parse_amount("Not disclosed"))
        self.assertFalse(present("nan"))
        self.assertTrue(present("0"))

    def test_loan_and_contract_source_columns_detected(self):
        with tempfile.TemporaryDirectory() as d:
            z=Path(d)/"test.zip"
            with ZipFile(z,"w") as out:
                out.writestr("data.csv",
                   "sofifa_id,club_name,wage_eur,contract_valid_until,club_loaned_from,loan_end_date\n"
                   "13,Cardiff City,€10K,2021,Manchester City,2020-06-30\n"
                   "14,Manchester City,N/A,,,\n")
            with ZipFile(z) as stream:
                report=_columns(stream,"data.csv")
            self.assertEqual(report["rows"],2)
            self.assertEqual(report["loan_parent_rows"],1)
            self.assertEqual(report["fields"]["wage_eur"]["present"],1)
            self.assertEqual(report["fields"]["wage_eur"]["parseable_amount"],1)
            self.assertEqual(report["loan_end_fields"],["loan_end_date"])
            self.assertIn("contract",column_category("contract_valid_until"))
            self.assertEqual(YEARS.__len__(),22)


if __name__=="__main__":
    unittest.main()
