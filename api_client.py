import requests
import config

# --- JSON de prueba para simulación local ---
#MOCK_DEXSCREENER_RESPONSE = {
#    "schemaVersion": "1.0.0",
#    "pairs": [
#        {
#            "chainId": "solana",
#            "dexId": "raydium",
#            "url": "https://dexscreener.com/solana/dk1aepmbe5xcba25weburjlnffyusnaxajkf2h6z2tmy",
#            "pairAddress": "DK1Aepmbe5XCBa25WebUrJlnffYUSNAxAjKF2H6Z2tmy",
#            "baseToken": {
#                "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzL7_qrN5L3n3g",
#                "name": "dogwifhat",
#                "symbol": "WIF"
#            },
#            "quoteToken": {
#                "symbol": "SOL"
#            },
#            "priceNative": "0.0125",
#            "priceUsd": "1.75",
#            "fdv": 1748017320,
#            "volume": { "h24": 50123456 },
#            "priceChange": { "h24": -5.7 }
#        }
#    ]
#}

def format_large_number(num: float) -> str:
    if num is None: return "N/A"
    try:
        num = float(num)
    except (ValueError, TypeError):
        return "N/A"
    if num < 1_000: return f"{num:,.2f}"
    if num < 1_000_000: return f"{num / 1_000:,.2f}K"
    if num < 1_000_000_000: return f"{num / 1_000_000:,.2f}M"
    return f"{num / 1_000_000_000:,.2f}B"

def get_token_data(token_address: str) -> tuple[dict | None, dict | None, str | None]:
    """
    Fetches market data for a Solana token. It now returns the base token info
    separately from the pair info to allow for "Lite" analysis.

    Returns:
        A tuple: (best_pair, base_token_info, error_message).
    """
    if config.ENVIRONMENT == "development":
        print("--- MODO DE PRUEBA LOCAL ACTIVADO: Devolviendo datos falsos. ---")
        return MOCK_DEXSCREENER_RESPONSE["pairs"][0], MOCK_DEXSCREENER_RESPONSE["pairs"][0]['baseToken'], None

    BASE_URL = "https://api.dexscreener.com/latest/dex"
    HEADERS = { 'User-Agent': 'Mozilla/5.0 ...' } # Tu User-Agent aquí
    endpoint = f"/tokens/{token_address}"
    
    try:
        response = requests.get(BASE_URL + endpoint, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        pairs = data.get("pairs")
        
        if not pairs:
            first_pair = data.get("pairs", [{}])[0]
            base_token_info = first_pair.get('baseToken') if first_pair else None
            
            if base_token_info:
                 return None, base_token_info, "Token has no active trading pairs."
            else:
                 return None, None, "Token not found on DexScreener."
        
        best_pair = max(pairs, key=lambda p: p.get('liquidity', {}).get('usd', 0), default=None)
        base_token_info = best_pair.get('baseToken') if best_pair else None

        if not best_pair or best_pair.get('liquidity', {}).get('usd', 0) == 0:
             return None, base_token_info, "Token has pairs, but none have sufficient liquidity."

        return best_pair, base_token_info, None

    except requests.exceptions.HTTPError as e:
        return None, None, "Token not found on DexScreener." if e.response.status_code == 404 else f"An HTTP error occurred: {e}"
    except Exception as e:
        return None, None, f"An unexpected error occurred: {e}"

def format_token_analysis(pair_data: dict, error_message: str = None) -> str:
    """
    Takes raw pair data and formats it into a robust message,
    gracefully handling missing or malformed data fields.
    """
    if error_message:
        return f"⚠️ <b>Analysis Failed:</b>\n<i>{error_message}</i>"
    if not pair_data:
        return "⚠️ <b>Analysis Failed:</b>\n<i>Could not retrieve token data.</i>"

    base_token = pair_data.get('baseToken', {})
    quote_token = pair_data.get('quoteToken', {})
    
    # --- INICIO DE LA MODIFICACIÓN: Extracción y Validación Segura ---
    
    # Extraemos los datos y nos aseguramos de que sean del tipo correcto.
    # Si no, les asignamos None para que sean manejados más adelante.
    try:
        price_usd = float(pair_data.get('priceUsd')) if pair_data.get('priceUsd') is not None else None
    except (ValueError, TypeError):
        price_usd = None
        
    try:
        price_native = float(pair_data.get('priceNative')) if pair_data.get('priceNative') is not None else None
    except (ValueError, TypeError):
        price_native = None
        
    try:
        market_cap = float(pair_data.get('fdv')) if pair_data.get('fdv') is not None else None
    except (ValueError, TypeError):
        market_cap = None
        
    try:
        volume_24h = float(pair_data.get('volume', {}).get('h24')) if pair_data.get('volume', {}).get('h24') is not None else None
    except (ValueError, TypeError):
        volume_24h = None
        
    try:
        price_change_24h = float(pair_data.get('priceChange', {}).get('h24')) if pair_data.get('priceChange', {}).get('h24') is not None else None
    except (ValueError, TypeError):
        price_change_24h = None

    # --- FIN DE LA MODIFICACIÓN ---

    # --- Construcción del Mensaje Dinámico ---
    
    message_lines = []
    
    # Header
    message_lines.append(f"<b>{base_token.get('name', 'Unknown Token')}</b> (<code>${base_token.get('symbol', 'N/A')}</code>)")
    message_lines.append("")

    # Price
    if price_usd is not None:
        change_line = ""
        if price_change_24h is not None:
            change_symbol = "📈" if price_change_24h >= 0 else "📉"
            change_line = f"({change_symbol} {price_change_24h}%)"
        message_lines.append(f"<b>Price:</b> <code>${price_usd:,.8f}</code> {change_line}")

    if price_native is not None:
        message_lines.append(f"<b>Value:</b> <code>{price_native:,.6f} ${quote_token.get('symbol', 'N/A')}</code>")
    
    # Statistics Section
    stats_lines = []
    if market_cap is not None:
        stats_lines.append(f"<b>Market Cap:</b> <code>${format_large_number(market_cap)}</code>")
    if volume_24h is not None:
        stats_lines.append(f"<b>24h Volume:</b> <code>${format_large_number(volume_24h)}</code>")
    
    if stats_lines:
        message_lines.append("")
        message_lines.append(f"📊 <b><u>Statistics:</u></b>")
        message_lines.extend(stats_lines)

    # Associated Links
    message_lines.append("")
    message_lines.append(f"🔗 <b><u>Associated Links:</u></b>")
    links = []
    if pair_data.get('url'):
        links.append(f"<a href='{pair_data.get('url')}'>DexScreener</a>")
    if base_token.get('address'):
        links.append(f"<a href='https://solscan.io/token/{base_token.get('address')}'>Solscan</a>")
        links.append(f"<a href='https://rugcheck.xyz/tokens/{base_token.get('address')}'>RugCheck</a>")
    message_lines.append(" | ".join(links))

    # Security Analysis
    message_lines.append("")
    message_lines.append(f"🛡️ <b><u>Security Analysis:</u></b>")
    message_lines.append(f"<i>Security data not available via DexScreener.</i>")

    return "\n".join(message_lines)