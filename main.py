import os
import math
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import numpy as np
import pandas as pd
import yfinance as yf

# Render用のレスポンス対応ダミーサーバー
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # アクセスログの無駄な出力を防止

def run_dummy_server():
    try:
        port = int(os.environ.get("PORT", 10000))
        server = HTTPServer(("0.0.0.0", port), DummyHandler)
        print(f"--> Web server started on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"--> Web server error: {e}")

threading.Thread(target=run_dummy_server, daemon=True).start()

# Discord Webhook URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1302821215437885501/kO79Cky4q2x9M_e3_E0sX34m9k93X"

# AIパラメータ（学習済み設定）
W_BB, W_RSI, W_MOM, W_ATR, BIAS, WIN_THRESHOLD = 0.35, 0.25, 0.25, 0.15, -0.1, 0.65

def send_discord(message, win_prob, price, atr):
    color = 0x00FF00 if win_prob >= 0.70 else 0xFFFF00
    payload = {
        "embeds": [{
            "title": f"🚨 【逆神AI】{message} サイン発生！",
            "color": color,
            "fields": [
                {"name": "現在価格 (XAU/USD)", "value": f"${price:.2f}", "inline": True},
                {"name": "予測勝率", "value": f"{win_prob*100:.1f}%", "inline": True},
                {"name": "ボラティリティ (ATR)", "value": f"${atr:.2f}", "inline": True}
            ],
            "footer": {"text": "24h Gold Monitoring Bot"}
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"Discord Send Error: {e}")

def check_market():
    df = yf.download(tickers="GC=F", period="1d", interval="1m", progress=False)
    if len(df) < 30: return
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close, high, low = df['Close'], df['High'], df['Low']
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-6)
    rsi = 100 - (100 / (1 + rs))
    
    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    
    c, mid, std, r, a = close.iloc[-1], bb_mid.iloc[-1], bb_std.iloc[-1], rsi.iloc[-1], atr.iloc[-1]
    
    score_sell = ((c - mid) / (std + 1e-6)) * W_BB + ((r - 50) / 20) * W_RSI + BIAS
    score_buy = ((mid - c) / (std + 1e-6)) * W_BB + ((50 - r) / 20) * W_RSI + BIAS
    
    prob_sell = 1 / (1 + math.exp(-score_sell))
    prob_buy = 1 / (1 + math.exp(-score_buy))
    
    if prob_sell >= WIN_THRESHOLD:
        send_discord("イナゴ高値掴みトラップ (SHORT推奨)", prob_sell, c, a)
    elif prob_buy >= WIN_THRESHOLD:
        send_discord("狼狽売り底値トラップ (LONG推奨)", prob_buy, c, a)

# 24時間監視スタート
while True:
    try:
        check_market()
        time.sleep(60)
    except Exception as e:
        time.sleep(10)
