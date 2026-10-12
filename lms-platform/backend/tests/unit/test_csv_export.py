"""CSV must round-trip text while neutralizing spreadsheet formulas."""

import csv
from decimal import Decimal
from io import StringIO

from src.modules.reporting_export.domain.csv import csv_bytes


def test_csv_formula_controls_unicode_quotes_null_and_numeric_values():
    cells = [
        "=SUM(A1:A2)",
        " +cmd",
        "-cmd",
        "@SUM(1)",
        "\ttext",
        "\rtext",
        "\ntext",
        'Tiếng Việt, "quoted"\nline',
        None,
        Decimal("-1.25"),
    ]
    encoded = csv_bytes(["value"], [{"value": v} for v in cells])
    assert encoded.startswith(b"\xef\xbb\xbf")
    decoded = list(csv.reader(StringIO(encoded.decode("utf-8-sig"))))
    assert [r[0] for r in decoded[1 : 7 + 1]] == ["'" + v for v in cells[:7]]
    assert [r[0] for r in decoded[8:]] == [cells[7], "", "-1.25"]
