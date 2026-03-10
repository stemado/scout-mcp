"""SpreadsheetML 2003 XML to CSV converter.

Handles .xls files that are actually XML SpreadsheetML (Excel 2003 XML format).
These are commonly served by enterprise web portals with application/excel MIME type
and .xls extension, but contain XML markup instead of binary BIFF data.

Identified by: <?mso-application progid="Excel.Sheet"?> processing instruction
and the urn:schemas-microsoft-com:office:spreadsheet namespace.
"""

from __future__ import annotations

import csv
import os

import defusedxml.ElementTree as ET

from scout.converters import register

_SS_NS = "urn:schemas-microsoft-com:office:spreadsheet"
_NS = {"ss": _SS_NS}


@register("spreadsheetml_2003", "csv")
def spreadsheetml_to_csv(source_path: str) -> str:
    """Convert a SpreadsheetML 2003 XML file to CSV.

    Args:
        source_path: Absolute path to the .xls (SpreadsheetML) file.

    Returns:
        Absolute path to the generated .csv file (same directory, .csv extension).
    """
    tree = ET.parse(source_path)
    root = tree.getroot()

    table = root.find(f".//{{{_SS_NS}}}Table")
    if table is None:
        raise ValueError(f"No <Table> element found in {source_path}")

    rows = table.findall(f"{{{_SS_NS}}}Row")
    if not rows:
        raise ValueError(f"No <Row> elements found in {source_path}")

    # Determine output path
    base, _ = os.path.splitext(source_path)
    output_path = base + ".csv"

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in rows:
            cells = row.findall(f"{{{_SS_NS}}}Cell")
            csv_row: list[str] = []
            col_index = 0

            for cell in cells:
                # Handle ss:Index for sparse columns (1-based in the XML)
                explicit_index = cell.get(f"{{{_SS_NS}}}Index")
                if explicit_index is not None:
                    target = int(explicit_index) - 1
                    # Pad with empty strings up to the target column
                    while col_index < target:
                        csv_row.append("")
                        col_index += 1

                data = cell.find(f"{{{_SS_NS}}}Data")
                csv_row.append(data.text if data is not None and data.text else "")
                col_index += 1

                # Handle ss:MergeAcross (merged cells span multiple columns)
                merge_across = cell.get(f"{{{_SS_NS}}}MergeAcross")
                if merge_across is not None:
                    for _ in range(int(merge_across)):
                        csv_row.append("")
                        col_index += 1

            writer.writerow(csv_row)

    return output_path
