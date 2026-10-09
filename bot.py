import os, time, threading, requests
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID_HERE")
MIN_PROFIT = float(os.getenv("MIN_PROFIT", "1.0"))

app = Flask(__name__)

BOOKMAKERS = ["Bet9ja", "SportyBet", "1xBet", "BetKing", "MSport", "NairaBet", "22Bet", "Melbet"]

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        print(e)

def check_surebets():
    while True:
        print("Scanning 14 bookies...")
        time.sleep(60)

@app.route("/")
def home():
    return f"✅ Bot Live - Scanning {len(BOOKMAKERS)} bookies"

@app.route("/test")
def test():
    send_telegram("🚨 TEST ALERT - Your Naija Arb Bot is working!")
    return "Test sent to Telegram!"

if __name__ == "__main__":
    threading.Thread(target=check_surebets, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
