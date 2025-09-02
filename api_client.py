import requests
import config

MOCK_DEXSCREENER_RESPONSE = {
    "pairs": [{
        "chainId": "solana", "dexId": "raydium", "url": "https://dexscreener.com/solana/...",
        "baseToken": {"address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzL7_qrN5L3n3g", "name": "dogwifhat", "symbol": "WIF"},
        "quoteToken": {"symbol": "SOL"}, "priceNative": "0.0125", "priceUsd": "1.75",
        "fdv": 1748017320, "volume": {"h24": 50123456}, "priceChange": {"h24": -5.7}
    }]
}

def format_large_number(num: float) -> str:
    if num is None: return "N/A"
    try: num = float(num)
    except (ValueError, TypeError): return "N/A"
    if num < 1_000: return f"{num:,.2f}"
    if num < 1_000_000: return f"{num / 1_000:,.2f}K"
    if num < 1_000_000_000: return f"{num / 1_000_000:,.2f}M"
    return f"{num / 1_000_000_000:,.2f}B"

def get_token_analysis(token_address: str) -> dict:
    """
    Fetches and prepares token data for formatting. Returns a single dictionary.
    """
    if config.ENVIRONMENT == "development":
        print("--- MODO DE PRUEBA LOCAL ACTIVADO: Devolviendo datos de prueba. ---")
        return {"pair_data": MOCK_DEXSCREENER_RESPONSE["pairs"][0]}

    BASE_URL = "https://api.dexscreener.com/latest/dex"
    HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36' }
    endpoint = f"/tokens/{token_address}"
    
    try:
        response = requests.get(BASE_URL + endpoint, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        pairs = data.get("pairs")
        
        if not pairs:
            return {"error": "Token found, but it has no active trading pairs."}
        
        best_pair = max(pairs, key=lambda p: p.get('liquidity', {}).get('usd', 0), default=None)
        
        if not best_pair or best_pair.get('liquidity', {}).get('usd', 0) == 0:
             base_token_info = pairs[0].get('baseToken') if pairs else None
             return {"error": "Token has pairs, but none have sufficient liquidity.", "token_info": base_token_info}

        return {"pair_data": best_pair}

    except requests.exceptions.HTTPError as e:
        return {"error": "Token not found on DexScreener."}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

def format_token_analysis(analysis_result: dict) -> str:
    """
    Takes a result dictionary and formats it into a full or "Lite" analysis message.
    """
    error_message = analysis_result.get("error")
    pair_data = analysis_result.get("pair_data")
    token_info = analysis_result.get("token_info")

    # --- INICIO DE LA LÓGICA CORREGIDA ---

    # Si no tenemos ningún dato del token, mostramos el error principal
    if not pair_data and not token_info:
        return f"⚠️ <b>Analysis Failed:</b>\n<i>{error_message or 'Token not found.'}</i>"

    # Si tenemos info del token (del caso de error) pero no del par, la usamos
    if not pair_data and token_info:
        base_token = token_info
        message = (
            f"<b>{base_token.get('name', 'N/A')}</b> (<code>${base_token.get('symbol', 'N/A')}</code>)\n\n"
            f"⚠️ <b>No Market Data Found:</b>\n"
            f"<i>{error_message}</i>\n\n"
            f"🔗 <b><u>Associated Links:</u></b>\n"
            f"<a href='https://solscan.io/token/{base_token.get('address')}'>Solscan</a> | "
            f"<a href='https://rugcheck.xyz/tokens/{base_token.get('address')}'>RugCheck</a>"
        )
        return message

    # Si llegamos aquí, es porque tenemos datos completos del par
    base_token = pair_data.get('baseToken', {})
    quote_token = pair_data.get('quoteToken', {})
    price_usd = pair_data.get('priceUsd')
    price_native = pair_data.get('priceNative')
    market_cap = pair_data.get('fdv')
    volume_24h = pair_data.get('volume', {}).get('h24')
    price_change_24h = pair_data.get('priceChange', {}).get('h24', 0)
    
    change_symbol = "📈" if price_change_24h >= 0 else "📉"
    
    message = (
        f"<b>{base_token.get('name')}</b> (<code>${base_token.get('symbol')}</code>)\n\n"
        f"<b>Price:</b> <code>${price_usd}</code> ({change_symbol} {price_change_24h}%)\n"
        f"<b>Value:</b> <code>{price_native} ${quote_token.get('symbol')}</code>\n\n"
        f"📊 <b><u>Statistics:</u></b>\n"
        f"<b>Market Cap:</b> <code>${format_large_number(market_cap)}</code>\n"
        f"<b>24h Volume:</b> <code>${format_large_number(volume_24h)}</code>\n\n"
        f"🔗 <b><u>Associated Links:</u></b>\n"
        f"<a href='{pair_data.get('url')}'>DexScreener</a> | "
        f"<a href='https://solscan.io/token/{base_token.get('address')}'>Solscan</a> | "
        f"<a href='https://rugcheck.xyz/tokens/{base_token.get('address')}'>RugCheck</a>"
    )
    return message