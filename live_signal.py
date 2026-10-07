import time
import os
import threading
import requests
import pandas as pd
from flask import Flask
from pybit.unified_trading import HTTP

# --- FLASK SERVER FOR RENDER FREE WEBSERVICE ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running 24/7!", 200

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8606129843:AAEsoUupG1xV7MJeDm0vC2QVV4dowFF9Wjc")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7730171706")

SYMBOL = "1000BONKUSDT"
CATEGORY = "linear"

session = HTTP(testnet=False)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram alert error: {e}")

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_kline_data(interval_str):
    res = session.get_kline(category=CATEGORY, symbol=SYMBOL, interval=interval_str, limit=100)
    if res.get("retCode") != 0:
        return None

    data = res["result"]["list"]
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["volume"] = df["volume"].astype(float)
    df = df.iloc[::-1].reset_index(drop=True)
    return df

def get_market_data():
    df_15m = get_kline_data("15")
    if df_15m is None:
        return None, None

    df_15m["EMA_9"] = df_15m["close"].ewm(span=9, adjust=False).mean()
    df_15m["EMA_21"] = df_15m["close"].ewm(span=21, adjust=False).mean()
    df_15m["EMA_200"] = df_15m["close"].ewm(span=200, adjust=False).mean()
    df_15m["RSI"] = calculate_rsi(df_15m["close"], period=14)

    ema_12 = df_15m["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df_15m["close"].ewm(span=26, adjust=False).mean()
    df_15m["MACD"] = ema_12 - ema_26
    df_15m["MACD_signal"] = df_15m["MACD"].ewm(span=9, adjust=False).mean()
    df_15m["VOL_MA20"] = df_15m["volume"].rolling(window=20).mean()

    df_15m["SWING_LOW"] = df_15m["low"].rolling(window=10).min()
    df_15m["SWING_HIGH"] = df_15m["high"].rolling(window=10).max()

    df_1h = get_kline_data("60")
    if df_1h is not None:
        df_1h["EMA_200"] = df_1h["close"].ewm(span=200, adjust=False).mean()

    return df_15m, df_1h

def bot_loop():
    send_telegram(f"🚀 **Multi-Timeframe Bot Active (Free Tier)!**\nSymbol: `{SYMBOL}`\nEntry: 15m | Validation: 1h\nUpdates: Every 15 Minutes")
    
    while True:
        try:
            df_15m, df_1h = get_market_data()
            if df_15m is not None and len(df_15m) >= 50 and df_1h is not None and len(df_1h) >= 50:
                latest = df_15m.iloc[-1]
                prev = df_15m.iloc[-2]
                
                close = latest["close"]
                ema_9 = latest["EMA_9"]
                ema_21 = latest["EMA_21"]
                ema_200_15m = latest["EMA_200"]
                rsi = latest["RSI"]
                macd = latest["MACD"]
                macd_sig = latest["MACD_signal"]
                vol = latest["volume"]
                vol_ma = latest["VOL_MA20"]

                latest_1h = df_1h.iloc[-1]
                close_1h = latest_1h["close"]
                ema200_1h = latest_1h["EMA_200"]
                macro_bullish = close_1h > ema200_1h
                macro_bearish = close_1h < ema200_1h

                bullish_cross = (prev["EMA_9"] <= prev["EMA_21"]) and (ema_9 > ema_21)
                bearish_cross = (prev["EMA_9"] >= prev["EMA_21"]) and (ema_9 < ema_21)

                above_15m_ema200 = close > ema_200_15m
                below_15m_ema200 = close < ema_200_15m
                rsi_bullish = 40 <= rsi <= 70
                rsi_bearish = 30 <= rsi <= 60
                macd_bullish = macd > macd_sig
                macd_bearish = macd < macd_sig
                high_volume = vol > vol_ma

                signal_sent = False

                if bullish_cross and above_15m_ema200 and macro_bullish and rsi_bullish and macd_bullish and high_volume:
                    entry = close
                    sl = latest["SWING_LOW"]
                    risk = entry - sl
                    tp = entry + (risk * 2)

                    msg = (
                        f"🟢 **VALIDATED LONG SIGNAL**\n\n"
                        f"📌 **Pair:** `{SYMBOL}`\n"
                        f"📍 **Entry Price:** `{entry:.6f}`\n"
                        f"🎯 **Take Profit:** `{tp:.6f}` (1:2 R:R)\n"
                        f"🛑 **Stop Loss:** `{sl:.6f}`\n\n"
                        f"📊 **Multi-Timeframe Analysis:**\n"
                        f"• 1h Macro Trend: Bullish (Above EMA200)\n"
                        f"• 15m Signal: EMA 9/21 Bullish Cross\n"
                        f"• RSI: {rsi:.1f} | MACD: Bullish"
                    )
                    send_telegram(msg)
                    signal_sent = True

                elif bearish_cross and below_15m_ema200 and macro_bearish and rsi_bearish and macd_bearish and high_volume:
                    entry = close
                    sl = latest["SWING_HIGH"]
                    risk = sl - entry
                    tp = entry - (risk * 2)

                    msg = (
                        f"🔴 **VALIDATED SHORT SIGNAL**\n\n"
                        f"📌 **Pair:** `{SYMBOL}`\n"
                        f"📍 **Entry Price:** `{entry:.6f}`\n"
                        f"🎯 **Take Profit:** `{tp:.6f}` (1:2 R:R)\n"
                        f"🛑 **Stop Loss:** `{sl:.6f}`\n\n"
                        f"📊 **Multi-Timeframe Analysis:**\n"
                        f"• 1h Macro Trend: Bearish (Below EMA200)\n"
                        f"• 15m Signal: Bearish Cross\n"
                        f"• RSI: {rsi:.1f} | MACD: Bearish"
                    )
                    send_telegram(msg)
                    signal_sent = True

                if not signal_sent:
                    trend_status = "BULLISH 📈" if macro_bullish else "BEARISH 📉"
                    update_msg = (
                        f"⏱ **15m Market Update ({SYMBOL})**\n"
                        f"• Price: `{close:.6f}`\n"
                        f"• 1h Macro Trend: {trend_status}\n"
                        f"• 15m RSI: `{rsi:.1f}`\n"
                        f"• Signal: Waiting for entry setup..."
                    )
                    send_telegram(update_msg)

        except Exception as e:
            print(f"Error in signal loop: {e}")

        time.sleep(900)

if __name__ == "__main__":
    # Start signal loop in a separate thread
    threading.Thread(target=bot_loop, daemon=True).start()
    
    # Run Flask server on port provided by Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
