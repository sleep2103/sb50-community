#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
성북50+ 커뮤니티 최신글 보드 자동 생성기
------------------------------------------------
- 20개 커뮤니티를 방문 → 각자 최신 글(제목/날짜/작성자/사진) 수집
- 최신순으로 정렬 → index.html(카드 보드) 생성
- 외부 패키지 불필요(파이썬 표준 라이브러리만). GitHub Actions에서 그대로 실행됨.

실행:
    python scraper.py          # 실제로 사이트를 방문해 index.html 생성 (GitHub용)
    python scraper.py --seed   # 사이트 방문 없이 내장 데이터로 첫 index.html 생성
"""

import argparse, html, re, sys, time, urllib.request
from datetime import datetime, timezone, timedelta
from urllib.error import URLError, HTTPError

BASE = "https://www.50plus.or.kr"
LIST_URL = BASE + "/sbc/community.do"
LIST_PAGES = 2
DELAY = 0.8
TIMEOUT = 20
KST = timezone(timedelta(hours=9))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

RE_COMMUNITY = re.compile(r'community-home\.do\?id=(\d+)"[^>]*>\s*([^<]+?)\s*<', re.I)
RE_POST = re.compile(
    r'community-member-post-view\.do\?CM_NO=(\d+)&(?:amp;)?POST_NO=(\d+)"[^>]*>\s*([^<]+?)\s*<', re.I)
RE_DATE = re.compile(r'(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}')
RE_IMG = re.compile(r'(/upload/im/[^"\'\)\s]+?\.(?:jpg|jpeg|png|gif))', re.I)
RE_AUTHORDATE = re.compile(
    r'([가-힣A-Za-z]{2,12})\s*\(\s*(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}\s*\)')


# ------- 내장 시드 데이터 (첫 화면 생성용. 이후 실제 방문이 덮어씀) -------
SEED_CARDS = [
    {"community":"순수사진예술","url":BASE+"/sbc/community-member-post-view.do?CM_NO=45901904&POST_NO=9475",
     "title":"(2026.6.12) 청계천·인사동 출사","sub":"사진강습 후 결성한 출사 모임",
     "meta":"이승규 · 2026.06.12","date":"2026-06-12","photo":None},
    {"community":"서투른 솜씨자랑","url":BASE+"/sbc/community-member-post-view.do?CM_NO=42435654&POST_NO=8802",
     "title":"사회공헌활동 목도리 만들기","sub":"취약계층을 위한 목도리 만들기 활동",
     "meta":"김윤희 · 2025.11.18","date":"2025-11-18",
     "photo":BASE+"/upload/im/2025/11/b01f328b-c684-4f51-afb4-ed0f441cec74.jpg"},
    {"community":"브레인핏 실버인지","url":BASE+"/sbc/community-home.do?id=73531462",
     "title":"치매 예방 교육의 전문성을 강화하는 실버인지 연구 모임","sub":"",
     "meta":"운영 김소영 · 회원 14명 · 2026년","date":"","photo":None},
    {"community":"서울 브레인댄스 연구소","url":BASE+"/sbc/community-home.do?id=70910302",
     "title":"댄스테라피·표현예술상담 수료생들의 지역 돌봄 봉사단체","sub":"",
     "meta":"운영 정민영 · 회원 9명 · 2026년","date":"","photo":None},
    {"community":"FunFun한 긍정사주","url":BASE+"/sbc/community-home.do?id=68301489",
     "title":"긍정적으로 삶을 바라보며 지켜내는 모임","sub":"",
     "meta":"운영 김성주 · 회원 12명 · 2025년","date":"","photo":None},
    {"community":"향기는 바람을 타고 제품 팩토리","url":BASE+"/sbc/community-home.do?id=45896744",
     "title":"퍼스널 역량의 비즈니스화를 실행하는 실전 유닛","sub":"",
     "meta":"운영 강홍석 · 회원 12명 · 2025년","date":"","photo":None},
    {"community":"보문 하모니카 커뮤니티","url":BASE+"/sbc/community-home.do?id=45991081",
     "title":"매주 모여 하모니카를 학습하고 활동하는 모임","sub":"",
     "meta":"운영 유순기 · 회원 8명 · 2024년","date":"","photo":None},
    {"community":"오이시이 니홍고","url":BASE+"/sbc/community-home.do?id=45968416",
     "title":"일본어 기초를 탄탄히 배워 지역 행사·센터 활동에 기여","sub":"",
     "meta":"운영 박종선 · 회원 6명 · 2023년","date":"","photo":None},
    {"community":"SB하모니카","url":BASE+"/sbc/community-home.do?id=45878503",
     "title":"보문동에서 하모니카를 하는 사람들의 모임","sub":"",
     "meta":"운영 황정수 · 회원 8명 · 2024년","date":"","photo":None},
    {"community":"타로톡방","url":BASE+"/sbc/community-home.do?id=45878281",
     "title":"타로로 소통하고 성장하는 공간, 초보부터 환영","sub":"",
     "meta":"운영 박자영 · 회원 20명 · 2024년","date":"","photo":None},
    {"community":"부동산 경매로 내집 마련하기","url":BASE+"/sbc/community-home.do?id=45644012",
     "title":"부동산 경매·전세사기 예방법을 함께 공부","sub":"",
     "meta":"운영 이창훈 · 회원 15명 · 2024년","date":"","photo":None},
    {"community":"성북사랑 KCN 뉴스 시민기자단","url":BASE+"/sbc/community-home.do?id=44852593",
     "title":"성북의 소식을 널리 알리는 시민기자단 모임","sub":"",
     "meta":"운영 김영윤 · 회원 8명 · 2024년","date":"","photo":None},
    {"community":"옳음환경교육","url":BASE+"/sbc/community-home.do?id=43274665",
     "title":"환경교육 프로그램·교구·교재를 개발하는 모임","sub":"",
     "meta":"운영 안정희 · 회원 10명 · 2022년","date":"","photo":None},
    {"community":"시니어모델실전","url":BASE+"/sbc/community-home.do?id=42703055",
     "title":"시니어 모델로 사회에 진출할 역량을 갖추는 모임","sub":"",
     "meta":"운영 구본미 · 회원 8명 · 2024년","date":"","photo":None},
    {"community":"시니어인지플러스","url":BASE+"/sbc/community-home.do?id=41901577",
     "title":"치매 예방·시니어 교육 강사 역량을 강화하는 커뮤니티","sub":"",
     "meta":"운영 김명순 · 회원 15명 · 2023년","date":"","photo":None},
    {"community":"정통연극연구소","url":BASE+"/sbc/community-home.do?id=40460677",
     "title":"정기공연·사회공헌을 겸한 정통연극 소모임","sub":"",
     "meta":"운영 이종섭 · 회원 10명 · 2024년","date":"","photo":None},
    {"community":"토탈공예커뮤니티","url":BASE+"/sbc/community-home.do?id=38061486",
     "title":"자율 운영으로 즐겁고 행복한 삶을 함께하는 공예 모임","sub":"",
     "meta":"운영 이수정 · 회원 6명 · 2024년","date":"","photo":None},
    {"community":"중장년 연극단 오아시스","url":BASE+"/sbc/community-home.do?id=37349798",
     "title":"연극 기초를 토대로 연극단을 활성화하는 모임","sub":"",
     "meta":"운영 송경미 · 회원 11명 · 2023년","date":"","photo":None},
    {"community":"빛그림 동인회 · 그림","url":BASE+"/sbc/community-home.do?id=37031382",
     "title":"다양한 재료로 도약하는 작품을 연구하는 그림 모임","sub":"",
     "meta":"운영 이석영 · 회원 10명 · 2023년","date":"","photo":None},
    {"community":"두근두근뇌운동","url":BASE+"/sbc/community-home.do?id=47979341",
     "title":"인지자극 활동으로 신체 기능 유지·향상을 도모하는 모임","sub":"",
     "meta":"운영 김여정 · 회원 6명 · 2022년","date":"","photo":None},
]

# 커뮤니티별 한 줄 소개 (실제 방문 시 카드 부제로 사용)
DESC = {c["community"].split(" ·")[0]: c["title"] for c in SEED_CARDS}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


def clean(t):
    t = html.unescape(t or "")
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


def gather():
    """실제로 사이트를 방문해 최신 글 카드 목록을 만든다."""
    communities, seen = [], set()
    for p in range(1, LIST_PAGES + 1):
        url = LIST_URL if p == 1 else f"{LIST_URL}?pageIndex={p}&"
        try:
            page = fetch(url); time.sleep(DELAY)
        except (URLError, HTTPError) as e:
            print(f"[!] 목록 {p} 실패: {e}", file=sys.stderr); continue
        for cid, name in RE_COMMUNITY.findall(page):
            if cid not in seen:
                seen.add(cid); communities.append((cid, clean(name)))

    cards = []
    for cid, name in communities:
        try:
            home = fetch(f"{BASE}/sbc/community-home.do?id={cid}"); time.sleep(DELAY)
        except (URLError, HTTPError) as e:
            print(f"[!] {name} 홈 실패: {e}", file=sys.stderr); continue

        m = RE_POST.search(home)
        if not m:  # 게시글 없는 커뮤니티 → 소개 카드
            cards.append({"community": name, "url": f"{BASE}/sbc/community-home.do?id={cid}",
                          "title": DESC.get(name, name), "sub": "", "meta": "커뮤니티 둘러보기",
                          "date": "", "photo": None})
            continue
        cm, post, title = m.group(1), m.group(2), clean(m.group(3))
        d = RE_DATE.search(home)
        date = d.group(1) if d else ""
        post_url = f"{BASE}/sbc/community-member-post-view.do?CM_NO={cm}&POST_NO={post}"

        photo, author = None, ""
        try:
            detail = fetch(post_url); time.sleep(DELAY)
            im = RE_IMG.search(detail)
            if im: photo = BASE + im.group(1)
            ad = RE_AUTHORDATE.search(detail)
            if ad:
                author = clean(ad.group(1)); date = ad.group(2)
        except (URLError, HTTPError) as e:
            print(f"[!] {name} 글 실패: {e}", file=sys.stderr)

        meta = (f"{author} · {date.replace('-', '.')}" if author and date
                else (date.replace('-', '.') if date else "최근 글"))
        cards.append({"community": name, "url": post_url, "title": title,
                      "sub": DESC.get(name, ""), "meta": meta, "date": date, "photo": photo})
    return cards


def render(cards, generated):
    cards = sorted(cards, key=lambda c: c.get("date") or "", reverse=True)
    items = []
    for c in cards:
        comm = html.escape(c["community"]); title = html.escape(c["title"])
        sub = html.escape(c.get("sub") or ""); meta = html.escape(c.get("meta") or "")
        url = html.escape(c["url"]); photo = c.get("photo")
        subhtml = f'<div class="sub">{sub}</div>' if sub else ""
        if photo:
            items.append(f'''<a class="card photo" href="{url}" target="_blank" rel="noopener"
     style="background-image:linear-gradient(180deg,rgba(0,0,0,.05),rgba(0,0,0,.35) 55%,rgba(0,0,0,.82)),url('{html.escape(photo)}')">
  <span class="pill glass">{comm}</span>
  <div class="grow"></div>
  <div class="title light">{title}</div>
  <div class="meta light">{meta}</div>
</a>''')
        else:
            items.append(f'''<a class="card plain" href="{url}" target="_blank" rel="noopener">
  <span class="pill">{comm}</span>
  <div class="title">{title}</div>
  {subhtml}
  <div class="grow"></div>
  <div class="meta">{meta}</div>
</a>''')
    grid = "\n".join(items)
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>성북50+ 커뮤니티 소식</title>
<style>
  :root{{--ink:#1d1d1f;--dim:#8e8e93;--line:#ececf0;
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Apple SD Gothic Neo","Pretendard","Malgun Gothic",system-ui,sans-serif;}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:transparent;color:var(--ink);-webkit-font-smoothing:antialiased;padding:6px}}
  .head{{padding:6px 6px 4px}}
  h1{{font-size:24px;font-weight:700;letter-spacing:-.02em}}
  .sub-h{{color:var(--dim);font-size:14px;margin-top:4px}}
  .grid{{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));padding:12px 6px}}
  .card{{display:flex;flex-direction:column;min-height:210px;border-radius:18px;padding:20px;
    text-decoration:none;color:var(--ink);transition:transform .25s ease,box-shadow .25s ease;overflow:hidden}}
  .card:hover{{transform:translateY(-3px)}}
  .plain{{background:#fff;border:1px solid var(--line);box-shadow:0 1px 3px rgba(0,0,0,.06)}}
  .plain:hover{{box-shadow:0 10px 24px rgba(0,0,0,.10)}}
  .photo{{background-size:cover;background-position:center;color:#fff}}
  .photo:hover{{box-shadow:0 12px 28px rgba(0,0,0,.28)}}
  .grow{{flex:1}}
  .pill{{align-self:flex-start;font-size:12px;font-weight:600;color:#6e6e73;background:#f2f2f7;padding:5px 11px;border-radius:20px}}
  .pill.glass{{color:#fff;background:rgba(255,255,255,.24)}}
  .title{{font-size:15.5px;font-weight:600;line-height:1.45;margin-top:12px}}
  .title.light{{font-size:16px;font-weight:700;text-shadow:0 1px 12px rgba(0,0,0,.4)}}
  .sub{{font-size:13px;color:#6e6e73;line-height:1.5;margin-top:6px}}
  .meta{{font-size:12.5px;color:var(--dim);margin-top:10px}}
  .meta.light{{color:rgba(255,255,255,.85)}}
  .foot{{text-align:center;color:var(--dim);font-size:12px;padding:6px 0 12px}}
</style></head>
<body>
  <div class="head"><h1>성북50+ 커뮤니티 소식</h1>
  <div class="sub-h">최신 글을 올린 커뮤니티 순서로 보여드려요</div></div>
  <div class="grid">
{grid}
  </div>
  <div class="foot">자동 업데이트 · {generated}</div>
</body></html>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="사이트 방문 없이 내장 데이터로 생성")
    ap.add_argument("--out", default="index.html")
    args = ap.parse_args()

    now = datetime.now(KST).strftime("%Y.%m.%d %H:%M")
    cards = SEED_CARDS if args.seed else gather()
    if not cards:
        print("[!] 수집된 카드가 없습니다. 시드로 대체합니다.", file=sys.stderr)
        cards = SEED_CARDS
    html_out = render(cards, now)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"✅ {len(cards)}개 카드 → {args.out} ({now})")


if __name__ == "__main__":
    main()
