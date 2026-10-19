from __future__ import annotations

import json
import urllib.parse

from .models import Fetch, Response


CDX_URL = "https://web.archive.org/cdx/search/cdx"


def is_cloudflare_challenge(response: Response) -> bool:
    return response.status == 403 and "Just a moment" in response.text
# end def


def latest_snapshot_url(url: str, fetch: Fetch) -> tuple[str, str] | None:
    query = urllib.parse.urlencode(
        {
            "url": url,
            "output": "json",
            "filter": ["statuscode:200", "mimetype:text/html"],
            "fl": "timestamp,original,statuscode",
            "limit": "1",
            "sort": "reverse",
        },
        doseq=True,
    )
    response = fetch(f"{CDX_URL}?{query}")
    if response.status != 200:
        return None
    # end if
    try:
        rows = json.loads(response.text)
        timestamp = rows[1][0]
    except (IndexError, TypeError, json.JSONDecodeError):
        return None
    # end try
    if not isinstance(timestamp, str) or not timestamp.isdigit():
        return None
    # end if
    return timestamp, f"https://web.archive.org/web/{timestamp}id_/{url}"
# end def
