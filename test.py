from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime
import time
import re
import os
import requests

TEAM_NAMES = {
    "広島東洋カープ": "Hiroshima",
    "中日ドラゴンズ": "Chunichi",
    "阪神タイガース": "Hanshin",
    "読売ジャイアンツ": "Yomiuri",
    "横浜DeNAベイスターズ": "DeNA",
    "東京ヤクルトスワローズ": "Yakult",
    "福岡ソフトバンクホークス": "SoftBank",
    "千葉ロッテマリーンズ": "Lotte",
    "オリックス・バファローズ": "ORIX",
    "東北楽天ゴールデンイーグルス": "Rakuten",
    "北海道日本ハムファイターズ": "Nippon-Ham",
    "埼玉西武ライオンズ": "Seibu",
}
VENUE_NAMES = {
    "東京ドーム": "Tokyo Dome",
    "横　浜": "Yokohama Stadium",
    "横浜": "Yokohama Stadium",
    "マツダスタジアム": "Mazda Stadium",
    "ZOZOマリン": "ZOZO Marine Stadium",
    "京セラD大阪": "Kyocera Dome Osaka",
    "みずほPayPay": "Mizuho PayPay Dome",
    "甲子園": "Koshien Stadium",
    "神宮": "Jingu Stadium",
    "バンテリンD": "Vantelin Dome Nagoya",
    "札幌D": "Sapporo Dome",
    "ESコン": "ES CON FIELD",
    "楽天モバイル": "Rakuten Mobile Park",
    "ベルーナD": "Belluna Dome",
}
def get_all_scores():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get("https://npb.jp/games/2026/")
    time.sleep(8)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    results = {}

    for block in soup.find_all("div", class_="block"):
        h6 = block.find("h6", class_="date")
        if not h6:
            continue

        # 日付を取得（例：3月29日（日））
        date_text = h6.text.strip()
        m = re.search(r'(\d+)月(\d+)日', date_text)
        if not m:
            continue
        month = int(m.group(1))
        day = int(m.group(2))
        date_key = f"2026-{month:02d}-{day:02d}"

        games = []
        for tr in block.find_all("tr"):
            scores = tr.find_all("td", class_="score")
            imgs = tr.find_all("img")
            if len(scores) == 2 and len(imgs) >= 2:
                home_ja = imgs[0].get("alt", "")
                away_ja = imgs[1].get("alt", "")
                home = TEAM_NAMES.get(home_ja, home_ja)
                away = TEAM_NAMES.get(away_ja, away_ja)
                try:
                    home_score = int(scores[0].text.strip())
                    away_score = int(scores[1].text.strip())
                except:
                    continue

                venue = ""
                next_tr = tr.find_next_sibling("tr")
                if next_tr:
                    state = next_tr.find("td", class_="state")
                    if state:
                        venue_ja = state.text.strip()
                        venue = VENUE_NAMES.get(venue_ja, venue_ja)

                games.append({
                    "home": home,
                    "homeScore": home_score,
                    "away": away,
                    "awayScore": away_score,
                    "venue": venue,
                    "videoUrl": ""
                })

        if games:
            results[date_key] = games

    return results

def get_standings():
    url = "https://npb.jp/bis/2026/stats/"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    r.encoding = 'utf-8'
    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")

    def parse_table(table):
        rows = []
        for tr in table.find_all("tr")[1:]:
            cols = tr.find_all(["td", "th"])
            if len(cols) >= 6:
                # hide_pcのspan（短縮名）を使う
                name_span = cols[0].find("span", class_="hide_sp")
                name_ja = name_span.text.strip() if name_span else cols[0].text.strip()
                name = TEAM_NAMES.get(name_ja, name_ja)
                rows.append({
                    "name": name,
                    "g": cols[1].text.strip(),
                    "w": cols[2].text.strip(),
                    "l": cols[3].text.strip(),
                    "t": cols[4].text.strip(),
                    "pct": cols[5].text.strip(),
                    "gb": cols[6].text.strip() if len(cols) > 6 else "-"
                })
        return rows

    return {
        "central": parse_table(tables[0]) if len(tables) > 0 else [],
        "pacific": parse_table(tables[1]) if len(tables) > 1 else [],
        "updated": datetime.now().strftime("%B %d, %Y")
    }

def make_standings_js(standings):
    def rows(teams):
        result = ""
        for t in teams:
            result += f'    {{ name:"{t["name"]}", g:{t["g"]}, w:{t["w"]}, l:{t["l"]}, t:{t["t"]}, pct:"{t["pct"]}", gb:"{t["gb"]}" }},\n'
        return result
    return f'''const STANDINGS = {{
  updated: "{standings["updated"]}",
  central: [
{rows(standings["central"])}  ],
  pacific: [
{rows(standings["pacific"])}  ],
}};'''

def update_html(all_scores, standings):
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    added = 0
    for date_key, games in sorted(all_scores.items(), reverse=True):
        if f'date: "{date_key}"' in html:
            print(f"{date_key} はスキップ")
            continue

        new_block = f'  {{\n    date: "{date_key}",\n    games: [\n'
        for g in games:
            new_block += f'      {{\n        away: "{g["away"]}",\n        awayScore: {g["awayScore"]},\n        home: "{g["home"]}",\n        homeScore: {g["homeScore"]},\n        venue: "{g["venue"]}",\n        videoUrl: ""\n      }},\n'
        new_block += "    ]\n  },\n"

        html = html.replace("const DATA = [\n", f"const DATA = [\n\n{new_block}")
        print(f"{date_key} を追加 ({len(games)}試合)")
        added += 1

    html = re.sub(r'const STANDINGS = \{.*?\};', make_standings_js(standings), html, flags=re.DOTALL)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n合計 {added}日分を追加しました")

# 実行
print("データ取得中...")
all_scores = get_all_scores()
for date, games in all_scores.items():
    print(f"\n{date}: {len(games)}試合")
    for g in games:
        print(f"  {g['home']} {g['homeScore']} - {g['awayScore']} {g['away']}  {g['venue']}")

standings = get_standings()
print(f"\n順位表: セ{len(standings['central'])}チーム パ{len(standings['pacific'])}チーム")

update_html(all_scores, standings)