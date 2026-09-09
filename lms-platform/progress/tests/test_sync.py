import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "sync.py"
spec = importlib.util.spec_from_file_location("progress_sync", path)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.task = {"wbs":"1.10", "title":"Test", "sheet_titles":["Test"],
                     "status":"Đã hoàn thành", "progress":1,
                     "evidence":"Tests passed", "verified_at":"2026-09-07"}

    def test_row_mapping_preserves_other_columns(self):
        changes = sync.plan_updates(
            [["1.1","Other"], ["1.10","Test","Owner",2,"deadline","Chưa thực hiện",0]],
            [self.task], "Plan", 3)
        self.assertEqual(changes[0]["range"], "'Plan'!F4:G4")
        self.assertEqual(changes[0]["new"], ["Đã hoàn thành",1])

    def test_matching_values_no_write(self):
        self.assertEqual(sync.plan_updates(
            [["1.10","Test","",0,"","Đã hoàn thành",1]], [self.task],"Plan",3), [])

    def test_refuses_missing_duplicate_mismatch_and_formula(self):
        cases = [[], [["1.10","Test"],["1.10","Test"]], [["1.10","Wrong"]],
                 [["1.10","Test","","","","=SUM(A1:A2)",0]]]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                sync.plan_updates(rows,[self.task],"Plan",3)

    def test_validate_status_and_evidence(self):
        sync.validate_tasks([self.task])
        for change in [{"progress":0},{"evidence":""},{"progress":2}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                sync.validate_tasks([{**self.task,**change}])

    def test_real_task_file(self):
        tasks = sync.read_json(path.parent / "tasks.json")["tasks"]
        sync.validate_tasks(tasks)
        self.assertEqual(len(tasks),15)


if __name__ == "__main__":
    unittest.main()
