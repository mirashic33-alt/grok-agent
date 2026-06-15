"""
billing.py — xAI Management API: real-time prepaid balance.

Endpoint: GET https://management-api.x.ai/v1/billing/teams/{team_id}/postpaid/invoice/preview
Auth:     Management API Key (NOT the inference key)
"""

import json
import urllib.request
import data.keystore as keystore
import data.logger as logger

_log = logger.get_logger("billing")

_BASE = "https://management-api.x.ai"


def fetch_balance() -> dict | None:
    """
    Returns {"remaining": float, "deposited": float, "spent": float, "lines": list}
    or None on failure. All amounts in USD.
    """
    mgmt_key = keystore.get("MGMT_API_KEY")
    team_id = keystore.get("TEAM_ID")
    if not mgmt_key or not team_id:
        _log.debug("billing: MGMT_API_KEY or TEAM_ID not set")
        return None

    url = f"{_BASE}/v1/billing/teams/{team_id}/postpaid/invoice/preview"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {mgmt_key}",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        inv = data.get("coreInvoice", {})
        deposited = abs(int(inv.get("prepaidCredits", {}).get("val", 0)))
        used      = abs(int(inv.get("prepaidCreditsUsed", {}).get("val", 0)))
        spent     = int(inv.get("totalWithCorr", {}).get("val", 0))
        remaining = deposited - used

        result = {
            "remaining": remaining / 100.0,
            "deposited": deposited / 100.0,
            "spent":     spent / 100.0,
            "lines":     inv.get("lines", []),
        }
        _log.debug(f"billing: ${result['remaining']:.2f} remaining "
                   f"(${result['deposited']:.2f} - ${result['spent']:.2f})")
        return result
    except Exception as e:
        _log.warning(f"billing fetch failed: {e}")
        return None
