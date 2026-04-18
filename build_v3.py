import re, json, os, sys
from datetime import datetime, timezone, timedelta

bitmoji = open('/home/claude/bitmoji_b64.txt').read().strip()

# ─── CONFIG ────────────────────────────────────────────────────────────────────
ODDS_API_KEY = os.environ.get('ODDS_API_KEY', '8f704d6437e1a8c264b58ae896ea0702')
ET_OFFSET    = -4  # EDT (Mar-Nov); script auto-detects but this is the default

SPORT_CONFIG = [
    {'key': 'icehockey_nhl',  'lg': 'NHL'},
    {'key': 'baseball_mlb',   'lg': 'MLB'},
    {'key': 'basketball_nba', 'lg': 'NBA'},
]

ABBR = {
    'Tampa Bay Lightning':'TB','Buffalo Sabres':'BUF','Boston Bruins':'BOS',
    'Carolina Hurricanes':'CAR','Ottawa Senators':'OTT','Florida Panthers':'FLA',
    'Montreal Canadiens':'MTL','Philadelphia Flyers':'PHI','New Jersey Devils':'NJ',
    'New York Rangers':'NYR','Calgary Flames':'CGY','Dallas Stars':'DAL',
    'Edmonton Oilers':'EDM','Utah Mammoth':'UTA','Nashville Predators':'NSH',
    'Anaheim Ducks':'ANA','Vegas Golden Knights':'VGK','Vancouver Canucks':'VAN',
    'Columbus Blue Jackets':'CBJ','Detroit Red Wings':'DET','Seattle Kraken':'SEA',
    'Winnipeg Jets':'WPG','Chicago Blackhawks':'CHI','San Jose Sharks':'SJ',
    'Los Angeles Kings':'LA','Minnesota Wild':'MIN','Pittsburgh Penguins':'PIT',
    'New York Islanders':'NYI','Washington Capitals':'WSH','Colorado Avalanche':'COL',
    'St. Louis Blues':'STL','Toronto Maple Leafs':'TOR',
    'Cleveland Guardians':'CLE','Kansas City Royals':'KC','San Diego Padres':'SD',
    'Cincinnati Reds':'CIN','Miami Marlins':'MIA','Milwaukee Brewers':'MIL',
    'Boston Red Sox':'BOS','St. Louis Cardinals':'STL','Washington Nationals':'WSH',
    'Athletics':'ATH','New York Yankees':'NYY','Los Angeles Dodgers':'LAD',
    'Toronto Blue Jays':'TOR','Baltimore Orioles':'BAL','Chicago White Sox':'CWS',
    'Detroit Tigers':'DET','Minnesota Twins':'MIN','Seattle Mariners':'SEA',
    'Texas Rangers':'TEX','Houston Astros':'HOU','Colorado Rockies':'COL',
    'Atlanta Braves':'ATL','Los Angeles Angels':'LAA','Philadelphia Phillies':'PHI',
    'San Francisco Giants':'SF','Arizona Diamondbacks':'AZ','New York Mets':'NYM',
    'Chicago Cubs':'CHC','Tampa Bay Rays':'TB','Pittsburgh Pirates':'PIT',
    'Minnesota Timberwolves':'MIN','Indiana Pacers':'IND','Chicago Bulls':'CHI',
    'Washington Wizards':'WAS','Milwaukee Bucks':'MIL','Brooklyn Nets':'BKN',
    'Miami Heat':'MIA','Toronto Raptors':'TOR','Charlotte Hornets':'CHA',
    'Boston Celtics':'BOS','New Orleans Pelicans':'NOP','Utah Jazz':'UTA',
    'Oklahoma City Thunder':'OKC','Dallas Mavericks':'DAL','LA Clippers':'LAC',
    'Los Angeles Lakers':'LAL','Houston Rockets':'HOU','Phoenix Suns':'PHX',
    'Memphis Grizzlies':'MEM','Denver Nuggets':'DEN','Portland Trail Blazers':'POR',
    'Sacramento Kings':'SAC','Golden State Warriors':'GSW','San Antonio Spurs':'SAS',
    'Cleveland Cavaliers':'CLE','Atlanta Hawks':'ATL','Detroit Pistons':'DET',
    'Orlando Magic':'ORL',
}

def abbr(name):
    return ABBR.get(name, (name or '').split()[-1][:3].upper())

def et_offset():
    """Auto-detect EDT vs EST based on current UTC time vs US DST rules."""
    now = datetime.now(timezone.utc)
    year = now.year
    # DST starts: 2nd Sunday of March at 2AM; ends: 1st Sunday of November at 2AM
    def nth_sunday(month, n):
        d = datetime(year, month, 1, tzinfo=timezone.utc)
        days_until_sun = (6 - d.weekday()) % 7
        return d + timedelta(days=days_until_sun + (n-1)*7)
    dst_start = nth_sunday(3, 2).replace(hour=7)   # 2AM ET = 7AM UTC
    dst_end   = nth_sunday(11, 1).replace(hour=6)  # 2AM ET = 6AM UTC (after fall back)
    return -4 if dst_start <= now < dst_end else -5

def et_now():
    return datetime.now(timezone.utc) + timedelta(hours=et_offset())

def date_str(dt):
    return dt.strftime('%Y-%m-%d')

def fmt_time(dt):
    h = dt.hour % 12 or 12
    m = dt.strftime('%M')
    ap = 'PM' if dt.hour >= 12 else 'AM'
    return f"{h}:{m} {ap} ET"

def fmt_label(dt):
    return dt.strftime('%a %b %-d').upper()

def fetch_json(url):
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [fetch] WARN: {e}", file=sys.stderr)
        return None

def fetch_today_and_tomorrow():
    today    = date_str(et_now())
    tomorrow = date_str(et_now() + timedelta(days=1))
    today_games, tmrw_games = [], []
    for sc in SPORT_CONFIG:
        url = (f"https://api.the-odds-api.com/v4/sports/{sc['key']}/odds/"
               f"?apiKey={ODDS_API_KEY}&regions=us&markets=h2h,totals"
               f"&oddsFormat=american&daysFrom=2")
        data = fetch_json(url)
        if not data:
            continue
        print(f"  {sc['lg']}: {len(data)} games")
        for g in data:
            start_et = datetime.fromisoformat(g['commence_time'].replace('Z','+00:00')) + timedelta(hours=et_offset())
            gdate    = date_str(start_et)
            aw, af   = abbr(g.get('away_team','')), g.get('away_team','')
            hm, hf   = abbr(g.get('home_team','')), g.get('home_team','')
            lg, tm   = sc['lg'], fmt_time(start_et)
            fo, ou, od, pr, fav = -110, 8.0, 'O', 50, hm
            for bk in (g.get('bookmakers') or [])[:1]:
                for mkt in bk.get('markets', []):
                    if mkt['key'] == 'h2h':
                        ocs = {abbr(o['name']): o['price'] for o in mkt['outcomes']}
                        if aw in ocs and hm in ocs:
                            fav = hm if ocs[hm] < ocs[aw] else aw
                            fo  = ocs[fav]
                            imp = abs(fo)/(abs(fo)+100)*100 if fo < 0 else 100/(fo+100)*100
                            pr  = round(imp)
                    elif mkt['key'] == 'totals' and mkt.get('outcomes'):
                        ou = float(mkt['outcomes'][0].get('point', 8.0))
                        od = 'O' if mkt['outcomes'][0].get('name') == 'Over' else 'U'
            entry = {'lg':lg,'aw':aw,'af':af,'hm':hm,'hf':hf,'tm':tm,'fav':fav,'fo':fo,'ou':ou,'od':od,'pr':pr}
            if   gdate == today:    today_games.append(entry)
            elif gdate == tomorrow: tmrw_games.append(entry)
    def sort_key(g):
        try:
            parts = g['tm'].split(':')
            h = int(parts[0]); rest = parts[1].split()
            m = int(rest[0]); ap = rest[1]
            if ap == 'PM' and h != 12: h += 12
            if ap == 'AM' and h == 12: h = 0
            return h * 60 + m
        except: return 9999
    today_games.sort(key=sort_key); tmrw_games.sort(key=sort_key)
    return today_games, tmrw_games

def fetch_finals():
    finals, seen = [], set()
    for sc in SPORT_CONFIG:
        url = (f"https://api.the-odds-api.com/v4/sports/{sc['key']}/scores/"
               f"?apiKey={ODDS_API_KEY}&daysFrom=3")
        data = fetch_json(url)
        if not data: continue
        for g in data:
            if not g.get('completed'): continue
            scores = {abbr(s['name']): s.get('score') for s in (g.get('scores') or [])}
            aw = abbr(g.get('away_team','')); af = g.get('away_team','')
            hm = abbr(g.get('home_team','')); hf = g.get('home_team','')
            aws = scores.get(aw); hms = scores.get(hm)
            if aws is None or hms is None: continue
            try: aws, hms = int(float(aws)), int(float(hms))
            except: continue
            k = f"{aw}@{hm}"
            if k not in seen:
                seen.add(k)
                finals.append({'lg':sc['lg'],'aw':aw,'af':af,'hm':hm,'hf':hf,'as':aws,'hs':hms})
    return finals[-40:]

def load_picks():
    try:
        import importlib.util
        # Look for picks.py in same dir as this script
        picks_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'picks.py')
        spec = importlib.util.spec_from_file_location('picks', picks_path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, 'PICKS', [])
    except Exception as e:
        print(f"  [picks] Could not load picks.py: {e}", file=sys.stderr)
        return []

def load_pga_picks():
    return [
        {'golfer':'Tommy Fleetwood',  'odds':'+120','note':'5 top-25 in last 8 Masters. T3 in 2024. Elite iron play at Augusta.','value':'Strong Value'},
        {'golfer':'Xander Schauffele','odds':'-145','note':'Three straight top-10s at Augusta. Elite ball-striker back in form.','value':'Value'},
        {'golfer':'Jordan Spieth',    'odds':'+105','note':'Augusta IQ unmatched. Superb scrambler on these specific breaks.','value':'Strong Value'},
        {'golfer':'Collin Morikawa',  'odds':'+130','note':'Elite tee-to-green. Back injury overpriced into his odds.','value':'Strong Value'},
        {'golfer':'Ludvig Aberg',     'odds':'-165','note':'Runner-up in Masters debut, T7 in 2025. Gaining steam with bettors.','value':'Value'},
        {'golfer':'Cameron Young',    'odds':'+110','note':'Peak form after 9-under 63 at THE PLAYERS.','value':'Value'},
        {'golfer':'Justin Rose',      'odds':'-180','note':'21st Masters start, 15 top-25 finishes. Runner-up 2025.','value':'Fair'},
        {'golfer':'Jake Knapp',       'odds':'+185','note':'Leads PGA Tour total strokes gained in 2026. T11+ in 6 of 7 starts.','value':'Strong Value'},
    ]

def generate_js_data(today_games, tmrw_games, finals, picks, pga_picks):
    data_date = date_str(et_now())
    today_lbl = fmt_label(et_now())
    tmrw_lbl  = fmt_label(et_now() + timedelta(days=1))

    def game_js(g):
        af = g['af'].replace("'","&#39;"); hf = g['hf'].replace("'","&#39;")
        return (f"  {{lg:'{g['lg']}',aw:'{g['aw']}',af:'{af}',hm:'{g['hm']}',hf:'{hf}',"
                f"tm:'{g['tm']}',fav:'{g['fav']}',fo:{g['fo']},ou:{g['ou']},od:'{g['od']}',pr:{g['pr']}}}")
    def final_js(f):
        af = f['af'].replace("'","&#39;"); hf = f['hf'].replace("'","&#39;")
        return f"  {{lg:'{f['lg']}',aw:'{f['aw']}',af:'{af}',hm:'{f['hm']}',hf:'{hf}',as:{f['as']},hs:{f['hs']}}}"
    def pick_js(p):
        return f"  {{aw:'{p['aw']}',hm:'{p['hm']}',lg:'{p['lg']}',pick:'{p['pick']}',odds:{p['odds']}}}"
    def pga_js(p):
        note = p['note'].replace("'","&#39;")
        return f"  {{golfer:'{p['golfer']}',odds:'{p['odds']}',note:'{note}',value:'{p['value']}'}}"

    picks_s  = ',\n'.join(pick_js(p) for p in picks)      or ''
    pga_s    = ',\n'.join(pga_js(p)  for p in pga_picks)  or ''
    finals_s = ',\n'.join(final_js(f) for f in finals)    or ''
    today_s  = ',\n'.join(game_js(g) for g in today_games) or ''
    tmrw_s   = ',\n'.join(game_js(g) for g in tmrw_games)  or ''

    return f"""var DATA_DATE    = '{data_date}';
var SHEET_CSV    = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQn5FvOpxjgT8sWb_HezeqjkTWMQj190-qA-ZmyOgsmd6j2YFySIozibt1PebFL2KWSvkXvVvbJhlSz/pub?output=csv';
var ODDS_API_KEY = '{ODDS_API_KEY}';
var SPORT_KEYS   = ['icehockey_nhl','baseball_mlb','basketball_nba'];
var LEAGUE_ORDER = ['NHL','MLB','NBA','NCAAMBB','PGA','NFL','NCAACB'];
var REC = {{W:79,L:95,T:1,pct:'45.4',last10:['W','L','W','L','W','L','W','L','W','L'],pend:0}};
var SPORT_REC = {{NHL:{{W:0,L:0}},MLB:{{W:0,L:0}},NBA:{{W:0,L:0}},PGA:{{W:0,L:0}},NFL:{{W:0,L:0}},NCAAMBB:{{W:0,L:0}},NCAACB:{{W:0,L:0}}}};
/* picks loaded from picks.py */
var PICKS = [
{picks_s}
];
var PGA_PICKS = [
{pga_s}
];
var FINALS = [
{finals_s}
];
/* TODAY = {today_lbl} */
var TODAY = [
{today_s}
];
/* TMRW = {tmrw_lbl} */
var TMRW = [
{tmrw_s}
];
var LIVE_SCORES = {{}};"""

# ─── FETCH AND BUILD ───────────────────────────────────────────────────────────
print("Fetching game data from Odds API...")
try:
    today_games, tmrw_games = fetch_today_and_tomorrow()
    finals                  = fetch_finals()
    print(f"  Today: {len(today_games)} | Tomorrow: {len(tmrw_games)} | Finals: {len(finals)}")
except Exception as e:
    print(f"  [API] WARN: {e}", file=sys.stderr)
    today_games, tmrw_games, finals = [], [], []

picks     = load_picks()
pga_picks = load_pga_picks()
print(f"  Picks: {len(picks)}")

js_data = generate_js_data(today_games, tmrw_games, finals, picks, pga_picks)

# Section labels for HTML
now_et    = et_now()
today_lbl = fmt_label(now_et)
tmrw_lbl  = fmt_label(now_et + timedelta(days=1))


github_action = """\
name: Daily Slate Update

on:
  schedule:
    # Runs at 11 AM UTC = 7 AM ET (EDT, Mar-Nov)
    # During EST (Nov-Mar) change to: '0 12 * * *'
    - cron: '0 11 * * *'
  workflow_dispatch:  # also allows manual trigger from GitHub Actions tab

jobs:
  update-slate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Build dashboard (fetches live odds automatically)
        env:
          ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}
        run: python3 build_v3.py

      - name: Commit and push updated dashboard
        run: |
          git config user.name "PuckPicksBot"
          git config user.email "bot@puckpicks.com"
          git add index.html
          git diff --staged --quiet || git commit -m "Auto slate update: $(TZ=America/New_York date '+%a %b %-d')"
          git push
"""

# ─── MAIN HTML ───────────────────────────────────────────────────────────────
page = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <meta name="theme-color" content="#0A0E14"/>
  <title>Puck&#39;s Picks</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;900&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet"/>
  <style>
    /* ─ TOKENS ─ */
    :root {
      --gold:#F5B800; --ice:#8ABDD8; --green:#00C97B; --red:#FF4D5A; --amber:#FF9A00;
      --dark1:#0A0E14; --dark2:#111720; --dark3:#1A2232; --dark4:#22304A;
      --text:#E8EDF4; --muted:#7A8FA8; --border:rgba(255,255,255,.08);
      --card-radius:12px; --tab-radius:8px;
    }
    *, *::before, *::after { box-sizing:border-box; margin:0; padding:0; }
    html { scroll-behavior:smooth; }
    body { font-family:'Barlow',sans-serif; background:var(--dark1); color:var(--text); min-height:100vh; }

    /* ─ TICKER ─ */
    .tkr { background:var(--dark2); border-bottom:2px solid var(--gold); overflow:hidden; height:36px; position:relative; }
    .tkr-t { display:flex; white-space:nowrap; position:absolute; top:0; left:0; height:100%; align-items:center; will-change:transform; }
    .ti { display:inline-flex; align-items:center; gap:6px; padding:0 14px; border-right:1px solid var(--border); height:100%; font-family:'Barlow Condensed',sans-serif; font-size:12px; }
    .ti-tm { font-weight:700; color:var(--text); text-transform:uppercase; letter-spacing:.5px; }
    .ti-sc { font-weight:900; font-size:13px; }
    .ti-sc.hi { color:var(--green); } .ti-sc.lo { color:var(--muted); }
    .ti-lbl { font-size:9px; color:var(--amber); font-weight:700; letter-spacing:1px; text-transform:uppercase; }
    .ti-fav { color:var(--gold); font-weight:700; }
    .ti-ou { color:var(--ice); font-weight:600; }
    .ti-sep { color:var(--muted); font-size:9px; }
    .ti-dot { width:4px; height:4px; border-radius:50%; background:var(--gold); opacity:.4; flex-shrink:0; }
    .ti-hdr { padding:0 10px; height:100%; display:inline-flex; align-items:center; font-family:'Barlow Condensed',sans-serif; font-size:9px; letter-spacing:2px; text-transform:uppercase; border-right:1px solid rgba(245,184,0,.3); background:rgba(245,184,0,.08); color:var(--gold); }
    .ti-hdr.fin { background:rgba(138,189,216,.08); color:var(--ice); border-color:rgba(138,189,216,.3); }
    .ti-live { display:inline-block; width:5px; height:5px; border-radius:50%; background:var(--red); animation:blink 1s infinite; flex-shrink:0; margin-right:2px; }
    @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.15} }

    /* ─ STATUS BAR ─ */
    .sbar { background:var(--dark3); border-bottom:1px solid var(--border); padding:4px 20px; display:flex; align-items:center; justify-content:space-between; gap:8px; flex-wrap:wrap; }
    .sbar-l { display:flex; align-items:center; gap:8px; min-width:0; }
    .sbar-r { display:flex; align-items:center; gap:8px; flex-shrink:0; }
    .sdot { width:8px; height:8px; border-radius:50%; background:var(--green); flex-shrink:0; transition:background .3s; }
    .sdot.off { background:var(--red); } .sdot.conn { background:var(--amber); animation:blink 1s infinite; }
    .stxt { font-family:'Barlow Condensed',sans-serif; font-size:12px; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .stxt strong { color:var(--text); }
    .cdt { font-family:'Barlow Condensed',sans-serif; font-size:11px; color:var(--muted); }
    .rbtn { background:transparent; border:1px solid var(--border); border-radius:4px; padding:3px 9px; font-family:'Barlow Condensed',sans-serif; font-size:10px; color:var(--muted); cursor:pointer; letter-spacing:1px; text-transform:uppercase; transition:all .15s; }
    .rbtn:hover { color:var(--gold); border-color:var(--gold); }

    /* ─ HEADER ─ */
    .hdr { background:var(--dark2); border-bottom:1px solid var(--border); padding:10px 20px; display:flex; align-items:center; justify-content:space-between; gap:12px; }
    .hdr-l { display:flex; align-items:center; gap:14px; min-width:0; }
    .logo { height:58px; width:58px; border-radius:50%; object-fit:cover; border:2px solid var(--gold); flex-shrink:0; }
    .logo-t .ttl { font-family:'Barlow Condensed',sans-serif; font-size:22px; font-weight:900; letter-spacing:2px; color:var(--gold); text-transform:uppercase; }
    .logo-t .sub { font-size:11px; color:var(--muted); letter-spacing:1px; text-transform:uppercase; margin-top:1px; }
    .hdr-r { display:flex; gap:8px; align-items:center; flex-shrink:0; }
    .spill { background:var(--dark3); border:1px solid var(--border); border-radius:8px; padding:6px 12px; text-align:center; min-width:64px; }
    .spill .n { font-family:'Barlow Condensed',sans-serif; font-size:17px; font-weight:700; color:var(--gold); white-space:nowrap; }
    .spill .l { font-size:9px; color:var(--muted); letter-spacing:1px; text-transform:uppercase; margin-top:1px; }

    /* ─ STREAK ─ */
    .strk { background:var(--dark2); border-bottom:1px solid var(--border); padding:8px 20px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
    .strk-lbl { font-family:'Barlow Condensed',sans-serif; font-size:11px; letter-spacing:1.5px; text-transform:uppercase; color:var(--muted); white-space:nowrap; }
    .strk-pills { display:flex; gap:3px; flex-wrap:nowrap; }
    .sp { width:24px; height:24px; border-radius:4px; display:flex; align-items:center; justify-content:center; font-family:'Barlow Condensed',sans-serif; font-size:11px; font-weight:700; flex-shrink:0; }
    .sp.W { background:rgba(0,201,123,.2); color:var(--green); border:1px solid rgba(0,201,123,.4); }
    .sp.L { background:rgba(255,77,90,.2); color:var(--red); border:1px solid rgba(255,77,90,.4); }
    .sp.T { background:rgba(138,189,216,.2); color:var(--ice); border:1px solid rgba(138,189,216,.4); }
    .sp.q { background:var(--dark4); color:var(--muted); border:1px solid var(--border); }
    .strk-em { font-size:18px; line-height:1; }
    .strk-sum { font-family:'Barlow Condensed',sans-serif; font-size:13px; color:var(--muted); }

    /* ─ SPORT STREAK BADGES (on tabs) ─ */
    .tab-rec { font-size:9px; font-weight:700; opacity:.7; display:block; letter-spacing:.5px; }

    /* ─ WARNINGS ─ */
    .warn { margin:8px 16px; border-radius:8px; padding:9px 14px; font-size:12px; line-height:1.5; display:none; }
    .warn.sheet { background:rgba(255,154,0,.08); border:1px solid rgba(255,154,0,.3); color:var(--amber); }
    .warn.stale { background:rgba(255,77,90,.08); border:1px solid rgba(255,77,90,.3); color:var(--red); }
    .warn a { color:var(--gold); text-decoration:underline; }

    /* ─ BEST BET ─ */
    .bb { margin:10px 16px 0; background:linear-gradient(135deg,rgba(245,184,0,.13),rgba(245,184,0,.03)); border:1px solid var(--gold); border-radius:var(--card-radius); padding:12px 16px; display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
    .bb-l { display:flex; align-items:center; gap:12px; }
    .bb-bdg { background:var(--gold); color:var(--dark1); font-family:'Barlow Condensed',sans-serif; font-size:10px; font-weight:900; letter-spacing:2px; padding:3px 8px; border-radius:4px; white-space:nowrap; flex-shrink:0; }
    .bb-m { font-family:'Barlow Condensed',sans-serif; font-size:18px; font-weight:700; color:var(--text); }
    .bb-s { font-size:11px; color:var(--muted); margin-top:1px; }
    .bb-r { text-align:right; }
    .bb-rl { font-size:9px; color:var(--muted); letter-spacing:1.5px; text-transform:uppercase; margin-bottom:2px; }
    .bb-rv { font-family:'Barlow Condensed',sans-serif; font-size:22px; font-weight:900; color:var(--gold); line-height:1; }
    .bb-ro { font-size:11px; color:var(--muted); margin-top:2px; }
    /* Unit size badge inside best bet */
    .bb-unit { display:inline-block; background:rgba(245,184,0,.2); border:1px solid rgba(245,184,0,.4); border-radius:4px; padding:1px 6px; font-family:'Barlow Condensed',sans-serif; font-size:11px; font-weight:700; color:var(--gold); margin-left:6px; }

    /* ─ TABS ─ */
    .tabs-wrap { position:relative; }
    .tabs { display:flex; gap:6px; padding:12px 16px 0; overflow-x:auto; scrollbar-width:none; -webkit-overflow-scrolling:touch; }
    .tabs::-webkit-scrollbar { display:none; }
    .tabs-wrap::after { content:''; position:absolute; right:0; top:0; width:32px; height:100%; background:linear-gradient(to right,transparent,var(--dark1)); pointer-events:none; }
    .tab { background:var(--dark3); border:1px solid var(--border); border-radius:var(--tab-radius); padding:6px 12px; font-family:'Barlow Condensed',sans-serif; font-size:12px; font-weight:600; color:var(--muted); letter-spacing:.5px; text-transform:uppercase; cursor:pointer; white-space:nowrap; transition:all .15s; line-height:1.3; }
    .tab:hover { color:var(--text); border-color:rgba(255,255,255,.2); }
    .tab.on { background:var(--gold); color:var(--dark1); border-color:var(--gold); }
    .tab.on .tab-rec { opacity:.6; }

    /* ─ SECTION HEADS ─ */
    .sh { display:flex; align-items:center; gap:10px; padding:14px 16px 8px; }
    .sh h2 { font-family:'Barlow Condensed',sans-serif; font-size:14px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:var(--text); }
    .sb { background:var(--gold); color:var(--dark1); font-size:10px; font-weight:700; padding:2px 6px; border-radius:3px; letter-spacing:1px; white-space:nowrap; }
    .sb.dim { background:var(--dark4); color:var(--muted); }
    .sl { flex:1; height:1px; background:var(--border); }

    /* ─ GRID ─ */
    .gg { display:grid; grid-template-columns:repeat(auto-fill,minmax(290px,1fr)); gap:10px; padding:0 16px; }

    /* ─ GAME CARD ─ */
    .gc { background:var(--dark2); border:1px solid var(--border); border-radius:var(--card-radius); overflow:hidden; transition:border-color .2s, box-shadow .2s; }
    .gc:hover { border-color:rgba(245,184,0,.3); box-shadow:0 4px 20px rgba(0,0,0,.3); }
    .gc.live-card { border-color:rgba(255,77,90,.3); }
    .gc-top { padding:11px 14px 9px; border-bottom:1px solid var(--border); }
    .gm { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
    .gm-l { display:flex; align-items:center; gap:6px; }
    .stag { font-size:10px; font-weight:700; letter-spacing:1.5px; text-transform:uppercase; padding:2px 6px; border-radius:3px; }
    .stag.nhl { background:rgba(212,237,255,.1); color:var(--ice); }
    .stag.mlb { background:rgba(0,201,123,.1); color:var(--green); }
    .stag.nba { background:rgba(245,184,0,.1); color:var(--gold); }
    .stag.pga { background:rgba(0,201,123,.08); color:#6BCB77; }
    .stag.nfl { background:rgba(255,77,90,.1); color:var(--red); }
    .stag.ncaambb { background:rgba(245,184,0,.1); color:var(--gold); }
    .stag.ncaacb { background:rgba(138,189,216,.1); color:var(--ice); }
    .live-badge { display:inline-flex; align-items:center; gap:4px; background:rgba(255,77,90,.15); border:1px solid rgba(255,77,90,.35); border-radius:3px; padding:1px 6px; font-size:9px; font-weight:700; color:var(--red); letter-spacing:1px; }
    .finbdg { font-size:10px; font-weight:700; color:var(--muted); letter-spacing:1px; font-family:'Barlow Condensed',sans-serif; }
    .gtm { font-size:11px; color:var(--muted); }
    .mu { display:flex; align-items:center; gap:8px; }
    .tc { flex:1; min-width:0; }
    .tab-ab { font-family:'Barlow Condensed',sans-serif; font-size:20px; font-weight:900; letter-spacing:1px; line-height:1; }
    .tc.away .tab-ab { color:var(--muted); }
    .tc.home .tab-ab { color:var(--text); }
    .tn { font-size:10px; color:var(--muted); margin-top:1px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    /* Live score on card */
    .tc-score { font-family:'Barlow Condensed',sans-serif; font-size:22px; font-weight:900; line-height:1; margin-top:2px; }
    .tc-score.leading { color:var(--green); }
    .tc-score.trailing { color:var(--muted); }
    .tc-score.tied { color:var(--amber); }
    /* Final score */
    .tsf { font-family:'Barlow Condensed',sans-serif; font-size:22px; font-weight:900; line-height:1; margin-top:2px; }
    .tsf.win { color:var(--green); } .tsf.loss { color:var(--muted); }
    .at { font-family:'Barlow Condensed',sans-serif; color:var(--muted); font-size:13px; flex-shrink:0; }
    /* Period/inning indicator */
    .game-period { font-size:10px; color:var(--red); font-weight:700; letter-spacing:.5px; text-align:center; margin-top:4px; }

    /* ─ PROB BAR ─ */
    .pb { height:3px; background:var(--dark4); margin:0 14px; border-radius:2px; overflow:hidden; }
    .pf { height:100%; background:var(--gold); border-radius:2px; transition:width .4s ease; }

    /* ─ ODDS ROW ─ */
    .co { display:flex; padding:8px 14px; }
    .ob { flex:1; text-align:center; padding:6px 3px; }
    .ob+.ob { border-left:1px solid var(--border); }
    .ol { font-size:9px; color:var(--muted); letter-spacing:1px; text-transform:uppercase; margin-bottom:3px; }
    .ov { font-family:'Barlow Condensed',sans-serif; font-size:17px; font-weight:700; color:var(--text); line-height:1; }
    .ov.fav { color:var(--gold); }
    .ov.sprd { color:var(--amber); font-size:14px; }
    .os { font-size:10px; color:var(--muted); margin-top:1px; }
    .os.val { color:var(--amber); font-weight:600; }

    /* ─ CARD META (value + confidence) ─ */
    .card-meta { display:flex; align-items:center; justify-content:space-between; padding:4px 14px 6px; border-top:1px solid var(--border); }
    .val-strong { background:rgba(0,201,123,.12); color:var(--green); border:1px solid rgba(0,201,123,.3); font-family:'Barlow Condensed',sans-serif; font-size:10px; font-weight:700; letter-spacing:1px; padding:2px 6px; border-radius:3px; text-transform:uppercase; }
    .val-good { background:rgba(245,184,0,.1); color:var(--gold); border:1px solid rgba(245,184,0,.28); font-family:'Barlow Condensed',sans-serif; font-size:10px; font-weight:700; letter-spacing:1px; padding:2px 6px; border-radius:3px; text-transform:uppercase; }
    .val-fair { background:rgba(122,143,168,.08); color:var(--muted); border:1px solid var(--border); font-family:'Barlow Condensed',sans-serif; font-size:10px; letter-spacing:1px; padding:2px 6px; border-radius:3px; text-transform:uppercase; }
    .conf { font-family:'Barlow Condensed',sans-serif; font-size:11px; display:flex; align-items:center; gap:3px; }
    .conf-hi { color:var(--green); } .conf-mid { color:var(--gold); } .conf-lo { color:var(--muted); }

    /* ─ UNIT SIZE badge ─ */
    .unit-badge { display:inline-block; padding:1px 6px; border-radius:3px; font-family:'Barlow Condensed',sans-serif; font-size:10px; font-weight:700; letter-spacing:1px; text-transform:uppercase; }
    .unit-3 { background:rgba(0,201,123,.15); color:var(--green); border:1px solid rgba(0,201,123,.3); }
    .unit-2 { background:rgba(245,184,0,.12); color:var(--gold); border:1px solid rgba(245,184,0,.28); }
    .unit-1 { background:rgba(122,143,168,.08); color:var(--muted); border:1px solid var(--border); }

    /* ─ PUCK PICK ─ */
    .pp { display:flex; align-items:center; justify-content:space-between; gap:6px; padding:6px 14px 8px; border-top:1px solid rgba(245,184,0,.15); background:rgba(245,184,0,.04); }
    .pp-l { display:flex; align-items:center; gap:5px; }
    .pp-star { color:var(--gold); font-size:11px; }
    .pp-lbl { font-size:10px; color:var(--muted); letter-spacing:.5px; text-transform:uppercase; }
    .pp-val { font-family:'Barlow Condensed',sans-serif; font-size:14px; font-weight:700; color:var(--gold); }
    /* Share button */
    .pp-share { background:none; border:1px solid rgba(245,184,0,.3); border-radius:4px; padding:2px 7px; font-size:10px; color:var(--gold); cursor:pointer; letter-spacing:.5px; transition:all .15s; white-space:nowrap; }
    .pp-share:hover { background:rgba(245,184,0,.1); }

    /* ─ RESULT BADGE on Finals ─ */
    .result-w { display:inline-flex; align-items:center; gap:3px; background:rgba(0,201,123,.15); color:var(--green); border:1px solid rgba(0,201,123,.3); border-radius:4px; padding:2px 7px; font-family:'Barlow Condensed',sans-serif; font-size:10px; font-weight:700; letter-spacing:1px; }
    .result-l { display:inline-flex; align-items:center; gap:3px; background:rgba(255,77,90,.12); color:var(--red); border:1px solid rgba(255,77,90,.3); border-radius:4px; padding:2px 7px; font-family:'Barlow Condensed',sans-serif; font-size:10px; font-weight:700; letter-spacing:1px; }
    .fin-pick-row { display:flex; align-items:center; justify-content:space-between; padding:5px 14px 7px; border-top:1px solid var(--border); background:rgba(255,255,255,.02); }
    .fin-pick-txt { font-family:'Barlow Condensed',sans-serif; font-size:12px; color:var(--muted); }

    /* ─ PGA GOLFER CARD ─ */
    .pga-card { background:var(--dark2); border:1px solid var(--border); border-radius:var(--card-radius); overflow:hidden; transition:border-color .2s, box-shadow .2s; }
    .pga-card:hover { border-color:rgba(0,201,123,.3); box-shadow:0 4px 20px rgba(0,0,0,.3); }
    .pga-top { padding:12px 14px 10px; border-bottom:1px solid var(--border); }
    .pga-hd { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
    .pga-event { font-size:10px; color:#6BCB77; font-weight:700; letter-spacing:1.5px; text-transform:uppercase; }
    .pga-name { font-family:'Barlow Condensed',sans-serif; font-size:24px; font-weight:900; color:var(--text); line-height:1; }
    .pga-prop { font-size:11px; color:var(--muted); margin-top:3px; }
    .pga-odds-row { display:flex; align-items:center; justify-content:space-between; padding:8px 14px; }
    .pga-odds { font-family:'Barlow Condensed',sans-serif; font-size:22px; font-weight:900; color:var(--gold); }
    .pga-note { font-size:11px; color:var(--muted); padding:0 14px 10px; line-height:1.5; border-top:1px solid var(--border); padding-top:8px; }
    .pga-credit { font-size:10px; color:var(--muted); opacity:.6; margin-top:4px; }

    /* ─ EMPTY STATE ─ */
    .ng { padding:28px 20px; text-align:center; color:var(--muted); font-size:12px; font-family:'Barlow Condensed',sans-serif; letter-spacing:1px; text-transform:uppercase; }
    .ng-icon { font-size:28px; margin-bottom:8px; opacity:.4; }

    /* ─ DEBUG PANEL ─ */
    .dbg { display:none; margin:8px 16px; background:var(--dark3); border:1px solid var(--border); border-radius:6px; padding:10px 14px; font-family:monospace; font-size:11px; color:var(--muted); line-height:1.6; max-height:200px; overflow-y:auto; }
    .dbg.show { display:block; }

    /* ─ NOTIFICATION BUTTON ─ */
    .notif-btn { background:rgba(245,184,0,.1); border:1px solid rgba(245,184,0,.3); border-radius:4px; padding:3px 9px; font-family:'Barlow Condensed',sans-serif; font-size:10px; color:var(--gold); cursor:pointer; letter-spacing:1px; text-transform:uppercase; }
    .notif-btn:hover { background:rgba(245,184,0,.2); }
    .notif-btn.on { background:var(--gold); color:var(--dark1); }

    /* ─ RESPONSIVE ─ */
    @media(max-width:640px) {
      .hdr { flex-wrap:wrap; }
      .hdr-r { width:100%; justify-content:space-between; }
      .spill { flex:1; padding:5px 8px; }
      .spill .n { font-size:15px; }
      .bb { flex-direction:column; gap:8px; }
      .bb-r { text-align:left; width:100%; display:flex; align-items:center; gap:12px; }
      .bb-rv { font-size:20px; }
      .gg { grid-template-columns:1fr; }
      .logo { height:48px; width:48px; }
      .logo-t .ttl { font-size:18px; }
    }
    @media(max-width:400px) {
      .hdr-r { gap:4px; }
      .spill .n { font-size:13px; }
      .spill .l { font-size:8px; }
    }
  </style>
</head>
<body>

<div id="wrap">
  <!-- TICKER -->
  <div class="tkr"><div class="tkr-t" id="tkrT"></div></div>

  <!-- STATUS -->
  <div class="sbar">
    <div class="sbar-l"><div class="sdot conn" id="sDot"></div><span class="stxt" id="sTxt">Loading...</span></div>
    <div class="sbar-r">
      <span class="cdt" id="cdt"></span>
      <button class="notif-btn" id="notifBtn" onclick="toggleNotif()" title="Get notified when new picks drop">&#128276; Notify</button>
      <button class="rbtn" onclick="refreshAll()">&#8635; Refresh</button>
    </div>
  </div>

  <!-- HEADER -->
  <div class="hdr">
    <div class="hdr-l">
      <img class="logo" src="data:image/jpeg;base64,__BITMOJI__" alt="Puck"/>
      <div class="logo-t">
        <div class="ttl">Puck&#39;s Picks</div>
        <div class="sub">Sharp Betting Intelligence &middot; @Puck_BYBR</div>
      </div>
    </div>
    <div class="hdr-r">
      <div class="spill"><div class="n" id="recN">79-95-1</div><div class="l">2026 Record</div></div>
      <div class="spill"><div class="n" id="pctN">45.4%</div><div class="l">Win %</div></div>
      <div class="spill"><div class="n" id="pendN" style="color:var(--green)">&#8212;</div><div class="l">Pending</div></div>
    </div>
  </div>

  <!-- STREAK -->
  <div class="strk">
    <span class="strk-lbl">Last 10</span>
    <div class="strk-pills" id="sPills"></div>
    <span class="strk-em" id="sEm"></span>
    <span class="strk-sum" id="sSum"></span>
  </div>

  <!-- WARNINGS -->
  <div class="warn sheet" id="shWarn">
    &#9888; <strong>Record could not load from Google Sheet.</strong>
    Make sure it&#39;s shared publicly: <strong>File &rarr; Share &rarr; Anyone with the link &rarr; Viewer</strong>.
    <a href="#" onclick="refreshAll();return false;">Retry</a>
  </div>
  <div class="warn stale" id="staleWarn">
    &#128197; <strong>Today&#39;s slate is from a previous day.</strong>
    Game data updates each morning at 7 AM ET.
    <a href="#" onclick="location.reload();return false;">Reload now</a>
  </div>

  <!-- BEST BET -->
  <div class="bb" id="bbBanner">
    <div class="bb-l">
      <div class="bb-bdg">&#11088; BEST BET</div>
      <div>
        <div class="bb-m" id="bbM">Loading...</div>
        <div class="bb-s" id="bbS"></div>
      </div>
    </div>
    <div class="bb-r">
      <div class="bb-rl">Puck&#39;s Pick</div>
      <div class="bb-rv" id="bbV">&#8212;</div>
      <div class="bb-ro" id="bbO"></div>
    </div>
  </div>

  <!-- TABS -->
  <div class="tabs-wrap">
    <div class="tabs" id="tabRow">
      <button class="tab on" onclick="filt('ALL',this)">All</button>
      <button class="tab" onclick="filt('NHL',this)">&#127954; NHL<span class="tab-rec" id="rec-NHL"></span></button>
      <button class="tab" onclick="filt('MLB',this)">&#9918; MLB<span class="tab-rec" id="rec-MLB"></span></button>
      <button class="tab" onclick="filt('NBA',this)">&#127936; NBA<span class="tab-rec" id="rec-NBA"></span></button>
      <button class="tab" onclick="filt('NCAAMBB',this)">&#127891;&#127936; NCAA MBB<span class="tab-rec" id="rec-NCAAMBB"></span></button>
      <button class="tab" onclick="filt('PGA',this)">&#9971; PGA<span class="tab-rec" id="rec-PGA"></span></button>
      <button class="tab" onclick="filt('NFL',this)">&#127944; NFL<span class="tab-rec" id="rec-NFL"></span></button>
      <button class="tab" onclick="filt('NCAACB',this)">&#127891;&#9918; NCAA CB<span class="tab-rec" id="rec-NCAACB"></span></button>
    </div>
  </div>

  <!-- TODAY -->
  <div class="sh"><h2>Today&#39;s Slate</h2><span class="sb" id="todayLbl">SAT APR 11</span><div class="sl"></div></div>
  <div class="gg" id="todayG"><div class="ng"><div class="ng-icon">&#128197;</div>Loading...</div></div>

  <!-- UPCOMING -->
  <div class="sh" style="margin-top:16px;"><h2>Upcoming</h2><span class="sb dim" id="tmrwLbl">SUN APR 12</span><div class="sl"></div></div>
  <div class="gg" id="tmrwG"><div class="ng">Loading...</div></div>

  <!-- FINALS -->
  <div class="sh" style="margin-top:16px;"><h2>Recent Finals</h2><span class="sb dim">APR 9&#8211;11</span><div class="sl"></div></div>
  <div class="gg" id="finG"><div class="ng">Loading...</div></div>

  <div class="dbg" id="dbgPanel"></div>
  <div style="height:40px;"></div>
</div>

<script>
/* ═══ CONFIG ═══ */
var REFRESH_SEC  = 60;
__AUTO_DATA__

/* ═══ DATE / TIME HELPERS ═══ */
function isDST(d){var j=new Date(d.getFullYear(),0,1).getTimezoneOffset(),u=new Date(d.getFullYear(),6,1).getTimezoneOffset();return d.getTimezoneOffset()<Math.max(j,u);}
function nowET(){var n=new Date(),off=isDST(n)?-4:-5;return new Date(n.getTime()+off*3600000);}
function todayStr(){var e=nowET();return e.getFullYear()+'-'+String(e.getMonth()+1).padStart(2,'0')+'-'+String(e.getDate()).padStart(2,'0');}
function fmtTime(d){var h=d.getHours(),m=d.getMinutes(),ap=h>=12?'PM':'AM';h=h%12||12;return h+':'+(m<10?'0':'')+m+' '+ap+' ET';}

/* gameIsPast — fully date-aware */
function gameIsPast(tm){
  if(!tm||/[A-Za-z]{3}\s+[A-Za-z]{3}/.test(tm)||tm.indexOf('Masters')>=0||tm.indexOf('R')===0) return false;
  var td=todayStr();
  if(DATA_DATE<td) return true;
  if(DATA_DATE>td) return false;
  try{
    var et=nowET(),p=tm.match(/(\d+):(\d+)\s*(AM|PM)/i);if(!p)return false;
    var h=parseInt(p[1]),m=parseInt(p[2]),ap=p[3].toUpperCase();
    if(ap==='PM'&&h!==12)h+=12;if(ap==='AM'&&h===12)h=0;
    var gMs=new Date(et.getFullYear(),et.getMonth(),et.getDate(),h,m,0).getTime();
    return (et.getTime()-gMs)>1800000;
  }catch(e){return false;}
}

/* ═══ HELPERS ═══ */
function fmt(n){return n>0?'+'+n:''+n;}
function scm(l){return {NHL:'nhl',MLB:'mlb',NBA:'nba',PGA:'pga',NFL:'nfl',NCAAMBB:'ncaambb',NCAACB:'ncaacb',NCAA:'ncaacb'}[l]||'nhl';}

function getPick(aw,hm,lg){
  var p=PICKS.find(function(p){return p.aw===aw&&p.hm===hm&&p.lg===lg;});
  if(!p) return null;
  var game=TODAY.find(function(g){return g.aw===aw&&g.hm===hm&&g.lg===lg;});
  if(!game||gameIsPast(game.tm)) return null;
  return p;
}

function sugSpread(lg,fav,odds,hasPick){
  if(hasPick||odds>-200) return null;
  var m={NHL:{l:fav+' -1.5',o:-115},MLB:{l:fav+' -1.5',o:-115},NBA:{l:fav+' -5.5',o:-112}};
  return m[lg]||null;
}

/* Value rating using implied probability vs our estimate */
function valueRating(prob,odds){
  var imp=odds<0?Math.abs(odds)/(Math.abs(odds)+100)*100:100/(odds+100)*100;
  var edge=prob-imp;
  if(edge>=8) return {label:'Strong Value',cls:'val-strong'};
  if(edge>=4) return {label:'Value',cls:'val-good'};
  if(edge>=-2) return {label:'Fair',cls:'val-fair'};
  return null;
}

/* Confidence tier */
function confidence(pr){
  if(pr>=80)return{stars:'&#9733;&#9733;&#9733;',lbl:'High',cls:'conf-hi'};
  if(pr>=62)return{stars:'&#9733;&#9733;',lbl:'Med',cls:'conf-mid'};
  return{stars:'&#9733;',lbl:'Low',cls:'conf-lo'};
}

/* Unit size recommendation based on edge */
function unitSize(prob,odds){
  var imp=odds<0?Math.abs(odds)/(Math.abs(odds)+100)*100:100/(odds+100)*100;
  var edge=prob-imp;
  if(edge>=8)  return {n:3, cls:'unit-3', lbl:'3u Strong'};
  if(edge>=4)  return {n:2, cls:'unit-2', lbl:'2u Value'};
  if(edge>=-2) return {n:1, cls:'unit-1', lbl:'1u Lean'};
  return null;
}

/* ═══ STREAK ═══ */
function renderStreak(last10){
  var el=document.getElementById('sPills'); el.innerHTML='';
  last10.forEach(function(r){
    var d=document.createElement('div');
    var cls=r==='W'?'W':r==='L'?'L':r==='T'?'T':'q';
    d.className='sp '+cls; d.textContent=r==='-'?'?':r; el.appendChild(d);
  });
  var w=last10.filter(function(x){return x==='W';}).length;
  var l=last10.filter(function(x){return x==='L';}).length;
  document.getElementById('sSum').textContent=w+'W - '+l+'L';
  var em=w>=7?'&#128293;':l>=7?'&#10052;&#65039;':'&#128528;';
  document.getElementById('sEm').innerHTML=em;
}

/* ═══ PER-SPORT RECORDS on tabs ═══ */
function updateSportRecs(){
  LEAGUE_ORDER.forEach(function(lg){
    var el=document.getElementById('rec-'+lg);
    if(!el) return;
    var r=SPORT_REC[lg];
    if(r&&(r.W+r.L)>0) el.textContent=r.W+'-'+r.L;
    else el.textContent='';
  });
}

/* ═══ SHEET FETCH ═══ */
async function fetchSheet(){
  var NL=String.fromCharCode(10),CR=String.fromCharCode(13),QUOT=String.fromCharCode(34);
  var dbg=document.getElementById('dbgPanel');
  try{
    var res=await fetch(SHEET_CSV,{signal:AbortSignal.timeout(12000)});
    if(!res.ok) throw new Error('HTTP '+res.status);
    var text=await res.text();
    if(!text||text.length<10) throw new Error('empty response');

    function parseCSV(raw){
      var out=[],lines=raw.trim().split(CR).join('').split(NL);
      for(var li=0;li<lines.length;li++){
        var line=lines[li],cols=[],cur='',inQ=false;
        for(var ci=0;ci<line.length;ci++){
          var ch=line[ci];
          if(ch===QUOT){if(inQ&&line[ci+1]===QUOT){cur+=QUOT;ci++;}else inQ=!inQ;}
          else if(ch===','&&!inQ){cols.push(cur.trim());cur='';}
          else cur+=ch;
        }
        cols.push(cur.trim()); out.push(cols);
      }
      return out;
    }

    var rows=parseCSV(text);
    var hi=-1,dateCol=-1,resultCol=-1,pickCol=-1,lgCol=-1;
    for(var i=0;i<Math.min(rows.length,15);i++){
      var rr=rows[i];
      for(var c=0;c<rr.length;c++){
        var v=rr[c].toUpperCase().trim();
        if(v==='DATE'||v==='DATE/TIME') dateCol=c;
        if(v==='RESULT'||v==='W/L'||v==='RESULT (W/L)'||v==='OUTCOME') resultCol=c;
        if(v==='PICK'||v==='MY PICK'||v==='BET'||v==='PICK/BET') pickCol=c;
        if(v==='SPORT'||v==='LEAGUE'||v==='SPORT/LEAGUE') lgCol=c;
      }
      if(dateCol>=0&&resultCol>=0){hi=i;break;}
    }

    console.log('[Sheet] rows:'+rows.length+' hi:'+hi+' resultCol:'+resultCol+' lgCol:'+lgCol);
    if(hi>=0) console.log('[Sheet] header:',rows[hi]);

    if(hi<0||resultCol<0){
      var msg='Sheet connected but headers not found. Row0: '+JSON.stringify(rows[0]||[]);
      dbg.textContent=msg; dbg.classList.add('show');
      throw new Error(msg);
    }

    var picks=[],sportPicks={};
    for(var i2=hi+1;i2<rows.length;i2++){
      var v2=(rows[i2][resultCol]||'').trim().toUpperCase();
      var lg2=lgCol>=0?(rows[i2][lgCol]||'').trim().toUpperCase():'ALL';
      var res2=v2==='W'?'W':v2==='L'?'L':(v2==='P'||v2==='T'||v2==='PUSH')?'T':null;
      if(res2){
        picks.push(res2);
        if(lg2&&lg2!=='ALL'){
          if(!sportPicks[lg2]) sportPicks[lg2]={W:0,L:0,T:0};
          if(res2==='W') sportPicks[lg2].W++;
          else if(res2==='L') sportPicks[lg2].L++;
          else sportPicks[lg2].T++;
        }
      }
    }

    /* Update per-sport records */
    Object.keys(sportPicks).forEach(function(lg){
      var key=lg.toUpperCase();
      if(SPORT_REC[key]) SPORT_REC[key]={W:sportPicks[lg].W,L:sportPicks[lg].L};
    });
    updateSportRecs();

    var W=picks.filter(function(x){return x==='W';}).length;
    var L=picks.filter(function(x){return x==='L';}).length;
    var T=picks.filter(function(x){return x==='T';}).length;
    var pct=(W+L)>0?(W/(W+L)*100).toFixed(1):'0.0';

    var pend=0,pc=pickCol>=0?pickCol:(resultCol>0?resultCol-1:4);
    for(var i3=rows.length-1;i3>hi;i3--){
      var rw=rows[i3],rv=(rw[resultCol]||'').trim().toUpperCase(),hp=rw[pc]&&rw[pc].trim().length>0;
      if(hp&&rv==='') pend++;
      else if(rv==='W'||rv==='L'||rv==='P'||rv==='T') break;
    }

    var last10=picks.slice(-10);
    while(last10.length<10) last10.unshift('-');

    dbg.classList.remove('show');
    return{W:W,L:L,T:T,pct:pct,pend:pend,last10:last10};
  }catch(e){
    console.warn('[Sheet]',e.message);
    if(dbg.textContent) dbg.classList.add('show');
    return null;
  }
}

/* ═══ LIVE SCORES FETCH ═══ */
async function fetchLiveScores(){
  for(var s=0;s<SPORT_KEYS.length;s++){
    try{
      var r=await fetch('https://api.the-odds-api.com/v4/sports/'+SPORT_KEYS[s]+'/scores/?apiKey='+ODDS_API_KEY+'&daysFrom=1',{signal:AbortSignal.timeout(8000)});
      if(!r.ok) continue;
      var games=await r.json();
      games.forEach(function(g){
        var key=abbrTeam(g.away_team)+'@'+abbrTeam(g.home_team);
        var awS=null,hmS=null;
        if(g.scores) g.scores.forEach(function(sc){
          if(abbrTeam(sc.name)===abbrTeam(g.away_team)) awS=sc.score;
          else hmS=sc.score;
        });
        LIVE_SCORES[key]={awayScore:awS,homeScore:hmS,completed:!!g.completed,live:!g.completed&&awS!==null};
      });
    }catch(e){console.warn('[LiveScores]',SPORT_KEYS[s],e.message);}
  }
}

/* ═══ TODAY ODDS AUTO-FETCH ═══ */
async function fetchTodaysOdds(){
  var sports=[{key:'icehockey_nhl',lg:'NHL'},{key:'baseball_mlb',lg:'MLB'},{key:'basketball_nba',lg:'NBA'}];
  for(var s=0;s<sports.length;s++){
    try{
      var r=await fetch('https://api.the-odds-api.com/v4/sports/'+sports[s].key+'/odds/?apiKey='+ODDS_API_KEY+'&regions=us&markets=h2h,totals&oddsFormat=american&daysFrom=1',{signal:AbortSignal.timeout(8000)});
      if(!r.ok) continue;
      var games=await r.json();
      games.forEach(function(g){
        var start=new Date(g.commence_time),off=isDST(start)?-4:-5;
        var etStart=new Date(start.getTime()+off*3600000);
        var gDate=etStart.getFullYear()+'-'+String(etStart.getMonth()+1).padStart(2,'0')+'-'+String(etStart.getDate()).padStart(2,'0');
        if(gDate!==todayStr()) return;
        var aw=abbrTeam(g.away_team),hm=abbrTeam(g.home_team),lg=sports[s].lg;
        if(TODAY.some(function(x){return x.aw===aw&&x.hm===hm&&x.lg===lg;})) return;
        var h=etStart.getHours(),m=etStart.getMinutes(),ap=h>=12?'PM':'AM',h12=h%12||12;
        var tmStr=h12+':'+(m<10?'0':'')+m+' '+ap+' ET';
        var fo=-110,ou=0,od='O',pr=50,fav=hm;
        if(g.bookmakers&&g.bookmakers.length){
          var bk=g.bookmakers[0];
          var h2h=(bk.markets||[]).find(function(m){return m.key==='h2h';});
          var tot=(bk.markets||[]).find(function(m){return m.key==='totals';});
          if(h2h&&h2h.outcomes){
            var awO=h2h.outcomes.find(function(o){return abbrTeam(o.name)===aw;});
            var hmO=h2h.outcomes.find(function(o){return abbrTeam(o.name)===hm;});
            if(awO&&hmO){fo=hmO.price<awO.price?hmO.price:awO.price;fav=hmO.price<awO.price?hm:aw;pr=Math.round(fo<0?Math.abs(fo)/(Math.abs(fo)+100)*100:100/(fo+100)*100);}
          }
          if(tot&&tot.outcomes&&tot.outcomes.length){ou=parseFloat(tot.outcomes[0].point)||0;od=tot.outcomes[0].name==='Over'?'O':'U';}
        }
        TODAY.push({lg:lg,aw:aw,af:g.away_team,hm:hm,hf:g.home_team,tm:tmStr,fav:fav,fo:fo,ou:ou,od:od,pr:pr});
      });
    }catch(e){console.warn('[TodayOdds]',sports[s].lg,e.message);}
  }
  TODAY.sort(function(a,b){return parseTimeToMins(a.tm)-parseTimeToMins(b.tm);});
}

function parseTimeToMins(tm){if(!tm)return 9999;var m=tm.match(/(\d+):(\d+)\s*(AM|PM)/i);if(!m)return 9999;var h=parseInt(m[1]),mi=parseInt(m[2]),ap=m[3].toUpperCase();if(ap==='PM'&&h!==12)h+=12;if(ap==='AM'&&h===12)h=0;return h*60+mi;}

function abbrTeam(name){
  var map={'Tampa Bay Lightning':'TB','Buffalo Sabres':'BUF','Boston Bruins':'BOS','Carolina Hurricanes':'CAR','Ottawa Senators':'OTT','Florida Panthers':'FLA','Montreal Canadiens':'MTL','Philadelphia Flyers':'PHI','New Jersey Devils':'NJ','New York Rangers':'NYR','Calgary Flames':'CGY','Dallas Stars':'DAL','Edmonton Oilers':'EDM','Utah Mammoth':'UTA','Nashville Predators':'NSH','Anaheim Ducks':'ANA','Vegas Golden Knights':'VGK','Vancouver Canucks':'VAN','Columbus Blue Jackets':'CBJ','Detroit Red Wings':'DET','Seattle Kraken':'SEA','Winnipeg Jets':'WPG','Chicago Blackhawks':'CHI','San Jose Sharks':'SJ','Los Angeles Kings':'LA','Minnesota Wild':'MIN','Pittsburgh Penguins':'PIT','New York Islanders':'NYI','Washington Capitals':'WSH','Colorado Avalanche':'COL','St. Louis Blues':'STL','Toronto Maple Leafs':'TOR','Cleveland Guardians':'CLE','Kansas City Royals':'KC','San Diego Padres':'SD','Cincinnati Reds':'CIN','Miami Marlins':'MIA','Milwaukee Brewers':'MIL','Boston Red Sox':'BOS','St. Louis Cardinals':'STL','Washington Nationals':'WSH','Athletics':'ATH','New York Yankees':'NYY','Los Angeles Dodgers':'LAD','Toronto Blue Jays':'TOR','Baltimore Orioles':'BAL','Chicago White Sox':'CWS','Detroit Tigers':'DET','Minnesota Twins':'MIN','Seattle Mariners':'SEA','Texas Rangers':'TEX','Houston Astros':'HOU','Colorado Rockies':'COL','Atlanta Braves':'ATL','Los Angeles Angels':'LAA','Philadelphia Phillies':'PHI','San Francisco Giants':'SF','Arizona Diamondbacks':'AZ','New York Mets':'NYM','Chicago Cubs':'CHC','Tampa Bay Rays':'TB','Pittsburgh Pirates':'PIT','Minnesota Timberwolves':'MIN','Indiana Pacers':'IND','Chicago Bulls':'CHI','Washington Wizards':'WAS','Milwaukee Bucks':'MIL','Brooklyn Nets':'BKN','Miami Heat':'MIA','Toronto Raptors':'TOR','Charlotte Hornets':'CHA','Boston Celtics':'BOS','New Orleans Pelicans':'NOP','Utah Jazz':'UTA','Oklahoma City Thunder':'OKC','Dallas Mavericks':'DAL','LA Clippers':'LAC','Los Angeles Lakers':'LAL','Houston Rockets':'HOU','Phoenix Suns':'PHX','Memphis Grizzlies':'MEM','Denver Nuggets':'DEN','Portland Trail Blazers':'POR','Sacramento Kings':'SAC','Golden State Warriors':'GSW','San Antonio Spurs':'SAS','Cleveland Cavaliers':'CLE','Atlanta Hawks':'ATL','Detroit Pistons':'DET','Orlando Magic':'ORL'};
  return map[name]||(name||'').split(' ').pop().substring(0,3).toUpperCase();
}

/* ═══ PICK RESULT CHECK ═══ */
function pickResult(p, g){
  /* Determine if a completed pick won or lost based on scores */
  if(!p||!g||g.as===undefined||g.hs===undefined) return null;
  var pick=p.pick.toUpperCase();
  /* ML pick */
  if(pick.indexOf(' ML')>=0){
    var team=pick.replace(' ML','').trim();
    var teamWon=(team===g.aw&&g.as>g.hs)||(team===g.hm&&g.hs>g.as);
    return teamWon?'W':'L';
  }
  /* -1.5 spread */
  if(pick.indexOf('-1.5')>=0){
    var team2=pick.replace(' -1.5','').trim();
    var margin=(team2===g.aw)?(g.as-g.hs):(g.hs-g.as);
    return margin>1.5?'W':'L';
  }
  /* +1.5 spread */
  if(pick.indexOf('+1.5')>=0){
    var team3=pick.replace(' +1.5','').trim();
    var margin2=(team3===g.aw)?(g.as-g.hs):(g.hs-g.as);
    return margin2>-1.5?'W':'L';
  }
  /* -5.5 NBA spread */
  if(pick.indexOf('-5.5')>=0){
    var team4=pick.replace(' -5.5','').trim();
    var margin3=(team4===g.aw)?(g.as-g.hs):(g.hs-g.as);
    return margin3>5.5?'W':'L';
  }
  return null;
}

/* ═══ SHARE PICK ═══ */
function sharePick(aw,hm,lg,pick,odds){
  var NL=String.fromCharCode(10);
  var oddsStr=(odds>0?'+':'')+odds;
  var emojis={NHL:'[NHL]',MLB:'[MLB]',NBA:'[NBA]',PGA:'[PGA]'};
  var lgTag=emojis[lg]||'[PICK]';
  var text=lgTag+' Puck Pick: '+aw+' @ '+hm+NL+'★ '+pick+' ('+oddsStr+')'+NL+NL+'Follow @Puck_BYBR for daily picks';
  var shareUrl='https://puckbybr.github.io/pucks-picks/';
  if(navigator.share){
    navigator.share({text:text,url:shareUrl}).catch(function(){});
  } else {
    var tw='https://twitter.com/intent/tweet?text='+encodeURIComponent(text)+'&url='+encodeURIComponent(shareUrl);
    window.open(tw,'_blank');
  }
}

/* ═══ NOTIFICATIONS ═══ */
function toggleNotif(){
  var btn=document.getElementById('notifBtn');
  if(!('Notification' in window)){alert('Browser notifications not supported.');return;}
  if(Notification.permission==='granted'){
    /* Toggle off */
    localStorage.removeItem('notifOn');
    btn.classList.remove('on');
    btn.innerHTML='&#128276; Notify';
  } else {
    Notification.requestPermission().then(function(p){
      if(p==='granted'){
        localStorage.setItem('notifOn','1');
        btn.classList.add('on');
        btn.innerHTML='&#128276; On';
        new Notification("Puck's Picks",{body:"You'll be notified when new picks drop!",icon:'/pucks-picks/icon.png'});
      }
    });
  }
}
function sendPickNotif(pick){
  if(Notification.permission==='granted'&&localStorage.getItem('notifOn')){
    new Notification('New Pick: '+pick.pick,{body:pick.aw+' @ '+pick.hm+' '+fmt(pick.odds),icon:'/pucks-picks/icon.png'});
  }
}
/* Init notification button state */
(function(){
  if(Notification.permission==='granted'&&localStorage.getItem('notifOn')){
    var btn=document.getElementById('notifBtn');
    btn.classList.add('on'); btn.innerHTML='&#128276; On';
  }
})();

/* ═══ PGA CARD ═══ */
function buildPGACard(g){
  var pgaPick=PGA_PICKS.find(function(p){return p.golfer===g.hf;});
  var val=pgaPick?pgaPick.value:'';
  var note=pgaPick?pgaPick.note:'Top-20 finish value play.';
  var valCls=val==='Strong Value'?'val-strong':val==='Value'?'val-good':'val-fair';
  var oddsStr=fmt(g.fo);
  var shareBtn=pgaPick?'<button class="pp-share" data-aw="'+g.aw+'" data-hm="'+g.hm+'" data-lg="PGA" data-pick="Top 20" data-odds="'+g.fo+'" onclick="sharePickEl(this)">&#128257; Share</button>':'';
  return '<div class="pga-card">'
    +'<div class="pga-top">'
    +'<div class="pga-hd"><span class="pga-event">&#9971; Masters 2026</span>'+(pgaPick?'<span class="'+valCls+'">'+val+'</span>':'')+'</div>'
    +'<div class="pga-name">'+g.hf+'</div>'
    +'<div class="pga-prop">Top-20 Finish &middot; via <strong>RunRickGood</strong></div>'
    +'</div>'
    +'<div class="pga-odds-row"><span class="pga-odds">'+oddsStr+'</span>'+shareBtn+'</div>'
    +'<div class="pga-note">'+note+'<div class="pga-credit">&#128249; RunRickGood on YouTube</div></div>'
    +'</div>';
}

function buildCard(g, showPicks){
  if(g.lg==='PGA') return buildPGACard(g);

  var pp=showPicks?getPick(g.aw,g.hm,g.lg):null;
  var sug=sugSpread(g.lg,g.fav,g.fo,!!pp);
  var ouL=g.lg==='NBA'?g.od+' '+g.ou+' pts':g.od+' '+g.ou;

  /* Check for live score */
  var liveKey=g.aw+'@'+g.hm;
  var liveData=LIVE_SCORES[liveKey];
  var isLive=liveData&&liveData.live;

  var favBlk=sug
    ?'<div class="ob"><div class="ol">Spread</div><div class="ov sprd">'+sug.l+'</div><div class="os val">'+fmt(sug.o)+' value</div></div>'
    :'<div class="ob"><div class="ol">Fav / ML</div><div class="ov fav">'+g.fav+'</div><div class="os">'+fmt(g.fo)+'</div></div>';

  var ppHtml='';
  if(pp){
    var us=unitSize(g.pr,g.fo);
    var shareBtn='<button class="pp-share" data-aw="'+g.aw+'" data-hm="'+g.hm+'" data-lg="'+g.lg+'" data-pick="'+pp.pick+'" data-odds="'+pp.odds+'" onclick="sharePickEl(this)">&#128257; Share</button>';
    ppHtml='<div class="pp"><div class="pp-l"><span class="pp-star">&#9733;</span><span class="pp-lbl">Pick:</span><span class="pp-val">'+pp.pick+' ('+fmt(pp.odds)+')</span>'+(us?'<span class="unit-badge '+us.cls+'">'+us.lbl+'</span>':'')+'</div>'+shareBtn+'</div>';
  }


  var vr=valueRating(g.pr,g.fo);
  var cf=confidence(g.pr);
  var metaHtml='<div class="card-meta">'
    +(vr?'<span class="'+vr.cls+'">'+vr.label+'</span>':'<span></span>')
    +'<span class="conf '+cf.cls+'">'+cf.stars+' '+cf.lbl+'</span>'
    +'</div>';

  /* Live score display in matchup */
  var awScore='',hmScore='',periodHtml='',liveBadge='';
  if(isLive){
    var awN=parseInt(liveData.awayScore||0),hmN=parseInt(liveData.homeScore||0);
    var awCls=awN>hmN?'leading':awN<hmN?'trailing':'tied';
    var hmCls=hmN>awN?'leading':hmN<awN?'trailing':'tied';
    awScore='<div class="tc-score '+awCls+'">'+awN+'</div>';
    hmScore='<div class="tc-score '+hmCls+'">'+hmN+'</div>';
    liveBadge='<div class="live-badge"><span class="ti-live"></span>LIVE</div>';
  }

  return '<div class="gc'+(isLive?' live-card':'')+'">'
    +'<div class="gc-top">'
    +'<div class="gm"><div class="gm-l"><span class="stag '+scm(g.lg)+'">'+g.lg+'</span>'+liveBadge+'</div><span class="gtm">'+g.tm+'</span></div>'
    +'<div class="mu">'
    +'<div class="tc away"><div class="tab-ab">'+g.aw+'</div><div class="tn">'+g.af+'</div>'+awScore+'</div>'
    +'<div class="at">@</div>'
    +'<div class="tc home"><div class="tab-ab">'+g.hm+'</div><div class="tn">'+g.hf+'</div>'+hmScore+'</div>'
    +'</div></div>'
    +'<div class="pb"><div class="pf" style="width:'+g.pr+'%"></div></div>'
    +'<div class="co">'+favBlk
    +'<div class="ob"><div class="ol">O / U</div><div class="ov">'+ouL+'</div><div class="os">-110</div></div>'
    +'<div class="ob"><div class="ol">Win Prob</div><div class="ov">'+g.pr+'%</div><div class="os">'+(g.fav===g.hm?'Home':'Away')+' Fav</div></div>'
    +'</div>'+metaHtml+ppHtml+'</div>';
}

/* ═══ FINAL CARD — with pick result badge ═══ */
function buildFin(g){
  var aw=g.as>g.hs,hw=g.hs>g.as;
  /* Check if there was a pick on this game */
  var historicPick=PICKS.find(function(p){return p.aw===g.aw&&p.hm===g.hm&&p.lg===g.lg;});
  var resultRow='';
  if(historicPick){
    var res=pickResult(historicPick,g);
    if(res){
      var resCls=res==='W'?'result-w':'result-l';
      var resIcon=res==='W'?'&#10003;':'&#10007;';
      resultRow='<div class="fin-pick-row"><span class="fin-pick-txt">&#9733; '+historicPick.pick+' ('+fmt(historicPick.odds)+')</span><span class="'+resCls+'">'+resIcon+' '+res+'</span></div>';
    }
  }
  return '<div class="gc">'
    +'<div class="gc-top">'
    +'<div class="gm"><span class="stag '+scm(g.lg)+'">'+g.lg+'</span><span class="finbdg">FINAL</span></div>'
    +'<div class="mu">'
    +'<div class="tc away"><div class="tab-ab">'+g.aw+'</div><div class="tn">'+g.af+'</div><div class="tsf '+(aw?'win':'loss')+'">'+g.as+'</div></div>'
    +'<div class="at">@</div>'
    +'<div class="tc home"><div class="tab-ab">'+g.hm+'</div><div class="tn">'+g.hf+'</div><div class="tsf '+(hw?'win':'loss')+'">'+g.hs+'</div></div>'
    +'</div></div>'+resultRow+'</div>';
}

/* ═══ RENDER ═══ */
var CL='ALL';
function filt(l,btn){
  CL=l;
  document.querySelectorAll('.tab').forEach(function(b){b.classList.remove('on');});
  btn.classList.add('on');
  render();
}
function render(){
  function f(g){return CL==='ALL'||g.lg===CL;}
  var tg=TODAY.filter(f).filter(function(g){return !gameIsPast(g.tm);});
  var tmg=TMRW.filter(f);
  var fg=FINALS.filter(f);
  document.getElementById('todayG').innerHTML=tg.length
    ?tg.map(function(g){return buildCard(g,true);}).join('')
    :'<div class="ng"><div class="ng-icon">&#9200;</div>No upcoming '+CL+' games today</div>';
  document.getElementById('tmrwG').innerHTML=tmg.length
    ?tmg.map(function(g){return buildCard(g,false);}).join('')
    :'<div class="ng">No '+CL+' games tomorrow</div>';
  document.getElementById('finG').innerHTML=fg.length
    ?fg.map(buildFin).join('')
    :'<div class="ng">No '+CL+' finals</div>';
  var pend=tg.filter(function(g){return !!getPick(g.aw,g.hm,g.lg);}).length;
  document.getElementById('pendN').textContent=REC.pend||pend||'&#8212;';
}

/* ═══ BEST BET ═══ */
function updateBestBet(){
  var banner=document.getElementById('bbBanner');
  if(!banner) return;
  var best=null;
  for(var i=0;i<PICKS.length;i++){
    var p=PICKS[i];
    var game=TODAY.find(function(g){return g.aw===p.aw&&g.hm===p.hm&&g.lg===p.lg;});
    if(game&&!gameIsPast(game.tm)){best={pick:p,game:game};break;}
  }
  if(!best){banner.style.display='none';return;}
  banner.style.display='';
  var us=unitSize(best.game.pr,best.pick.odds);
  document.getElementById('bbM').textContent=best.game.aw+' @ '+best.game.hm;
  document.getElementById('bbS').innerHTML=best.game.lg+' &middot; '+best.game.tm;
  document.getElementById('bbV').textContent=best.pick.pick;
  var oddsStr=(best.pick.odds>0?'+':'')+best.pick.odds;
  document.getElementById('bbO').innerHTML=oddsStr+(us?' <span class="bb-unit">'+us.lbl+'</span>':'');
}

/* ═══ TICKER ═══ */
var tPos=0,tAnim,tLast=0;
function buildTicker(){
  cancelAnimationFrame(tAnim);tPos=0;tLast=0;
  var tk=document.getElementById('tkrT');
  tk.style.transform='translateX(0)';tk.innerHTML='';

  function hdr(lbl,cls){var d=document.createElement('div');d.className='ti-hdr'+(cls?' '+cls:'');d.innerHTML=lbl;return d;}
  function scoreItem(aw,hm,awS,hwS,isLive){
    var d=document.createElement('div');d.className='ti';
    var awI=parseInt(awS)||0,hwI=parseInt(hwS)||0;
    var awW=awI>hwI,hwW=hwI>awI;
    var dot=isLive?'<span class="ti-live"></span>':'';
    d.innerHTML=dot+'<span class="ti-tm">'+aw+'</span>'+'<span class="ti-sc '+(awW?'hi':'lo')+'">'+awI+'</span>'+'<span class="ti-sep">&#8212;</span>'+'<span class="ti-sc '+(hwW?'hi':'lo')+'">'+hwI+'</span>'+'<span class="ti-tm">'+hm+'</span>'+'<span class="ti-lbl">'+(isLive?'LIVE':'FINAL')+'</span>'+'<span class="ti-dot"></span>';
    return d;
  }
  function oddsItem(g){
    var d=document.createElement('div');d.className='ti';
    d.innerHTML='<span class="ti-tm">'+g.aw+'@'+g.hm+'</span>'+'<span class="ti-sep">|</span>'+'<span class="ti-fav">'+g.fav+' '+fmt(g.fo)+'</span>'+'<span class="ti-sep">|</span>'+'<span class="ti-ou">O/U '+g.ou+'</span>'+'<span class="ti-dot"></span>';
    return d;
  }

  function fill(){
    var live={},pre={},fins={};
    LEAGUE_ORDER.forEach(function(l){live[l]=[];pre[l]=[];fins[l]=[];});
    TODAY.forEach(function(g){
      if(g.lg==='PGA') return;
      var key=g.aw+'@'+g.hm,sc=LIVE_SCORES[key],lg=g.lg;
      if(!live[lg]) live[lg]=[]; if(!pre[lg]) pre[lg]=[];
      if(sc&&sc.live) live[lg].push({g:g,sc:sc});
      else if(!gameIsPast(g.tm)) pre[lg].push(g);
    });
    FINALS.forEach(function(g){if(!fins[g.lg])fins[g.lg]=[];fins[g.lg].push(g);});

    var hasLive=LEAGUE_ORDER.some(function(l){return live[l]&&live[l].length;});
    var hasPre=LEAGUE_ORDER.some(function(l){return pre[l]&&pre[l].length;});
    var hasFin=LEAGUE_ORDER.some(function(l){return fins[l]&&fins[l].length;});

    if(hasLive){
      tk.appendChild(hdr('&#128308; LIVE','fin'));
      LEAGUE_ORDER.forEach(function(l){(live[l]||[]).forEach(function(item){tk.appendChild(scoreItem(item.g.aw,item.g.hm,item.sc.awayScore,item.sc.homeScore,true));});});
    }
    if(hasPre){
      tk.appendChild(hdr('&#127919; TODAY',''));
      LEAGUE_ORDER.forEach(function(l){(pre[l]||[]).forEach(function(g){tk.appendChild(oddsItem(g));});});
    }
    if(hasFin){
      tk.appendChild(hdr('FINALS','fin'));
      LEAGUE_ORDER.forEach(function(l){(fins[l]||[]).forEach(function(g){var key=g.aw+'@'+g.hm,sc=LIVE_SCORES[key];var awS=sc&&sc.completed?sc.awayScore:g.as;var hwS=sc&&sc.completed?sc.homeScore:g.hs;tk.appendChild(scoreItem(g.aw,g.hm,awS,hwS,false));});});
    }
  }
  fill();fill();

  var SPEED=38;
  requestAnimationFrame(function loop(ts){
    if(tLast){var half=tk.scrollWidth/2;if(half>0){tPos+=SPEED*((ts-tLast)/1000);if(tPos>=half)tPos=0;tk.style.transform='translateX(-'+tPos+'px)';}}
    tLast=ts;tAnim=requestAnimationFrame(loop);
  });
}

/* ═══ STATUS ═══ */
function setS(state,msg){
  document.getElementById('sDot').className='sdot'+(state==='live'?'':state==='conn'?' conn':' off');
  document.getElementById('sTxt').innerHTML=msg;
}

/* ═══ COUNTDOWN ═══ */
var cs=REFRESH_SEC,ct;
function startCd(){clearInterval(ct);cs=REFRESH_SEC;uCd();ct=setInterval(function(){cs--;uCd();if(cs<=0)refreshAll();},1000);}
function uCd(){document.getElementById('cdt').textContent='Refresh in '+cs+'s';}

/* ═══ STALE CHECK ═══ */
function checkStale(){
  var stale=DATA_DATE<todayStr();
  document.getElementById('staleWarn').style.display=stale?'block':'none';
}

/* ═══ 7 AM RELOAD ═══ */
function schedule7amReload(){
  var et=nowET(),next7=new Date(et);
  next7.setHours(7,0,5,0);
  if(et>=next7) next7.setDate(next7.getDate()+1);
  var ms=next7.getTime()-et.getTime();
  console.log('[7AM] Reload in '+(ms/3600000).toFixed(1)+'h');
  setTimeout(function(){location.reload();},ms);
}

/* ═══ MAIN REFRESH ═══ */
async function refreshAll(){
  setS('conn','Fetching...');
  var results=await Promise.allSettled([fetchSheet(),fetchLiveScores(),fetchTodaysOdds()]);
  var sh=results[0].status==='fulfilled'?results[0].value:null;
  var warn=document.getElementById('shWarn');

  if(sh&&(sh.W+sh.L+sh.T)>0){
    REC=Object.assign({},REC,sh);
    document.getElementById('recN').textContent=sh.W+'-'+sh.L+'-'+sh.T;
    document.getElementById('pctN').textContent=sh.pct+'%';
    document.getElementById('pendN').textContent=sh.pend||'&#8212;';
    renderStreak(sh.last10);
    warn.style.display='none';
    setS('live','Live &middot; <strong>'+new Date().toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'})+'</strong>');
  } else {
    renderStreak(REC.last10);
    document.getElementById('recN').textContent=REC.W+'-'+REC.L+'-'+REC.T;
    document.getElementById('pctN').textContent=REC.pct+'%';
    warn.style.display='block';
    setS('off','Sheet offline &mdash; <a href="#" onclick="refreshAll();return false;" style="color:var(--gold);text-decoration:underline;">Retry</a>');
  }

  render();
  buildTicker();
  updateBestBet();
  checkStale();
  updateSportRecs();
  startCd();

  /* Notify if new picks and notification permission granted */
  PICKS.forEach(function(p){
    var game=TODAY.find(function(g){return g.aw===p.aw&&g.hm===p.hm&&g.lg===p.lg;});
    if(game&&!gameIsPast(game.tm)){sendPickNotif(p);}
  });
}

/* ═══ INIT ═══ */
renderStreak(REC.last10);
render();
buildTicker();
updateBestBet();
checkStale();
schedule7amReload();
refreshAll();
</script>
</body>
</html>"""

page = page.replace('__BITMOJI__', bitmoji)
page = page.replace('__AUTO_DATA__', js_data)
page = page.replace('>SAT APR 11<', f'>{today_lbl}<')
page = page.replace('>SUN APR 12<', f'>{tmrw_lbl}<')

# Fallback: replace any remaining hardcoded date labels
import re as _re
page = _re.sub(r'id="todayLbl">[^<]+<', f'id="todayLbl">{today_lbl}<', page)
page = _re.sub(r'id="tmrwLbl">[^<]+<',  f'id="tmrwLbl">{tmrw_lbl}<',   page)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Dashboard done! {len(page):,} bytes -> index.html")

# Write the GitHub Action
os.makedirs('/home/claude/github_action', exist_ok=True)
with open('/home/claude/github_action/daily-update.yml', 'w') as f:
    f.write(github_action)
print("GitHub Action written.")
