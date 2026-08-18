# QA Job Board KR

국내·해외·리모트 **QA / SQA / 테스트 엔지니어** 오픈 포지션을 한곳에 모아 보여주는 잡보드입니다.

**사이트:** https://hbass88.github.io/qa-job-board-kr/

## 동작 방식

- `data/jobs.json` — 사이트가 읽는 최종 데이터 (자동 생성)
- `data/curated.json` — 자동 수집이 어려운 소스(LinkedIn, Blind Hire, 사람인, 기업 채용페이지 등)의 수동 검증 공고. 직접 편집해서 추가/삭제 가능
- `scripts/update_jobs.py` — Jumpit·Wanted·Remotive·WeWorkRemotely·Greenhouse·카카오 채용 API에서 QA 공고를 수집해 curated와 병합
- `.github/workflows/update-jobs.yml` — 매일 06:00 KST에 자동 실행 (Actions 탭에서 수동 실행도 가능)

## 공고 직접 추가하기

`data/curated.json`의 `jobs` 배열에 아래 형식으로 추가 후 커밋하면 다음 자동 업데이트 때 병합됩니다.

```json
{
  "company": "회사명",
  "title": "공고 제목",
  "experience": "경력 요건",
  "location": "근무지",
  "source": "출처",
  "url": "공고 URL",
  "deadline": "YYYY-MM-DD 또는 상시",
  "notes": "한 줄 메모",
  "work_type": "국내 | 해외 | 리모트",
  "verified": "확인 날짜"
}
```

마감일(`deadline`)이 지난 공고는 자동으로 제외됩니다.

## 데이터 출처

Jumpit, Wanted, Rallit, 사람인, 잡플래닛, 인크루트, 리멤버, LinkedIn, Blind Hire, Remotive, WeWorkRemotely, 카카오/토스/LINE/쿠팡/크래프톤/SK/넥슨 채용 페이지

> 일부 사이트(잡코리아, 캐치, 로켓펀치, GroupBy 등)는 봇 차단으로 자동 수집이 불가하여 수동 검증분으로만 반영됩니다. 지원 전 반드시 원문 공고에서 마감 여부를 확인하세요.
