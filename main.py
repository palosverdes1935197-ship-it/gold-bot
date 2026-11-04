import math, time, requests, numpy as np, pandas as pd, yfinance as yf

# Discord Webhook URL（セット済み）
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1276310470113890387/Tl3LNLFOGDQRSYKUQtRf-MZNNp3cJRI_kyATbCpNok_NSi7sRbrtri1ekwAi0nbzFCpw"

# AIパラメータ（学習済み設定）
W_BB, W_RSI, W_MOM, W_ATR, BIAS, WIN_PROB_THRESH = 1.8, 1.4, -1.2, 0.6, -1.0, 0.65

def check_market():
    # ゴールド（1分足）の価格を取得
    df = yf.download(tickers="GC=F", period="1d", interval="1m", progress=False)
    if len(df) < 30: return
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    close, high, low = df['Close'], df['High'], df['Low']
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_up, bb_low = bb_mid + (bb_std * 2.0), bb_mid - (bb_std * 2.0)
    
    # 指標計算
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(9).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(9).mean()
    rsi = 100 - (100 / (1 + (gain / (loss + 1e-5))))
    mom = close - close.shift(14)
    tr = np.maximum(high - low, np.abs(high - close.shift(1)))
    atr = tr.rolling(14).mean()
    
    # 養分（イナゴ飛び乗り）の検知
    c1, c2 = close.iloc[-2], close.iloc[-3]
    is_sucker_buy = (c2 <= bb_up.iloc[-3]) and (c1 > bb_up.iloc[-2])
    is_sucker_sell = (c2 >= bb_low.iloc[-3]) and (c1 < bb_low.iloc[-2])
    
    if not is_sucker_buy and not is_sucker_sell: return

    # スコア（勝率）計算
    atr1, atr2 = atr.iloc[-2], atr.iloc[-3]
    if is_sucker_buy:
        f_bb = (c1 - bb_up.iloc[-2]) / (bb_up.iloc[-2] - bb_mid.iloc[-2] + 1e-5)
        z = (W_BB * f_bb) + (W_RSI * ((rsi.iloc[-2] - 70)/30)) + (W_MOM * (mom.iloc[-2]/(atr1+1e-5))) + (W_ATR * ((atr1-atr2)/(atr2+1e-5))) + BIAS
        prob = 1.0 / (1.0 + math.exp(-z))
        if prob >= WIN_PROB_THRESH:
            send_discord("SELL (売り)", prob, c1, atr1)

    if is_sucker_sell:
        f_bb = (bb_low.iloc[-2] - c1) / (bb_mid.iloc[-2] - bb_low.iloc[-2] + 1e-5)
        z = (W_BB * f_bb) + (W_RSI * ((30 - rsi.iloc[-2])/30)) + (W_MOM * (-mom.iloc[-2]/(atr1+1e-5))) + (W_ATR * ((atr1-atr2)/(atr2+1e-5))) + BIAS
        prob = 1.0 / (1.0 + math.exp(-z))
        if prob >= WIN_PROB_THRESH:
            send_discord("BUY (買い)", prob, c1, atr1)

def send_discord(side, prob, price, atr_val):
    color = 15158332 if side.startswith("SELL") else 3066993
    tp = price - (atr_val * 4.5) if side.startswith("SELL") else price + (atr_val * 4.5)
    sl = price + (atr_val * 2.5) if side.startswith("SELL") else price - (atr_val * 2.5)
    
    payload = {
        "embeds": [{
            "title": f"🚨 【逆神AI】{side} サイン発生！",
            "color": color,
            "fields": [
                {"name": "予測勝率", "value": f"**{prob*100:.1f}%**", "inline": True},
                {"name": "現在価格", "value": f"${price:.2f}", "inline": True},
                {"name": "利確目標 (+4.5 ATR)", "value": f"${tp:.2f}", "inline": False},
                {"name": "損切目標 (-2.5 ATR)", "value": f"${sl:.2f}", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

# 24時間監視スタート
while True:
    try:
        check_market()
        time.sleep(60) # 1分ごとにチェック
    except Exception as e:
        time.sleep(10)
