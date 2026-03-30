# src/schwab_mcp/tools/market_data.py
import json
import logging
from schwab_mcp._mcp import mcp
from schwab_mcp.client import get_schwab_client
from schwab_mcp.tools._response import _ok_or_error, _maybe_write_to_file, _write_to_file

logger = logging.getLogger("schwab_mcp.tools.market_data")


@mcp.tool()
def get_quotes(
    symbols: list[str],
    fields: str | None = None,
    indicative: bool = False,
) -> str:
    """Get real-time quotes for one or more symbols.

    Returns bid/ask, last price, volume, fundamentals, and extended-hours data.

    Args:
        symbols: List of ticker symbols, e.g. ["AAPL", "MSFT", "SPY"].
            Also accepts a comma-separated string: "AAPL,AMD".
        fields: Quote field filter: "all" (default), "quote", "fundamental".
        indicative: Set True for indicative (non-tradable) quotes. Default False.
    """
    logger.info("get_quotes called for %d symbols", len(symbols))
    client = get_schwab_client()
    resp = client.quotes(symbols, fields=fields, indicative=indicative)
    if not resp.ok:
        return f"Error ({resp.status_code}): {resp.text}"
    try:
        data = resp.json()
    except Exception:
        return resp.text
    if isinstance(data, dict) and data:
        keys = list(data.keys())
        count = len(keys)
        first = keys[0]
        context = f"{first}+{count - 1}more" if count > 1 else first
        filed = _maybe_write_to_file("quotes", context, data, count, threshold=5, noun="quotes")
        if filed:
            return filed
    return json.dumps(data, indent=2)


@mcp.tool()
def get_option_chain(
    symbol: str,
    contract_type: str | None = None,
    strike_count: int | None = None,
    include_underlying_quote: bool | None = None,
    strategy: str | None = None,
    interval: float | None = None,
    strike: float | None = None,
    range: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    volatility: float | None = None,
    underlying_price: float | None = None,
    interest_rate: float | None = None,
    days_to_expiration: int | None = None,
    exp_month: str | None = None,
    option_type: str | None = None,
    entitlement: str | None = None,
) -> str:
    """Get the option chain for a symbol with extensive filtering.

    Call get_option_expirations first to see available expiration dates.

    Args:
        symbol: Underlying symbol, e.g. "AAPL" or "$SPX".
        contract_type: "CALL", "PUT", or "ALL" (default "ALL").
        strike_count: Number of strikes above and below at-the-money to return.
        include_underlying_quote: Include underlying stock quote in response.
        strategy: "SINGLE" (default), "ANALYTICAL", "COVERED", "VERTICAL",
            "CALENDAR", "STRANGLE", "STRADDLE", "BUTTERFLY", "CONDOR",
            "DIAGONAL", "COLLAR", "ROLL".
        interval: Strike interval for spread strategies.
        strike: Specific strike price filter.
        range: "ITM", "NTM", "OTM", "SAK", "SBK", "SNK", "ALL".
        from_date: Start expiration date "YYYY-MM-DD". Not earlier than today.
        to_date: End expiration date "YYYY-MM-DD".
        volatility: Implied volatility override (for ANALYTICAL strategy).
        underlying_price: Underlying price override (for ANALYTICAL strategy).
        interest_rate: Interest rate override (for ANALYTICAL strategy).
        days_to_expiration: Days to expiration override (for ANALYTICAL strategy).
        exp_month: "JAN" through "DEC", or "ALL".
        option_type: "S" (standard), "NS" (non-standard), "ALL".
        entitlement: "PN" (PayingPro), "NP" (NonPro), "PP" (NonPayingPro).
    """
    logger.info("get_option_chain called for %s", symbol)
    client = get_schwab_client()
    resp = client.option_chains(
        symbol,
        contractType=contract_type,
        strikeCount=strike_count,
        includeUnderlyingQuote=include_underlying_quote,
        strategy=strategy,
        interval=interval,
        strike=strike,
        range=range,
        fromDate=from_date,
        toDate=to_date,
        volatility=volatility,
        underlyingPrice=underlying_price,
        interestRate=interest_rate,
        daysToExpiration=days_to_expiration,
        expMonth=exp_month,
        optionType=option_type,
        entitlement=entitlement,
    )
    if not resp.ok:
        return f"Error ({resp.status_code}): {resp.text}"
    try:
        data = resp.json()
    except Exception:
        return resp.text
    # Option chains always write to file
    filepath = _write_to_file("option-chain", symbol, data)
    return f"Option chain for {symbol} written to {filepath}"


@mcp.tool()
def get_option_expirations(symbol: str) -> str:
    """Get all available option expiration dates for a symbol.

    Call this before get_option_chain to see what expirations are available.

    Args:
        symbol: Underlying equity symbol, e.g. "AAPL".
    """
    logger.info("get_option_expirations called for %s", symbol)
    client = get_schwab_client()
    resp = client.option_expiration_chain(symbol)
    return _ok_or_error(resp)


@mcp.tool()
def get_price_history(
    symbol: str,
    period_type: str | None = None,
    period: int | None = None,
    frequency_type: str | None = None,
    frequency: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    need_extended_hours_data: bool | None = None,
    need_previous_close: bool | None = None,
) -> str:
    """Get OHLCV candle data for a symbol.

    Valid period/frequency combinations:
      periodType "day": period 1-5,10 (default 10); frequencyType "minute"; frequency 1,5,10,15,30
      periodType "month": period 1,2,3,6 (default 1); frequencyType "daily","weekly"; frequency 1
      periodType "year": period 1,2,3,5,10,15,20 (default 1); frequencyType "daily","weekly","monthly"; frequency 1
      periodType "ytd": period 1 (default 1); frequencyType "daily","weekly"; frequency 1

    Args:
        symbol: Equity or index symbol, e.g. "AAPL".
        period_type: "day", "month", "year", "ytd".
        period: Number of periods (varies by period_type, see above).
        frequency_type: "minute", "daily", "weekly", "monthly".
        frequency: Frequency interval (1,5,10,15,30 for minute; 1 for others).
        start_date: Start datetime or UNIX epoch ms; overrides period when set.
        end_date: End datetime or UNIX epoch ms.
        need_extended_hours_data: Include pre/post-market candles.
        need_previous_close: Include previous close price in response.
    """
    logger.info("get_price_history called for %s", symbol)
    client = get_schwab_client()
    resp = client.price_history(
        symbol,
        periodType=period_type,
        period=period,
        frequencyType=frequency_type,
        frequency=frequency,
        startDate=start_date,
        endDate=end_date,
        needExtendedHoursData=need_extended_hours_data,
        needPreviousClose=need_previous_close,
    )
    if not resp.ok:
        return f"Error ({resp.status_code}): {resp.text}"
    try:
        data = resp.json()
    except Exception:
        return resp.text
    candles = data.get("candles", [])
    context = f"{symbol}-{frequency_type}" if frequency_type else symbol
    filed = _maybe_write_to_file("price-history", context, data, len(candles), threshold=20, noun="candles")
    if filed:
        return filed
    return json.dumps(data, indent=2)


@mcp.tool()
def get_movers(
    index: str,
    sort: str | None = None,
    frequency: int | None = None,
) -> str:
    """Get top movers within an index or universe.

    Args:
        index: "$DJI" (Dow), "$COMPX" (NASDAQ Composite), "$SPX" (S&P 500),
            "NYSE", "NASDAQ", "OTCBB", "INDEX_ALL", "EQUITY_ALL",
            "OPTION_ALL", "OPTION_PUT", "OPTION_CALL".
        sort: "VOLUME", "TRADES", "PERCENT_CHANGE_UP", "PERCENT_CHANGE_DOWN".
        frequency: 0 (default, all day), 1, 5, 10, 30, 60 (minutes).
    """
    logger.info("get_movers called for index=%s", index)
    client = get_schwab_client()
    resp = client.movers(index, sort=sort, frequency=frequency)
    return _ok_or_error(resp)


@mcp.tool()
def get_market_hours(
    markets: list[str],
    date: str | None = None,
) -> str:
    """Get trading session hours for one or more markets.

    Returns pre-market, regular, and post-market session times.

    Args:
        markets: List of market types: "equity", "option", "bond",
            "future", "forex".
        date: Date in "YYYY-MM-DD" format; defaults to today.
    """
    logger.info("get_market_hours called for %s", markets)
    client = get_schwab_client()
    resp = client.market_hours(markets, date=date)
    return _ok_or_error(resp)
