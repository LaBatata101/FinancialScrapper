import csv
from io import BytesIO, StringIO

from app.db.models import AUMSnapshot


async def generate_csv_report(snapshots: list[AUMSnapshot]) -> BytesIO:
    buffer = StringIO()
    csv_writer = csv.writer(buffer)

    headers = ["Empresa", "AUM Value", "AUM Unit", "Standardized Value", "Source URL", "Extraction Date"]
    csv_writer.writerow(headers)

    for snap in snapshots:
        row = [
            snap.company.name,
            snap.aum_value,
            snap.aum_unit,
            snap.standardized_value,
            snap.source_url,
            snap.extracted_at.strftime("%Y-%m-%d %H:%M:%S"),
        ]
        csv_writer.writerow(row)

    bytes_buffer = BytesIO(buffer.getvalue().encode())
    buffer.close()

    return bytes_buffer
