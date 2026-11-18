import csv
import io

# Excel only reads a CSV as UTF-8 when it starts with a byte order mark.
EXCEL_BOM = chr(0xFEFF)
# Spreadsheets run a cell that starts with one of these characters as a formula.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def spreadsheet_text(value):
    return f"'{value}" if value.startswith(FORMULA_PREFIXES) else value


def results_csv(poll):
    tally = poll.tally()
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow(["Opción", "Votos", "Porcentaje"])
    for row in tally.rows:
        writer.writerow([spreadsheet_text(row.option.name), row.votes, f"{row.share:.2f}"])
    writer.writerow(["Total de votos válidos", tally.total, ""])
    return EXCEL_BOM + buffer.getvalue()
