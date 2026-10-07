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

def get_market_data():
    """Fetches kline data and calculates SMA strategy for 1000BONKUSDT."""
    res = session.get_kline(category=CATEGORY, symbol=SYMBOL, interval="15", limit=50)
    if res.get("retCode") != 0:
        print(f"Bybit API Error: {res.get('retMsg')}")
        return None

    # Parse kline list into DataFrame
    data = res["result"]["list"]
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df["close"] = df["close"].astype(float)
    
    # Reverse to chronological order (oldest first)
    df = df.iloc[::-1].reset_index(drop=True)
    
    # Moving Average calculations
    df["SMA_9"] = df["close"].rolling(window=9).mean()
    df["SMA_21"] = df["close"].rolling(window=21).mean()
    
    return df

def run_bot():
    print(f"Starting trading bot for {SYMBOL}...")
    send_telegram(f"🚀 Trading Bot is live on Render for {SYMBOL}!")
    
    while True:
        try:
            df = get_market_data()
            if df is not None and len(df) >= 21:
                latest_close = df["close"].iloc[-1]
                sma_9 = df["SMA_9"].iloc[-1]
                sma_21 = df["SMA_21"].iloc[-1]
                
                print(f"[{SYMBOL}] Close: {latest_close} | SMA9: {sma_9:.6f} | SMA21: {sma_21:.6f}")
                
                # Simple Moving Average Crossover Signals
                if df["SMA_9"].iloc[-2] <= df["SMA_21"].iloc[-2] and sma_9 > sma_21:
                    msg = f"🟢 BULLISH SIGNAL: SMA9 crossed above SMA21 for {SYMBOL} at {latest_close}"
                    send_telegram(msg)
                elif df["SMA_9"].iloc[-2] >= df["SMA_21"].iloc[-2] and sma_9 < sma_21:
                    msg = f"🔴 BEARISH SIGNAL: SMA9 crossed below SMA21 for {SYMBOL} at {latest_close}"
                    send_telegram(msg)

        except Exception as e:
            print(f"Error in main loop: {e}")

        # Check market data every 60 seconds
        time.sleep(60)

if __name__ == "__main__":
    run_bot()
