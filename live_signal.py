import time
import os
import requests
import pandas as pd
from pybit.unified_trading import HTTP

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8606129843:AAEsoUupG1xV7MJeDm0vC2QVV4dowFF9Wjc")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7730171706")

# Bybit API credentials (Optional for public signal checks)
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "YOUR_BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "YOUR_BYBIT_API_SECRET")

# Target pair on Bybit
SYMBOL = "1000BONKUSDT"
CATEGORY = "linear"

# Initialize Bybit Unified Trading HTTP Client
session = HTTP(
    testnet=False,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET,
)

def send_telegram(message):
    """Sends alert message directly to your Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram alert error: {e}")

def calculate_rsi(series, period=14):
    """Calculates Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_market_data():
    """Fetches kline data and computes SMA, EMA, RSI, MACD, and Volume indicators."""
    res = session.get_kline(category=CATEGORY, symbol=SYMBOL, interval="15", limit=100)
    if res.get("retCode") != 0:
        print(f"Bybit API Error: {res.get('retMsg')}")
        return None

    data = res["result"]["list"]
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)
    
    # Chronological order (oldest first)
    df = df.iloc[::-1].reset_index(drop=True)
    
    # --- INDICATORS ---
    # 1. Moving Averages
    df["SMA_9"] = df["close"].rolling(window=9).mean()
    df["SMA_21"] = df["close"].rolling(window=21).mean()
    df["EMA_200"] = df["close"].ewm(span=200, adjust=False).mean()

    # 2. RSI (14)
    df["RSI"] = calculate_rsi(df["close"], period=14)

    # 3. MACD (12, 26, 9)
    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema_12 - ema_26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    # 4. Volume Filter (Volume higher than 20-period Average Volume)
    df["VOL_MA20"] = df["volume"].rolling(window=20).mean()

    return df

def run_bot():
    print(f"Starting advanced trading bot for {SYMBOL}...")
    send_telegram(f"🚀 Multi-Indicator Bot updated on Render for {SYMBOL}!\nIndicators: SMA, EMA200, RSI, MACD, Volume.")
    
    while True:
        try:
            df = get_market_data()
            if df is not None and len(df) >= 50:
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                
                close = latest["close"]
                sma_9 = latest["SMA_9"]
                sma_21 = latest["SMA_21"]
                ema_200 = latest["EMA_200"]
                rsi = latest["RSI"]
                macd = latest["MACD"]
                macd_sig = latest["MACD_signal"]
                vol = latest["volume"]
                vol_ma = latest["VOL_MA20"]

                # Crossover condition
                bullish_cross = (prev["SMA_9"] <= prev["SMA_21"]) and (sma_9 > sma_21)
                bearish_cross = (prev["SMA_9"] >= prev["SMA_21"]) and (sma_9 < sma_21)

                # Filters
                above_ema200 = close > ema_200
                below_ema200 = close < ema_200
                rsi_bullish = 40 <= rsi <= 70  # Healthy momentum, not overbought
                rsi_bearish = 30 <= rsi <= 60  # Healthy momentum, not oversold
                macd_bullish = macd > macd_sig
                macd_bearish = macd < macd_sig
                high_volume = vol > vol_ma

                # --- SIGNAL LOGIC ---
                if bullish_cross and above_ema200 and rsi_bullish and macd_bullish and high_volume:
                    msg = (
                        f"🟢 STRONG BULLISH SIGNAL: {SYMBOL}\n"
                        f"Price: {close}\n"
                        f"RSI: {rsi:.1f} | MACD: Bullish\n"
                        f"Trend: Above EMA200 | Volume: Above Avg"
                    )
                    send_telegram(msg)

                elif bearish_cross and below_ema200 and rsi_bearish and macd_bearish and high_volume:
                    msg = (
                        f"🔴 STRONG BEARISH SIGNAL: {SYMBOL}\n"
                        f"Price: {close}\n"
                        f"RSI: {rsi:.1f} | MACD: Bearish\n"
                        f"Trend: Below EMA200 | Volume: Above Avg"
                    )
                    send_telegram(msg)

        except Exception as e:
            print(f"Error in main loop: {e}")

        time.sleep(60)

if __name__ == "__main__":
    run_bot()
