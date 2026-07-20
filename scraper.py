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
MAX_CARDS = 16                    # 전체 최신글 중 보여줄 카드 수
KST = timezone(timedelta(hours=9))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

RE_COMMUNITY = re.compile(r'community-home\.do\?id=(\d+)"[^>]*>\s*([^<]+?)\s*<', re.I)
RE_POST = re.compile(
    r'community-member-post-view\.do\?CM_NO=(\d+)&(?:amp;)?POST_NO=(\d+)"[^>]*>\s*([^<]+?)\s*<', re.I)
# 게시판 한 줄: 글 링크(제목) + 뒤따르는 작성일
RE_ROW = re.compile(
    r'community-member-post-view\.do\?CM_NO=(\d+)&(?:amp;)?POST_NO=(\d+)"[^>]*>\s*([^<]+?)\s*<'
    r'.*?(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}', re.I | re.S)
RE_DATE = re.compile(r'(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}')
RE_IMG = re.compile(r'(/upload/im/[^"\'\)\s]+?\.(?:jpg|jpeg|png|gif))', re.I)
RE_AUTHORDATE = re.compile(
    r'([가-힣A-Za-z]{2,12})\s*\(\s*(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}\s*\)')

# 콘텐츠가 아닌 이미지(센터 로고 등)는 배경으로 쓰지 않음
IMG_EXCLUDE = (
    "36dd6ba3-8569-4d3c-9d75-2dddec9537a1",  # 성북50+ 센터 로고
)

# 커뮤니티 번호(CM_NO) ↔ 이름 대조표 (성북센터 전체 30개)
NAME_BY_ID = {
    "73531462": "브레인핏 실버인지",
    "70910302": "서울 브레인댄스 연구소",
    "68301489": "FunFun한 긍정사주",
    "47979341": "두근두근뇌운동",
    "45991081": "보문 하모니카 커뮤니티",
    "45968416": "오이시이 니홍고",
    "45901904": "순수사진예술",
    "45896744": "향기는 바람을 타고 제품 팩토리",
    "45878503": "SB하모니카",
    "45878281": "타로톡방",
    "45644012": "부동산 경매로 내집 마련하기",
    "44852593": "성북사랑 KCN 뉴스 시민기자단",
    "43274665": "옳음환경교육",
    "42703055": "시니어모델실전",
    "42435654": "서투른 솜씨자랑",
    "41901577": "시니어인지플러스",
    "40460677": "정통연극연구소",
    "38061486": "토탈공예커뮤니티",
    "37349798": "중장년 연극단 오아시스",
    "37031382": "빛그림 동인회",
    "37030258": "유튜브랑",
    "35004420": "성북 연필 드로잉반",
    "27597810": "디지털 세상",
    "20342101": "맑은누리오카리나",
    "20211556": "떡사모",
    "19430676": "하늘바람 오카리나",
    "10979681": "소통하는 미디어 라이브",
    "7301517": "디지털 노마드",
    "7059667": "그린커피",
    "4347664": "우플",
}
RE_CID = re.compile(r'community-home\.do\?id=(\d+)')


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
    # 방문할 커뮤니티 번호 수집 (목록 페이지 + 대조표 합집합)
    ids, seen = [], set()
    for p in range(1, LIST_PAGES + 1):
        url = LIST_URL if p == 1 else f"{LIST_URL}?pageIndex={p}&"
        try:
            page = fetch(url); time.sleep(DELAY)
        except (URLError, HTTPError) as e:
            print(f"[!] 목록 {p} 실패: {e}", file=sys.stderr); continue
        for cid in RE_CID.findall(page):
            if cid not in seen:
                seen.add(cid); ids.append(cid)
    for cid in NAME_BY_ID:                 # 목록 파싱이 비어도 대조표 커뮤니티는 방문
        if cid not in seen:
            seen.add(cid); ids.append(cid)

    cards = []
    # 1단계: 각 커뮤니티 게시판에서 최근 글들의 (제목·날짜·링크)만 수집
    posts = []
    for cid in ids:
        try:
            home = fetch(f"{BASE}/sbc/community-home.do?id={cid}"); time.sleep(DELAY)
        except (URLError, HTTPError) as e:
            print(f"[!] {cid} 홈 실패: {e}", file=sys.stderr); continue
        seg = home.split("커뮤니티 게시판")[-1]        # 게시판 영역만
        for cm, post, title, date in RE_ROW.findall(seg):
            posts.append({"community": NAME_BY_ID.get(cm, "성북50+ 커뮤니티"),
                          "title": clean(title), "date": date,
                          "url": f"{BASE}/sbc/community-member-post-view.do?CM_NO={cm}&POST_NO={post}"})

    # 2단계: 전체를 날짜순으로 정렬 → 상위 MAX_CARDS개만
    posts.sort(key=lambda x: x["date"], reverse=True)
    posts = posts[:MAX_CARDS]

    # 3단계: 상위 글만 본문 방문 → 사진·작성자·온전한 제목 수집
    for pd in posts:
        photos, author, title_full = [], "", ""
        try:
            detail = fetch(pd["url"]); time.sleep(DELAY)
            ad = RE_AUTHORDATE.search(detail)
            if ad:
                author = clean(ad.group(1))
            # 온전한 제목: 빵부스러기('커뮤니티 게시판') 이후 ~ 작성자·날짜 이전의 제목 heading
            region = detail.split("커뮤니티 게시판")[-1]
            if ad and ad.group(0) in region:
                region = region.split(ad.group(0))[0]
            mt = re.search(r'<h[1-4][^>]*>(.*?)</h[1-4]>', region, re.S)
            if mt:
                cand = clean(mt.group(1)).replace("목록으로", "").strip()
                if len(cand) >= 2:
                    title_full = cand
            if not title_full:                      # 보조: 영역 텍스트에서 제목 추출
                cand = clean(region).replace("목록으로", "").strip()
                if 2 <= len(cand) <= 120:
                    title_full = cand
            start = ad.end() if ad else 0
            fend = re.search(r'패밀리사이트|Copyright|커뮤니티 가입', detail)
            body = detail[start: fend.start() if fend else len(detail)]
            for path in RE_IMG.findall(body):
                if any(bad in path for bad in IMG_EXCLUDE):
                    continue
                u = BASE + path
                if u not in photos:
                    photos.append(u)
                if len(photos) >= 5:
                    break
        except (URLError, HTTPError) as e:
            print(f"[!] 글 방문 실패: {e}", file=sys.stderr)

        d = pd["date"]
        meta = (f"{author} · {d.replace('-', '.')}" if author and d
                else (d.replace('-', '.') if d else "최근 글"))
        # 목록 제목이 잘렸거나(…) 비었으면 상세 페이지 제목으로 대체
        list_title = (pd["title"] or "").rstrip("… .")
        title = title_full or list_title or "(제목 없음)"
        cards.append({"community": pd["community"], "url": pd["url"], "title": title,
                      "meta": meta, "date": d, "photos": photos})
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
        photos = c.get("photos") or []; delay = f"{i * 0.05:.2f}s"
        if photos:
            layers = "".join(
                f'<div class="photo{" on" if k == 0 else ""}" '
                f'style="background-image:url(\'{html.escape(p)}\')"></div>'
                for k, p in enumerate(photos))
            thumb = f'<div class="thumb"><div class="stack">{layers}</div></div>'
        else:
            thumb = (f'<div class="thumb noimg"><div class="glyph">{comm}</div></div>')
        items.append(f'''<a class="card" style="--i:{delay}" href="{url}" target="_blank" rel="noopener">
  {thumb}
  <div class="body">
    <div class="eyebrow"><span class="dot"></span>{comm}</div>
    <div class="title">{title}</div>
    <div class="date">{meta}</div>
  </div>
</a>''')
    grid = "\n".join(items)
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>커뮤니티 소식</title>
<style>
  :root{{--ink:#1d1d1f;--dim:#8e8e93;--line:#ececf0;--accent:#0071e3;
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Apple SD Gothic Neo","Pretendard","Malgun Gothic",system-ui,sans-serif;}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  html,body{{max-width:100%;overflow-x:hidden}}
  body{{background:transparent;color:var(--ink);-webkit-font-smoothing:antialiased;padding:8px}}
  header{{padding:6px 8px 16px;margin:0 4px 4px}}
  h1{{font-size:clamp(22px,2.8vw,30px);font-weight:700;letter-spacing:-.03em}}
  .sub-h{{color:var(--dim);font-size:14px;margin-top:6px}}
  .grid{{display:grid;gap:22px;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));
    padding:20px 6px;align-items:start}}
  /* 폰: 2열 고정 + 잘림 방지 */
  @media (max-width:640px){{
    .grid{{grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;padding:16px 4px}}
    .body{{padding:14px 14px 16px}}
    .title{{font-size:14px}}
    .card{{border-radius:24px}}
  }}
  .card{{position:relative;display:flex;flex-direction:column;background:#fff;
    border-radius:28px;overflow:hidden;text-decoration:none;color:inherit;
    box-shadow:0 6px 20px rgba(0,0,0,.08),0 2px 6px rgba(0,0,0,.04);
    transition:transform .3s cubic-bezier(.22,.61,.36,1),box-shadow .3s ease;
    opacity:0;transform:translateY(16px);animation:up .55s var(--i,0s) forwards cubic-bezier(.22,.61,.36,1)}}
  .card:hover{{transform:translateY(-6px);box-shadow:0 22px 48px rgba(0,0,0,.16),0 4px 12px rgba(0,0,0,.06)}}
  @keyframes up{{to{{opacity:1;transform:none}}}}
  .thumb{{position:relative;width:100%;aspect-ratio:16/10;overflow:hidden;
    margin:10px 10px 0;width:calc(100% - 20px);border-radius:20px;background:#f2f2f7}}
  .stack{{position:absolute;inset:0}}
  .photo{{position:absolute;inset:0;background-size:cover;background-position:center;
    opacity:0;transition:opacity .9s ease,transform .8s ease}}
  .photo.on{{opacity:1}}
  .card:hover .photo.on{{transform:scale(1.06)}}
  /* 사진 없는 카드: 차분한 회색 톤 + 커뮤니티 이름 크게 */
  .thumb.noimg{{display:flex;align-items:center;justify-content:center;
    background:linear-gradient(150deg,#eef0f3,#dfe3e8)}}
  .thumb.noimg .glyph{{font-size:clamp(20px,3vw,30px);font-weight:800;letter-spacing:-.03em;
    color:#b7bcc4;text-align:center;line-height:1.15;padding:0 14%}}
  .body{{position:relative;padding:16px 18px 20px;
    background:rgba(255,255,255,.72);backdrop-filter:blur(20px) saturate(1.4);
    -webkit-backdrop-filter:blur(20px) saturate(1.4)}}
  .eyebrow{{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;
    color:var(--accent);letter-spacing:.01em}}
  .eyebrow .dot{{width:6px;height:6px;border-radius:50%;background:var(--accent)}}
  .title{{font-size:15.5px;font-weight:700;color:var(--ink);line-height:1.38;margin-top:9px;
    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
  .date{{font-size:12.5px;color:var(--dim);margin-top:12px}}
  .foot{{color:var(--dim);font-size:12px;text-align:center;padding:8px 0 14px}}
  @media (prefers-reduced-motion:reduce){{.card{{animation:none;opacity:1;transform:none}}
    .card:hover .photo.on{{transform:none}}}}
</style></head>
<body>
  <header><h1>커뮤니티 소식</h1>
  <div class="sub-h">우리가 함께한 활동을 기록하고, 모두에게 공유해요</div></header>
  <div class="grid">
{grid}
  </div>
  <div class="foot">마지막 확인 · {generated} (KST)</div>
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
    // 자기 높이를 홈페이지(부모 창)에 알려서 iframe이 자동으로 맞추게 함
    function postHeight(){{
      var h = document.body.scrollHeight;
      if (window.parent) window.parent.postMessage({{sb50height: h}}, "*");
    }}
    window.addEventListener('load', postHeight);
    window.addEventListener('resize', postHeight);
    setInterval(postHeight, 1500);            // 사진 로딩·슬라이드 후에도 맞춤
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
