import csv
import io

from starlette.responses import StreamingResponse


def make_csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    """Return a StreamingResponse containing CSV data for the given rows."""
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
