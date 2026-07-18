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

# 콘텐츠가 아닌 이미지(센터 로고 등)는 배경으로 쓰지 않음
IMG_EXCLUDE = (
    "36dd6ba3-8569-4d3c-9d75-2dddec9537a1",  # 성북50+ 센터 로고
)


# ------- 내장 시드 데이터 (첫 화면 생성용. 이후 실제 방문이 덮어씀) -------
SEED_CARDS = [
    {"community":"순수사진예술","url":BASE+"/sbc/community-member-post-view.do?CM_NO=45901904&POST_NO=9475",
     "title":"(2026.6.12) 청계천·인사동 출사","sub":"사진강습 후 결성한 출사 모임",
     "meta":"이승규 · 2026.06.12","date":"2026-06-12","photos":[]},
    {"community":"서투른 솜씨자랑","url":BASE+"/sbc/community-member-post-view.do?CM_NO=42435654&POST_NO=8802",
     "title":"사회공헌활동 목도리 만들기","sub":"취약계층을 위한 목도리 만들기 활동",
     "meta":"김윤희 · 2025.11.18","date":"2025-11-18",
     "photos":[BASE+"/upload/im/2025/11/b01f328b-c684-4f51-afb4-ed0f441cec74.jpg"]},
    {"community":"브레인핏 실버인지","url":BASE+"/sbc/community-home.do?id=73531462",
     "title":"치매 예방 교육의 전문성을 강화하는 실버인지 연구 모임","sub":"",
     "meta":"운영 김소영 · 회원 14명 · 2026년","date":"","photos":[]},
    {"community":"서울 브레인댄스 연구소","url":BASE+"/sbc/community-home.do?id=70910302",
     "title":"댄스테라피·표현예술상담 수료생들의 지역 돌봄 봉사단체","sub":"",
     "meta":"운영 정민영 · 회원 9명 · 2026년","date":"","photos":[]},
    {"community":"FunFun한 긍정사주","url":BASE+"/sbc/community-home.do?id=68301489",
     "title":"긍정적으로 삶을 바라보며 지켜내는 모임","sub":"",
     "meta":"운영 김성주 · 회원 12명 · 2025년","date":"","photos":[]},
    {"community":"향기는 바람을 타고 제품 팩토리","url":BASE+"/sbc/community-home.do?id=45896744",
     "title":"퍼스널 역량의 비즈니스화를 실행하는 실전 유닛","sub":"",
     "meta":"운영 강홍석 · 회원 12명 · 2025년","date":"","photos":[]},
    {"community":"보문 하모니카 커뮤니티","url":BASE+"/sbc/community-home.do?id=45991081",
     "title":"매주 모여 하모니카를 학습하고 활동하는 모임","sub":"",
     "meta":"운영 유순기 · 회원 8명 · 2024년","date":"","photos":[]},
    {"community":"오이시이 니홍고","url":BASE+"/sbc/community-home.do?id=45968416",
     "title":"일본어 기초를 탄탄히 배워 지역 행사·센터 활동에 기여","sub":"",
     "meta":"운영 박종선 · 회원 6명 · 2023년","date":"","photos":[]},
    {"community":"SB하모니카","url":BASE+"/sbc/community-home.do?id=45878503",
     "title":"보문동에서 하모니카를 하는 사람들의 모임","sub":"",
     "meta":"운영 황정수 · 회원 8명 · 2024년","date":"","photos":[]},
    {"community":"타로톡방","url":BASE+"/sbc/community-home.do?id=45878281",
     "title":"타로로 소통하고 성장하는 공간, 초보부터 환영","sub":"",
     "meta":"운영 박자영 · 회원 20명 · 2024년","date":"","photos":[]},
    {"community":"부동산 경매로 내집 마련하기","url":BASE+"/sbc/community-home.do?id=45644012",
     "title":"부동산 경매·전세사기 예방법을 함께 공부","sub":"",
     "meta":"운영 이창훈 · 회원 15명 · 2024년","date":"","photos":[]},
    {"community":"성북사랑 KCN 뉴스 시민기자단","url":BASE+"/sbc/community-home.do?id=44852593",
     "title":"성북의 소식을 널리 알리는 시민기자단 모임","sub":"",
     "meta":"운영 김영윤 · 회원 8명 · 2024년","date":"","photos":[]},
    {"community":"옳음환경교육","url":BASE+"/sbc/community-home.do?id=43274665",
     "title":"환경교육 프로그램·교구·교재를 개발하는 모임","sub":"",
     "meta":"운영 안정희 · 회원 10명 · 2022년","date":"","photos":[]},
    {"community":"시니어모델실전","url":BASE+"/sbc/community-home.do?id=42703055",
     "title":"시니어 모델로 사회에 진출할 역량을 갖추는 모임","sub":"",
     "meta":"운영 구본미 · 회원 8명 · 2024년","date":"","photos":[]},
    {"community":"시니어인지플러스","url":BASE+"/sbc/community-home.do?id=41901577",
     "title":"치매 예방·시니어 교육 강사 역량을 강화하는 커뮤니티","sub":"",
     "meta":"운영 김명순 · 회원 15명 · 2023년","date":"","photos":[]},
    {"community":"정통연극연구소","url":BASE+"/sbc/community-home.do?id=40460677",
     "title":"정기공연·사회공헌을 겸한 정통연극 소모임","sub":"",
     "meta":"운영 이종섭 · 회원 10명 · 2024년","date":"","photos":[]},
    {"community":"토탈공예커뮤니티","url":BASE+"/sbc/community-home.do?id=38061486",
     "title":"자율 운영으로 즐겁고 행복한 삶을 함께하는 공예 모임","sub":"",
     "meta":"운영 이수정 · 회원 6명 · 2024년","date":"","photos":[]},
    {"community":"중장년 연극단 오아시스","url":BASE+"/sbc/community-home.do?id=37349798",
     "title":"연극 기초를 토대로 연극단을 활성화하는 모임","sub":"",
     "meta":"운영 송경미 · 회원 11명 · 2023년","date":"","photos":[]},
    {"community":"빛그림 동인회 · 그림","url":BASE+"/sbc/community-home.do?id=37031382",
     "title":"다양한 재료로 도약하는 작품을 연구하는 그림 모임","sub":"",
     "meta":"운영 이석영 · 회원 10명 · 2023년","date":"","photos":[]},
    {"community":"두근두근뇌운동","url":BASE+"/sbc/community-home.do?id=47979341",
     "title":"인지자극 활동으로 신체 기능 유지·향상을 도모하는 모임","sub":"",
     "meta":"운영 김여정 · 회원 6명 · 2022년","date":"","photos":[]},
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
                          "date": "", "photos": []})
            continue
        cm, post, title = m.group(1), m.group(2), clean(m.group(3))
        d = RE_DATE.search(home)
        date = d.group(1) if d else ""
        post_url = f"{BASE}/sbc/community-member-post-view.do?CM_NO={cm}&POST_NO={post}"

        photos, author = [], ""
        try:
            detail = fetch(post_url); time.sleep(DELAY)
            ad = RE_AUTHORDATE.search(detail)
            if ad:
                author = clean(ad.group(1)); date = ad.group(2)
            # 본문 영역만: 작성자·날짜 이후 ~ 푸터 이전 (상단 헤더 로고 제외)
            start = ad.end() if ad else 0
            fend = re.search(r'패밀리사이트|Copyright|커뮤니티 가입', detail)
            body = detail[start: fend.start() if fend else len(detail)]
            for path in RE_IMG.findall(body):
                if any(bad in path for bad in IMG_EXCLUDE):
                    continue
                u = BASE + path
                if u not in photos:
                    photos.append(u)
                if len(photos) >= 5:      # 카드당 최대 5장까지 순환
                    break
        except (URLError, HTTPError) as e:
            print(f"[!] {name} 글 실패: {e}", file=sys.stderr)

        meta = (f"{author} · {date.replace('-', '.')}" if author and date
                else (date.replace('-', '.') if date else "최근 글"))
        cards.append({"community": name, "url": post_url, "title": title,
                      "sub": DESC.get(name, ""), "meta": meta, "date": date, "photos": photos})
    return cards


def gradient_for(name):
    """사진 없는 카드용: 이름 기반 결정적 그라데이션."""
    h = 0
    for ch in (name or ""):
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return f"linear-gradient(150deg,hsl({h % 360} 52% 30%),hsl({(h + 40) % 360} 58% 18%))"


def render(cards, generated):
    cards = sorted(cards, key=lambda c: c.get("date") or "", reverse=True)
    items = []
    for i, c in enumerate(cards):
        comm = html.escape(c["community"]); title = html.escape(c["title"])
        meta = html.escape(c.get("meta") or ""); url = html.escape(c["url"])
        photos = c.get("photos") or []; delay = f"{i * 0.06:.2f}s"
        if photos:
            layers = "".join(
                f'<div class="photo{" on" if k == 0 else ""}" '
                f'style="background-image:url(\'{html.escape(p)}\')"></div>'
                for k, p in enumerate(photos))
            stack = f'<div class="stack">{layers}</div>'
        else:
            stack = (f'<div class="stack"><div class="photo on noimg" '
                     f'style="background:{gradient_for(c["community"])}">'
                     f'<div class="glyph">{comm}</div></div></div>')
        items.append(f'''<a class="card" style="--i:{delay}" href="{url}" target="_blank" rel="noopener">
  {stack}
  <div class="scrim"></div>
  <span class="badge"><span class="dot"></span>{comm}</span>
  <div class="body"><div class="title">{title}</div><div class="meta">{meta}</div></div>
</a>''')
    grid = "\n".join(items)
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>성북50+ 커뮤니티 소식</title>
<style>
  :root{{--ink:#1d1d1f;--dim:#6e6e73;--glass:rgba(255,255,255,.16);--glass-brd:rgba(255,255,255,.32);
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Apple SD Gothic Neo","Pretendard","Malgun Gothic",system-ui,sans-serif;}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:transparent;color:var(--ink);-webkit-font-smoothing:antialiased;padding:8px}}
  header{{padding:4px 4px 2px}}
  h1{{font-size:clamp(20px,2.6vw,26px);font-weight:700;letter-spacing:-.03em}}
  .sub-h{{color:var(--dim);font-size:13.5px;margin-top:4px}}
  .grid{{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));padding:14px 4px}}
  .card{{position:relative;aspect-ratio:3/2;border-radius:18px;overflow:hidden;background:#111;
    text-decoration:none;color:#fff;display:block;box-shadow:0 8px 24px rgba(0,0,0,.12);
    opacity:0;transform:translateY(14px);animation:up .6s var(--i,0s) forwards cubic-bezier(.22,.61,.36,1)}}
  @keyframes up{{to{{opacity:1;transform:none}}}}
  .stack{{position:absolute;inset:0;transition:transform .8s cubic-bezier(.22,.61,.36,1)}}
  .card:hover .stack{{transform:scale(1.06)}}
  .photo{{position:absolute;inset:0;background-size:cover;background-position:center;
    opacity:0;transition:opacity .9s ease}}
  .photo.on{{opacity:1}}
  .noimg{{display:flex;align-items:center;justify-content:center}}
  .noimg .glyph{{font-size:clamp(30px,5vw,52px);font-weight:800;letter-spacing:-.04em;
    color:rgba(255,255,255,.12);text-align:center;line-height:.92;padding:0 10%}}
  .scrim{{position:absolute;inset:0;background:linear-gradient(180deg,
    rgba(0,0,0,.02) 0%,rgba(0,0,0,0) 28%,rgba(0,0,0,.34) 62%,rgba(0,0,0,.82) 100%)}}
  .badge{{position:absolute;top:13px;left:13px;font-size:12px;font-weight:600;
    padding:5px 10px;border-radius:999px;background:var(--glass);border:1px solid var(--glass-brd);
    backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);display:inline-flex;align-items:center;gap:6px}}
  .badge .dot{{width:6px;height:6px;border-radius:50%;background:#4ade80}}
  .body{{position:absolute;left:0;right:0;bottom:0;padding:16px}}
  .title{{font-size:16px;font-weight:700;line-height:1.28;letter-spacing:-.01em;
    text-shadow:0 2px 16px rgba(0,0,0,.5);
    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
  .meta{{margin-top:7px;font-size:12px;color:rgba(255,255,255,.78)}}
  .foot{{color:var(--dim);font-size:12px;text-align:center;padding:8px 0 14px}}
  @media (prefers-reduced-motion:reduce){{.card{{animation:none;opacity:1;transform:none}}
    .card:hover .stack{{transform:none}}}}
</style></head>
<body>
  <header><h1>성북50+ 커뮤니티 소식</h1>
  <div class="sub-h">최신 글을 올린 커뮤니티 순서로 보여드려요</div></header>
  <div class="grid">
{grid}
  </div>
  <div class="foot">자동 업데이트 · {generated}</div>
  <script>
    document.querySelectorAll('.stack').forEach(function(st, idx){{
      var ph = st.querySelectorAll('.photo');
      if (ph.length < 2) return;              // 사진 1장 이하면 순환 안 함
      var i = 0;
      setTimeout(function(){{
        setInterval(function(){{
          ph[i].classList.remove('on');
          i = (i + 1) % ph.length;
          ph[i].classList.add('on');
        }}, 3500);
      }}, idx * 400);                          // 카드마다 시작을 어긋나게
    }});
  </script>
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
