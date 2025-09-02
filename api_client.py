import requests
import config

MOCK_DEXSCREENER_RESPONSE = {
    "pairs": [{
        "chainId": "solana", "dexId": "raydium", "url": "https://dexscreener.com/solana/...",
        "baseToken": {"address": "EKpQGS...", "name": "dogwifhat", "symbol": "WIF"},
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
    Fetches and formats token data. Returns a single dictionary with either
    the formatted message or an error message.
    """
    if config.ENVIRONMENT == "development":
        print("--- MODO DE PRUEBA LOCAL ACTIVADO: Devolviendo datos falsos. ---")
        return format_token_data(MOCK_DEXSCREENER_RESPONSE["pairs"][0])

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

        return format_token_data(best_pair)

    except requests.exceptions.HTTPError as e:
        return {"error": "Token not found on DexScreener."}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

def format_token_data(pair_data: dict) -> dict:
    """
    Helper function to format the data into a message string.
    Returns a dictionary with the final message.
    """
    base_token = pair_data.get('baseToken', {})
    
    # Si tenemos datos de mercado, construimos el mensaje completo
    if pair_data.get('priceUsd'):
        quote_token = pair_data.get('quoteToken', {})
        price_change_24h = pair_data.get('priceChange', {}).get('h24', 0)
        change_symbol = "📈" if price_change_24h >= 0 else "📉"
        
        message = (
            f"<b>{base_token.get('name', 'N/A')}</b> (<code>${base_token.get('symbol', 'N/A')}</code>)\n\n"
            f"<b>Price:</b> <code>${pair_data.get('priceUsd')}</code> ({change_symbol} {price_change_24h}%)\n"
            f"<b>Value:</b> <code>{pair_data.get('priceNative')} ${quote_token.get('symbol')}</code>\n\n"
            f"📊 <b><u>Statistics:</u></b>\n"
            f"<b>Market Cap:</b> <code>${format_large_number(pair_data.get('fdv'))}</code>\n"
            f"<b>24h Volume:</b> <code>${format_large_number(pair_data.get('volume', {}).get('h24'))}</code>\n\n"
            f"🔗 <b><u>Associated Links:</u></b>\n"
            f"<a href='{pair_data.get('url')}'>DexScreener</a> | "
            f"<a href='https://solscan.io/token/{base_token.get('address')}'>Solscan</a> | "
            f"<a href='https://rugcheck.xyz/tokens/{base_token.get('address')}'>RugCheck</a>"
        )
        return {"message": message}
    
    # Si no, construimos el mensaje "Lite"
    else:
        message = (
            f"<b>{base_token.get('name', 'N/A')}</b> (<code>${base_token.get('symbol', 'N/A')}</code>)\n\n"
            f"⚠️ <b>No Market Data Found.</b>\n\n"
            f"🔗 <b><u>Associated Links:</u></b>\n"
            f"<a href='https://solscan.io/token/{base_token.get('address')}'>Solscan</a> | "
            f"<a href='https://rugcheck.xyz/tokens/{base_token.get('address')}'>RugCheck</a>"
        )
        return {"message": message}