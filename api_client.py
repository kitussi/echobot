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

def format_token_analysis(pair_data: dict, base_token_info: dict, error_message: str = None) -> str:
    """
    Formats data into a full or "Lite" analysis message for Telegram.
    """
    # CASO 1: No tenemos ni siquiera la información básica del token
    if not base_token_info:
        return f"⚠️ <b>Analysis Failed:</b>\n<i>{error_message or 'Token not found.'}</i>"

    # CASO 2: Tenemos info básica, pero no datos de mercado (Análisis "Lite")
    if not pair_data:
        message = (
            f"<b>{base_token_info.get('name')}</b> (<code>${base_token_info.get('symbol')}</code>)\n\n"
            f"⚠️ <b>No Market Data Found:</b>\n"
            f"<i>{error_message or 'This token currently has no active or sufficient liquidity on tracked exchanges.'}</i>\n\n"
            
            f"🔗 <b><u>Associated Links:</u></b>\n"
            f"<a href='https://solscan.io/token/{base_token_info.get('address')}'>Solscan</a> | "
            f"<a href='https://rugcheck.xyz/tokens/{base_token_info.get('address')}'>RugCheck</a>"
        )
        return message

    # CASO 3: Tenemos todo (Análisis Completo)
    quote_token = pair_data.get('quoteToken', {})
    price_usd = pair_data.get('priceUsd')
    price_native = pair_data.get('priceNative')
    market_cap = pair_data.get('fdv')
    volume_24h = pair_data.get('volume', {}).get('h24')
    price_change_24h = pair_data.get('priceChange', {}).get('h24', 0)
    
    change_symbol = "📈" if price_change_24h >= 0 else "📉"
    
    message = (
        f"<b>{base_token_info.get('name')}</b> (<code>${base_token_info.get('symbol')}</code>)\n\n"
        f"<b>Price:</b> <code>${price_usd}</code> ({change_symbol} {price_change_24h}%)\n"
        # ... (resto del mensaje completo, sin cambios)
    )
    return message