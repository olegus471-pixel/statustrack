"""
Client for the AIMA case-tracking API.

Confirmed endpoint (from the site's own Network tab):
    GET https://api-contactenos.aima.gov.pt/api/FormTracking/{tracking_id}

Nothing else needs to be configured. The API_URL_TEMPLATE / API_METHOD env
vars below only exist as an escape hatch in case AIMA ever changes their
endpoint - normal use requires no configuration at all.
"""

import os
import re
import httpx

API_URL_TEMPLATE = os.getenv(
    "API_URL_TEMPLATE",
    "https://api-contactenos.aima.gov.pt/api/FormTracking/{tracking_id}",
)
API_METHOD = os.getenv("API_METHOD", "GET").upper()
POST_BODY_KEY = os.getenv("API_POST_BODY_KEY", "id")

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class TrackingNotFound(Exception):
    pass


class TrackingApiError(Exception):
    pass


def extract_tracking_id(text: str) -> str | None:
    """Pull the UUID out of either a full tracking URL or a bare UUID."""
    match = UUID_RE.search(text.strip())
    return match.group(0) if match else None


async def fetch_case_status(tracking_id: str, timeout: int = 15) -> dict:
    """
    Returns a dict with the fields we care about:
        {
            "encontrado": bool,
            "numero_processo": str,
            "tipo": str,          # e.g. "Deferido"
            "label_pt": str,      # e.g. "Decisão final – Deferido"
            "label_en": str,
            "descricao_pt": str,
            "descricao_en": str,
            "acao_pt": str,
            "acao_en": str,
            "data_criacao": str,  # ISO date of this status step
        }
    Raises TrackingNotFound if the case id is invalid/unknown,
    or TrackingApiError on network/parse failures.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        try:
            if API_METHOD == "POST":
                resp = await client.post(API_URL_TEMPLATE, json={POST_BODY_KEY: tracking_id})
            else:
                url = API_URL_TEMPLATE.format(tracking_id=tracking_id)
                resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as e:
            raise TrackingApiError(f"HTTP error while calling AIMA API: {e}") from e
        except ValueError as e:
            raise TrackingApiError(f"Could not parse JSON response: {e}") from e

    if not payload.get("success", True):
        raise TrackingApiError(payload.get("error") or "API returned success=false")

    data = payload.get("result", {}).get("data", {})
    if not data.get("encontrado", False):
        raise TrackingNotFound("Case not found for this tracking id")

    historico = data.get("historico", [])
    current = next((h for h in historico if h.get("estadoAtual")), None)
    if current is None:
        raise TrackingApiError("No entry with estadoAtual=true in historico")

    return {
        "encontrado": True,
        "numero_processo": data.get("numeroProcessoMascarado", ""),
        "tipo": current.get("tipo", ""),
        "label_pt": current.get("labelPt", ""),
        "label_en": current.get("labelEn", ""),
        "descricao_pt": current.get("descricaoPt", ""),
        "descricao_en": current.get("descricaoEn", ""),
        "acao_pt": data.get("acaoPt", ""),
        "acao_en": data.get("acaoEn", ""),
        "data_criacao": current.get("dataCriacao", ""),
    }
