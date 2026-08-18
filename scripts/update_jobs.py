#!/usr/bin/env python3
"""QA 잡보드 자동 업데이트 스크립트.

GitHub Actions에서 매일 실행됩니다.
API 접근이 가능한 소스(Jumpit, Remotive, WeWorkRemotely RSS, Greenhouse 보드,
카카오/원티드 공개 API)에서 QA 공고를 수집해 data/curated.json(수동 검증분)과
병합한 뒤 data/jobs.json 을 갱신합니다.
"""
import json
import re
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KST = timezone(timedelta(hours=9))

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "application/json, text/html, application/xml;q=0.9, */*;q=0.8",
      "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"}

QA_TITLE_RE = re.compile(r"\bQA\b|quality\s*assurance|\bSQA\b|test\s*engineer|테스트\s*엔지니어|품질\s*보증|품질보증", re.IGNORECASE)
QA_EXCLUDE_RE = re.compile(r"제약|의약|화장품|식품|건설|용접|도금|사출|반도체\s*공정|품질관리\s*\(QC\)|\bQC\b", re.IGNORECASE)

KEYWORDS = ["QA 엔지니어", "QA Engineer", "Software QA", "QA Manager", "SQA", "테스트 엔지니어"]


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_json(url, timeout=20):
    return json.loads(fetch(url, timeout).decode("utf-8", errors="replace"))


def is_qa(title):
    return bool(QA_TITLE_RE.search(title)) and not QA_EXCLUDE_RE.search(title)


def collect_jumpit():
    jobs = []
    seen = set()
    for kw in KEYWORDS:
        try:
            q = urllib.parse.quote(kw)
            d = fetch_json(f"https://jumpit-api.saramin.co.kr/api/positions?keyword={q}&sort=rsp_rate&page=1&pageSize=50")
            positions = d.get("result", {}).get("positions", []) or d.get("positions", [])
            for p in positions:
                pid = p.get("id")
                title = p.get("title", "")
                if not pid or pid in seen or not is_qa(title):
                    continue
                seen.add(pid)
                jobs.append({
                    "company": p.get("companyName", ""),
                    "title": title,
                    "experience": f"{p.get('minCareer', '?')}~{p.get('maxCareer', '?')}년" if p.get("minCareer") is not None else "공고 참조",
                    "location": ", ".join(p.get("locations", [])) if isinstance(p.get("locations"), list) else str(p.get("locations", "")),
                    "source": "Jumpit",
                    "url": f"https://jumpit.saramin.co.kr/position/{pid}",
                    "deadline": p.get("closedAt", "상시")[:10] if p.get("closedAt") else "상시",
                    "notes": ", ".join(p.get("techStacks", [])[:5]) if p.get("techStacks") else "",
                    "work_type": "국내",
                })
        except Exception as e:
            print(f"[jumpit:{kw}] {e}", file=sys.stderr)
    return jobs


def collect_wanted():
    jobs = []
    seen = set()
    for kw in ["QA", "QA Engineer", "SQA"]:
        try:
            q = urllib.parse.quote(kw)
            d = fetch_json(f"https://www.wanted.co.kr/api/v4/jobs?country=kr&job_sort=job.latest_order&locations=all&years=-1&query={q}&limit=50")
            for p in d.get("data", []):
                pid = p.get("id")
                title = p.get("position", "")
                if not pid or pid in seen or not is_qa(title):
                    continue
                seen.add(pid)
                comp = (p.get("company") or {}).get("name", "")
                addr = (p.get("address") or {}).get("location", "")
                jobs.append({
                    "company": comp, "title": title,
                    "experience": "공고 참조", "location": addr or "공고 참조",
                    "source": "Wanted",
                    "url": f"https://www.wanted.co.kr/wd/{pid}",
                    "deadline": p.get("due_time") or "상시",
                    "notes": "", "work_type": "국내",
                })
        except Exception as e:
            print(f"[wanted:{kw}] {e}", file=sys.stderr)
    return jobs


def collect_remotive():
    jobs = []
    try:
        d = fetch_json("https://remotive.com/api/remote-jobs?category=qa&limit=50")
        for p in d.get("jobs", []):
            title = p.get("title", "")
            if not is_qa(title):
                continue
            jobs.append({
                "company": p.get("company_name", ""), "title": title,
                "experience": "공고 참조",
                "location": p.get("candidate_required_location", "Remote"),
                "source": "Remotive", "url": p.get("url", ""),
                "deadline": "미표기",
                "notes": (p.get("publication_date") or "")[:10] + " 게재",
                "work_type": "리모트",
            })
    except Exception as e:
        print(f"[remotive] {e}", file=sys.stderr)
    return jobs


def collect_wwr():
    jobs = []
    try:
        raw = fetch("https://weworkremotely.com/remote-jobs.rss")
        root = ET.fromstring(raw)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            if not is_qa(title):
                continue
            link = (item.findtext("link") or "").strip()
            region = (item.findtext("region") or "Remote").strip() if item.find("region") is not None else "Remote"
            jobs.append({
                "company": title.split(":")[0].strip() if ":" in title else "",
                "title": title.split(":", 1)[1].strip() if ":" in title else title,
                "experience": "공고 참조", "location": f"풀리모트 ({region})",
                "source": "WeWorkRemotely", "url": link,
                "deadline": "미표기", "notes": "", "work_type": "리모트",
            })
    except Exception as e:
        print(f"[wwr] {e}", file=sys.stderr)
    return jobs


GREENHOUSE_BOARDS = ["coupang", "kraftonindia", "sendbird", "moloco", "dunamu", "toss", "tosspayments", "tossbank", "tosssecurities"]


def collect_greenhouse():
    jobs = []
    for board in GREENHOUSE_BOARDS:
        try:
            d = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs")
            for p in d.get("jobs", []):
                title = p.get("title", "")
                if not is_qa(title):
                    continue
                jobs.append({
                    "company": board.capitalize(), "title": title,
                    "experience": "공고 참조",
                    "location": (p.get("location") or {}).get("name", ""),
                    "source": "기업 채용페이지 (Greenhouse)",
                    "url": p.get("absolute_url", ""),
                    "deadline": "상시",
                    "notes": (p.get("updated_at") or "")[:10] + " 업데이트",
                    "work_type": "국내" if "Seoul" in str(p.get("location")) or "Korea" in str(p.get("location")) else "해외",
                })
        except Exception as e:
            print(f"[greenhouse:{board}] {e}", file=sys.stderr)
    return jobs


def collect_kakao():
    jobs = []
    try:
        d = fetch_json("https://careers.kakao.com/public/api/job-list?skillSet=&part=TECHNOLOGY&company=ALL&keyword=QA&employeeType=&page=1")
        for p in d.get("jobList", []):
            title = p.get("jobOfferTitle", "")
            if not is_qa(title):
                continue
            jobs.append({
                "company": p.get("companyNameEn", "카카오") or "카카오", "title": title,
                "experience": p.get("qualification", "공고 참조")[:40] if p.get("qualification") else "공고 참조",
                "location": p.get("workingPlace", "판교") or "판교",
                "source": "기업 채용페이지",
                "url": f"https://careers.kakao.com/jobs/{p.get('realId', p.get('jobOfferId', ''))}",
                "deadline": (p.get("endDate") or "상시")[:10],
                "notes": "카카오 공식 채용 API 수집", "work_type": "국내",
            })
    except Exception as e:
        print(f"[kakao] {e}", file=sys.stderr)
    return jobs


def not_expired(job, today):
    dl = job.get("deadline", "")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", dl or "")
    if not m:
        return True
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) >= today
    except ValueError:
        return True


def norm_url(u):
    return (u or "").rstrip("/").split("?utm")[0].lower()


def main():
    today = datetime.now(KST).date()
    curated = json.loads((DATA / "curated.json").read_text(encoding="utf-8"))["jobs"]

    auto = []
    auto += collect_jumpit()
    auto += collect_wanted()
    auto += collect_kakao()
    auto += collect_greenhouse()
    auto += collect_remotive()
    auto += collect_wwr()
    print(f"auto collected: {len(auto)}")

    # 기존 jobs.json의 자동 수집분도 참고해 급격한 감소(수집 실패) 시 보존
    prev = []
    jobs_path = DATA / "jobs.json"
    if jobs_path.exists():
        try:
            prev = json.loads(jobs_path.read_text(encoding="utf-8")).get("jobs", [])
        except Exception:
            pass

    merged, seen = [], set()
    for job in curated + auto + prev:
        key = norm_url(job.get("url"))
        key2 = (job.get("company", "").strip().lower(), job.get("title", "").strip().lower())
        if not key or key in seen or key2 in seen:
            continue
        if not not_expired(job, today):
            continue
        seen.add(key)
        seen.add(key2)
        merged.append(job)

    out = {
        "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "total": len(merged),
        "jobs": merged,
    }
    jobs_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(merged)} jobs -> {jobs_path}")


if __name__ == "__main__":
    main()
