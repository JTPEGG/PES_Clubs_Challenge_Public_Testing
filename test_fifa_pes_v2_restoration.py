"""Offline tests for isolated 2015–2020 restored-source candidate build."""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from scripts.build_fifa_fc_restored_2015_2020 import (
    ROOT, YEARS, build, inspect_csv, source_url, SOURCE_STATUS,
)

HEADER = ("sofifa_id", "short_name", "long_name", "dob", "nationality",
          "overall", "player_positions", "skill_ball_control",
          "skill_dribbling", "attacking_short_passing",
          "movement_sprint_speed", "goalkeeping_reflexes")


def sample(rows=210, *, duplicate_id=False, bad_position=False):
    buffer = io.StringIO(newline="")
    w = csv.DictWriter(buffer, fieldnames=HEADER)
    w.writeheader()
    for i in range(rows):
        w.writerow({
            "sofifa_id": 1 if duplicate_id else i + 100,
            "short_name": f"Player {i}",
            "long_name": f"Test Player {i}",
            "dob": "1988-02-04",
            "nationality": "England",
            "overall": 72,
            "player_positions": "" if bad_position else
                                ("GK" if i < 120 else "ST, CF"),
            "skill_ball_control": 65,
            "skill_dribbling": 64,
            "attacking_short_passing": 62,
            "movement_sprint_speed": 70,
            "goalkeeping_reflexes": 72,
        })
    return buffer.getvalue().encode("utf-8")


class RestoredSourceTests(unittest.TestCase):
    def test_each_edition_has_pinned_source_and_fc25_is_unavailable(self):
        urls = [source_url(y) for y in YEARS]
        self.assertEqual(len(urls), 6)
        self.assertTrue(all("/66fc78145ff32ea2dea839459e247833856e0f47/" in x
                            for x in urls))
        with self.assertRaises(ValueError):
            source_url(2025)

    def test_strict_role_id_and_minimum_coverage(self):
        result = inspect_csv(sample(), 2020, 150)
        self.assertEqual(result["player_rows"], 210)
        self.assertEqual(result["source_goalkeepers"], 120)
        with self.assertRaises(ValueError):
            inspect_csv(sample(), 2020, 210)
        with self.assertRaises(ValueError):
            inspect_csv(sample(duplicate_id=True), 2020, 150)
        with self.assertRaises(ValueError):
            inspect_csv(sample(bad_position=True), 2020, 150)

    def test_restored_zip_does_not_mutate_original_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            base, output = Path(folder) / "original.zip", Path(folder) / "restored.zip"
            manifest = {"downloads": [
                {"edition": y, "player_rows": 150, "status": "DOWNLOADED",
                 "source_url": f"https://example.com/old/{y}.csv",
                 "sha256": f"old-{y}"}
                for y in YEARS
            ]}
            with ZipFile(base, "w") as z:
                z.writestr("original/MANIFEST.json", json.dumps(manifest))
                z.writestr("original/data/source.csv", b"source data never changed")
            first = base.read_bytes()
            with patch("scripts.build_fifa_fc_restored_2015_2020.download",
                       side_effect=lambda year: sample()):
                result = build(output, base)
            self.assertEqual(first, base.read_bytes())
            self.assertEqual(result["status"], SOURCE_STATUS)
            self.assertEqual(result["source_rows_six_years"], 1260)
            self.assertEqual(result["original_rows_six_years"], 900)
            self.assertFalse(result["converter_source_automatically_replaced"])
            with ZipFile(output) as z:
                for year in YEARS:
                    self.assertEqual(
                        z.read(f"{ROOT}/data/{year}_sofifa.csv"), sample())
                self.assertIn(f"{ROOT}/MANIFEST.json", z.namelist())
                self.assertNotIn(f"{ROOT}/data/2025_sofifa.csv", z.namelist())


if __name__ == "__main__":
    unittest.main()
