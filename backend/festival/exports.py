import csv
import io

# Excel only reads a CSV as UTF-8 when it starts with a byte order mark.
EXCEL_BOM = chr(0xFEFF)


def results_csv(poll):
    tally = poll.tally()
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow(["Opción", "Votos", "Porcentaje"])
    for row in tally.rows:
        writer.writerow([row.option.name, row.votes, f"{row.share:.2f}"])
    writer.writerow(["Total de votos válidos", tally.total, ""])
    return EXCEL_BOM + buffer.getvalue()
