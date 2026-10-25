from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class SqlContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analytics = "\n".join(
            path.read_text(encoding="utf-8").upper()
            for path in sorted((ROOT / "sql" / "analytics").glob("*.sql"))
        )
        cls.ddl = "\n".join(
            path.read_text(encoding="utf-8").upper()
            for path in sorted((ROOT / "sql" / "ddl").glob("*.sql"))
        )

    def test_required_analytical_sql_is_present(self):
        for token in (
            "DENSE_RANK()",
            "LAG(",
            "FULL OUTER JOIN",
            "PERCENTILE_CONT(",
            "EXPLAIN (ANALYZE",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.analytics)

    def test_required_schemas_are_present(self):
        for schema in ("AUDIT", "RAW", "STG", "DWH", "MART"):
            with self.subTest(schema=schema):
                self.assertIn("SCHEMA IF NOT EXISTS {}".format(schema), self.ddl)

    def test_salary_constraint_is_present(self):
        self.assertIn("SALARY_FROM <= SALARY_TO", self.ddl)


if __name__ == "__main__":
    unittest.main()
