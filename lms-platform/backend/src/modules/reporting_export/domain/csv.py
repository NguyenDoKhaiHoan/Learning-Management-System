"""CSV transport with UTF-8 BOM and safe spreadsheet text cells."""

import csv
from datetime import datetime
from io import StringIO


def csv_bytes(columns, rows):
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        values = []
        for column in columns:
            value = row.get(column)
            if isinstance(value, datetime):
                value = value.isoformat() + ("Z" if value.tzinfo is None else "")
            if isinstance(value, str) and (
                value.lstrip().startswith(("=", "+", "-", "@"))
                or value.startswith(("\t", "\r", "\n"))
            ):
                value = "'" + value
            values.append("" if value is None else value)
        writer.writerow(values)
    return output.getvalue().encode("utf-8-sig")
