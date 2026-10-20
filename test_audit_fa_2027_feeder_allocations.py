import json,tempfile,csv,unittest
from pathlib import Path
from scripts.audit_fa_2027_feeder_allocations import audit,key

class FAMensFeederReviewTests(unittest.TestCase):
 def test_source_allocation_has_unique_72_mens_clubs(self):
  p=Path("data/warehouse/england_nls_2027_official_step_1_2_allocations.json")
  doc=json.loads(p.read_text())
  self.assertEqual(doc["edition"],2027)
  self.assertEqual(sum(len(x["clubs"]) for x in doc["divisions"]),72)
  self.assertEqual(len({key(x) for d in doc["divisions"] for x in d["clubs"]}),72)
  self.assertEqual(key("AFC Telford United"),key("AFC Telford"))
  self.assertEqual(key("Scarborough Athletic"),key("Scarborough"))
 def test_reject_missing_source_north_south_allocation(self):
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder)
   csv_path=d/"bad.csv"
   csv_path.write_text("Edition,League_Code,Evidence_Status,Fixture_Club\n")
   with self.assertRaises(ValueError):
    audit("data/warehouse/england_nls_2027_official_step_1_2_allocations.json",
          csv_path,d/"out")

if __name__=="__main__":unittest.main()
