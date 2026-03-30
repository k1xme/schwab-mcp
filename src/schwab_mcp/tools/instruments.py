# src/schwab_mcp/tools/instruments.py
import logging
from schwab_mcp._mcp import mcp
from schwab_mcp.client import get_schwab_client
from schwab_mcp.tools._response import _ok_or_error

logger = logging.getLogger("schwab_mcp.tools.instruments")


@mcp.tool()
def search_instruments(symbol: str, projection: str) -> str:
    """Search for instruments by symbol or description.

    Args:
        symbol: Symbol or search string, e.g. "AAPL".
        projection: Search type:
            "symbol-search" — exact symbol lookup,
            "symbol-regex" — regex pattern on symbol,
            "desc-search" — keyword search in description,
            "desc-regex" — regex on description,
            "search" — search by symbol or description,
            "fundamental" — return fundamental data for the exact symbol.
    """
    logger.info("search_instruments called, symbol=%s, projection=%s", symbol, projection)
    client = get_schwab_client()
    resp = client.instruments(symbol, projection)
    return _ok_or_error(resp)


@mcp.tool()
def get_instrument(cusip: str) -> str:
    """Get instrument details by CUSIP identifier.

    Args:
        cusip: 9-character CUSIP identifier (e.g. "037833100" for Apple Inc.).
    """
    logger.info("get_instrument called, cusip=%s", cusip)
    client = get_schwab_client()
    resp = client.instrument_cusip(cusip)
    return _ok_or_error(resp)
