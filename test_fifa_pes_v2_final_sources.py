"""Safety tests for the final 22-year mixed-provider V2 source archive."""
import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.assemble_fifa_pes_v2_final_sources import (
    create_combined, overlap_report, REQUIRED, RESTORED
)
from scripts.export_fifa_pes_v2 import source_members


def sample(prefix, *, restored=False):
    buff=io.StringIO(newline="")
    if restored:
        names=("sofifa_id","short_name","long_name","dob","nationality",
               "overall","player_positions")
        w=csv.DictWriter(buff,fieldnames=names)
        w.writeheader()
        for i in range(3):
            w.writerow({"sofifa_id":i+1,"short_name":prefix+str(i),
                "long_name":"Test Player" if i==0 else prefix+str(i),
                "dob":"1990-04-01","nationality":"England","overall":"70",
                "player_positions":"GK"})
    else:
        names=("player_id","name","birthdate","nationality","rating",
               "preferred_positions")
        w=csv.DictWriter(buff,fieldnames=names)
        w.writeheader()
        for i in range(2):
            w.writerow({"player_id":i+1,"name":"Test Player" if i==0 else prefix+str(i),
                "birthdate":"1990-04-01","nationality":"England","rating":"70",
                "preferred_positions":"GK"})
    return buff.getvalue().encode("utf-8")


class FullArchiveTests(unittest.TestCase):
    def test_cross_provider_identity_does_not_merge_rows(self):
        common=overlap_report(sample("Old"),sample("New",restored=True))
        self.assertEqual(common["unique_name_dob_nationality_candidate_matches"],1)
        self.assertFalse(common["cross_provider_id_linkage_verified"])
        self.assertTrue(common["player_rows_not_automatically_union_merged"])

    def test_22_unique_years_source_bytes_checksum_and_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            old,restored,output=(base/"original.zip",base/"restored.zip",
                                 base/"ready.zip")
            first=[]
            with ZipFile(old,"w") as z:
                for year in range(2005,2028):
                    data=sample("Old"+str(year))
                    name=f"fifa_fc/data/{year}_original.csv"
                    z.writestr(name,data)
                    first.append({"edition":year,"status":"DOWNLOADED",
                        "player_rows":2,"source_url":"https://example.org/old.csv",
                        "catalog_source":"historical_legacy",
                        "sha256":hashlib.sha256(data).hexdigest()})
                z.writestr("fifa_fc/MANIFEST.json",json.dumps({"downloads":first}))
            newer={}
            with ZipFile(restored,"w") as z:
                for year in sorted(RESTORED):
                    data=sample("New"+str(year),restored=True)
                    z.writestr(f"fifa_restored/data/{year}_sofifa.csv",data)
                    newer[str(year)]={"player_rows":3,
                        "sha256":hashlib.sha256(data).hexdigest(),
                        "source_url":"https://example.org/sofifa.csv"}
                z.writestr("fifa_restored/MANIFEST.json",json.dumps({
                    "source_repository":"independent/SoFIFA","editions":newer}))
            old_before=old.read_bytes()
            restored_before=restored.read_bytes()
            result=create_combined(old,restored,output)
            self.assertEqual(result["editions_expected"],22)
            self.assertEqual(result["source_rows"],22*2+6)
            self.assertEqual(result["six_restored_source_rows"],18)
            self.assertEqual(old_before,old.read_bytes())
            self.assertEqual(restored_before,restored.read_bytes())
            with ZipFile(output) as z:
                members=source_members(z)
                self.assertEqual(set(members),REQUIRED)
                self.assertNotIn(2025,members)
                for year in REQUIRED:
                    expected=sample("New"+str(year),restored=True) if year in RESTORED else sample("Old"+str(year))
                    self.assertEqual(z.read(members[year]),expected)
                m=json.loads(z.read("fifa_to_pes_v2_selected_full_sources/MANIFEST.json"))
                self.assertTrue(m["no_cross_provider_id_merges"])
                self.assertFalse(m["player_roster_coverage_not_independently_verified"] is False)
                for year in RESTORED:
                    self.assertEqual(m["provider_crosswalk_quality_review"][str(year)]
                        ["unique_name_dob_nationality_candidate_matches"],1)


if __name__=="__main__":
    unittest.main()
