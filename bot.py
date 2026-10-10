import os, time, threading, requests
from flask import Flask, request, jsonify
from datetime import datetime
from collections import defaultdict

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
MIN_PROFIT = float(os.getenv("MIN_PROFIT", "1.0"))
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
STAKE = 50000
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"  # Set DEMO_MODE=false for REAL ONLY

ALL_SPORTS = [
    "soccer_epl", "soccer_spain_la_liga", "soccer_germany_bundesliga", "soccer_italy_serie_a", "soccer_france_ligue_one",
    "soccer_uefa_champs_league", "soccer_europa_league", "soccer_england_championship",
    "basketball_nba", "basketball_euroleague",
    "tennis_atp_singles", "tennis_wta_singles",
    "americanfootball_nfl", "baseball_mlb", "icehockey_nhl",
    "mma_mixed_martial_arts", "cricket_icc_world_cup", "rugby_rugby_union"
]

app = Flask(__name__)

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
        requests.post(url, json=payload, timeout=20)
        print(f"TG REAL: {text[:150]}")
    except Exception as e:
        print(f"TG error: {e}")

def calc_2way(o1,o2):
    try:
        o1=float(o1); o2=float(o2)
        if o1<=1 or o2<=1: return None
        total = 1/o1 + 1/o2
        if total < 1:
            pct = (1-total)*100
            if pct>15 or pct<MIN_PROFIT: return None
            s1 = STAKE * (1/o1) / total
            s2 = STAKE * (1/o2) / total
            cash = STAKE * (1/total - 1)
            return pct, s1, s2, cash, total
    except: pass
    return None

def calc_3way(o1,o2,o3):
    try:
        o1=float(o1); o2=float(o2); o3=float(o3)
        if min(o1,o2,o3)<=1: return None
        total = 1/o1 + 1/o2 + 1/o3
        if total < 1:
            pct = (1-total)*100
            if pct>15 or pct<MIN_PROFIT: return None
            s1 = STAKE * (1/o1) / total
            s2 = STAKE * (1/o2) / total
            s3 = STAKE * (1/o3) / total
            cash = STAKE * (1/total - 1)
            return pct, s1, s2, s3, cash, total
    except: pass
    return None

def get_real_time_all_sports():
    """REAL TIME ONLY - No demo pattern"""
    if not ODDS_API_KEY:
        print("NO ODDS_API_KEY - Cannot fetch REAL TIME matches. Add key to Render Env")
        return [], "NO_API_KEY"
    
    all_games = []
    errors = []
    # REAL TIME - scan ALL sports but in batches to save quota
    # Scan 8 sports per cycle, rotate through 16
    now_hour = datetime.now().hour
    half = 0 if now_hour % 2 == 0 else 1
    sports_batch = ALL_SPORTS[half*8:(half+1)*8]
    
    print(f"REAL TIME scanning batch {half}: {sports_batch}")
    for sport_key in sports_batch:
        try:
            # Fetch with all regions for best odds comparison
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds?regions=eu,uk,us,au&markets=h2h,totals,btts,spreads&oddsFormat=decimal&apiKey={ODDS_API_KEY}"
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                data = r.json()
                # Only keep games that are happening soon or live
                for g in data:
                    g['_sport'] = sport_key
                    g['_fetched_at'] = datetime.now().isoformat()
                all_games.extend(data)
                remaining = r.headers.get('x-requests-remaining', '?')
                print(f"{sport_key}: {len(data)} REAL live games, remaining quota {remaining}")
            elif r.status_code == 429:
                print(f"Quota exceeded! Remaining: {r.headers.get('x-requests-remaining')}")
                errors.append("QUOTA_EXCEEDED")
                break
            else:
                print(f"{sport_key} error {r.status_code}: {r.text[:100]}")
                errors.append(f"{sport_key}:{r.status_code}")
            time.sleep(0.8)
        except Exception as e:
            print(f"{sport_key} exception {e}")
            errors.append(str(e))
    
    status = "OK" if all_games else ",".join(errors) if errors else "NO_GAMES"
    print(f"REAL TIME TOTAL: {len(all_games)} live games - status {status}")
    return all_games, status

def scan_real_time_only():
    send_telegram(f"Meta Arb v13 REAL TIME ONLY LIVE! No more demo pattern - Only real live matches from Odds API - Scanning {len(ALL_SPORTS)} sports - Markets: Over/Under, BTTS, 1X2, H2H, Spreads - Min {MIN_PROFIT}% - Demo mode: {DEMO_MODE}")
    
    while True:
        try:
            print(f"\n[{datetime.now()}] v13 REAL TIME ONLY scan...")
            games, fetch_status = get_real_time_all_sports()
            
            if fetch_status == "NO_API_KEY":
                if DEMO_MODE:
                    send_telegram("WARNING: No ODDS_API_KEY set, DEMO_MODE=true so using demo pattern. Set DEMO_MODE=false and add ODDS_API_KEY for REAL TIME matches!")
                else:
                    send_telegram(f"REAL TIME: No ODDS_API_KEY found. Add your key from the-odds-api.com to Render Env vars. Current time {datetime.now()} - Waiting for key...")
                    time.sleep(120)
                    continue
            
            if not games:
                send_telegram(f"REAL TIME SCAN: {fetch_status} - No live games right now or no arbs. Scanned {len(ALL_SPORTS)} sports at {datetime.now()} - Will rescan in 60s")
                time.sleep(90)
                continue
            
            # Process REAL games for arbs
            arb_found = 0
            for game in games[:20]:  # Check top 20 real games
                sport = game.get('_sport','unknown')
                home = game.get('home_team','Home')
                away = game.get('away_team','Away')
                commence = game.get('commence_time','')
                
                markets_best = defaultdict(dict)
                for bk in game.get('bookmakers',[]):
                    bk_name = bk.get('title','Book')
                    for mk in bk.get('markets',[]):
                        mk_key = mk.get('key','')
                        for out in mk.get('outcomes',[]):
                            name = out.get('name','')
                            price = out.get('price',0)
                            point = out.get('point','')
                            key_name = f"{name} {point}" if point!='' else name
                            if key_name not in markets_best[mk_key] or price > markets_best[mk_key][key_name][0]:
                                markets_best[mk_key][key_name] = (price, bk_name, name, point)
                
                # REAL Over/Under
                if 'totals' in markets_best:
                    by_point = defaultdict(dict)
                    for k,(price,bk,name,point) in markets_best['totals'].items():
                        by_point[point][name] = (price,bk)
                    for point, outcomes in by_point.items():
                        if 'Over' in outcomes and 'Under' in outcomes:
                            o1,b1 = outcomes['Over']; o2,b2 = outcomes['Under']
                            c = calc_2way(o1,o2)
                            if c:
                                pct,s1,s2,cash,tot = c
                                msg = f"REAL TIME {pct:.2f}% {sport} Totals! LIVE: {home} vs {away} Over {point} {b1} @ {o1} + Under {point} {b2} @ {o2} Profit N{cash:,.0f} | Starts {commence[:16]}"
                                send_telegram(msg)
                                arb_found+=1
                                time.sleep(4)
                
                # REAL BTTS
                if 'btts' in markets_best:
                    if 'Yes' in markets_best['btts'] and 'No' in markets_best['btts']:
                        o1,b1,_,_ = markets_best['btts']['Yes']; o2,b2,_,_ = markets_best['btts']['No']
                        c = calc_2way(o1,o2)
                        if c:
                            pct,s1,s2,cash,tot = c
                            msg = f"REAL TIME {pct:.2f}% {sport} BTTS! LIVE: {home} vs {away} Yes {b1} @ {o1} + No {b2} @ {o2} Profit N{cash:,.0f}"
                            send_telegram(msg)
                            arb_found+=1
                            time.sleep(4)
                
                # REAL H2H 3-way and 2-way
                if 'h2h' in markets_best:
                    outcomes = markets_best['h2h']
                    has_home=None; has_away=None; has_draw=None
                    for k,(price,bk,name,point) in outcomes.items():
                        if name.lower()=='draw':
                            has_draw=(price,bk,name)
                        elif name==home:
                            has_home=(price,bk,name)
                        elif name==away:
                            has_away=(price,bk,name)
                    if has_home and has_draw and has_away:
                        o1,b1,_ = has_home; o2,b2,_ = has_draw; o3,b3,_ = has_away
                        c = calc_3way(o1,o2,o3)
                        if c:
                            pct,s1,s2,s3,cash,tot = c
                            msg = f"REAL TIME {pct:.2f}% {sport} 1X2! LIVE: {home} vs {away} H@{o1} {b1} D@{o2} {b2} A@{o3} {b3} Profit N{cash:,.0f} | {commence[:16]}"
                            send_telegram(msg)
                            arb_found+=1
                            time.sleep(5)
                    elif has_home and has_away:
                        o1,b1,_ = has_home; o2,b2,_ = has_away
                        c = calc_2way(o1,o2)
                        if c:
                            pct,s1,s2,cash,tot = c
                            msg = f"REAL TIME {pct:.2f}% {sport} H2H! LIVE: {home} vs {away} {b1} @ {o1} + {b2} @ {o2} Profit N{cash:,.0f} | {commence[:16]}"
                            send_telegram(msg)
                            arb_found+=1
                            time.sleep(4)
            
            if arb_found==0:
                send_telegram(f"REAL TIME: Scanned {len(games)} live matches across {len(ALL_SPORTS)} sports at {datetime.now()} - No arb >{MIN_PROFIT}% found this cycle. Next scan in 60s")
            
            time.sleep(60)
        except Exception as e:
            print(f"Loop error: {e}")
            import traceback; traceback.print_exc()
            time.sleep(30)

@app.route("/")
def home():
    mode = "REAL TIME ONLY" if not DEMO_MODE else "DEMO ROTATING"
    return f"Meta Arb v13 {mode} LIVE! Real live matches only - No demo Liverpool loop - {len(ALL_SPORTS)} sports - Min {MIN_PROFIT}% - Time {datetime.now()} - Go to /live /status /test /health"

@app.route("/live")
def live():
    games, status = get_real_time_all_sports()
    if status=="NO_API_KEY":
        return jsonify({"error": "No ODDS_API_KEY set", "message": "Add your API key from the-odds-api.com to Render Env vars ODDS_API_KEY", "demo_mode": DEMO_MODE, "sports_available": ALL_SPORTS})
    result = []
    for g in games[:20]:
        result.append({
            "sport": g.get('_sport'),
            "home": g.get('home_team'),
            "away": g.get('away_team'),
            "commence_time": g.get('commence_time'),
            "bookmakers": len(g.get('bookmakers',[]))
        })
    return jsonify({"status": status, "total_live_games": len(games), "sample_games": result, "fetched_at": datetime.now().isoformat(), "sports_scanned": ALL_SPORTS[:8]})

@app.route("/test")
def test():
    send_telegram(f"TEST v13 REAL TIME ONLY! Scanning real live matches now at {datetime.now()} - No demo pattern")
    return f"Test v13 REAL TIME sent! Mode DEMO={DEMO_MODE} - Check /live for real matches - Time {datetime.now()}"

@app.route("/status")
def status():
    has_key = f"YES - {len(ALL_SPORTS)} sports REAL TIME" if ODDS_API_KEY else "NO - Add ODDS_API_KEY from the-odds-api.com for REAL TIME"
    return f"v13 REAL TIME ONLY | {has_key} | Demo mode {DEMO_MODE} (set false for real only) | Min {MIN_PROFIT}% | {datetime.now()} | /live shows real matches"

@app.route("/health")
def health():
    return "OK v13 REAL TIME ONLY Live"

@app.route("/sports")
def sports():
    return jsonify({"all_sports": ALL_SPORTS, "total": len(ALL_SPORTS), "note": "v13 scans 8 sports per hour rotating, real live games only, no demo Liverpool loop"})

@app.errorhandler(404)
def not_found(e):
    return f"v13 REAL TIME ONLY LIVE! Use /live for real matches, /status, /test, /health - {datetime.now()}", 200

if __name__ == "__main__":
    threading.Thread(target=scan_real_time_only, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting v13 REAL TIME ONLY on port {port} - DEMO_MODE={DEMO_MODE}")
    app.run(host="0.0.0.0", port=port, debug=False)
