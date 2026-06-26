# middl.news (믿을 뉴스)

판단이 바뀔 조건까지 공개하는 1인 뉴스 실험. GitHub Pages + Jekyll(빌드 액션 불필요).

## 구조
```
_config.yml            사이트 설정
CNAME                  커스텀 도메인(middl.news)
index.html             홈(사안 목록)
_layouts/default.html  공통 레이아웃(헤더·푸터·구독 링크)
_layouts/post.html     글 레이아웃(반례 CTA 포함)
_posts/                글(Markdown). 파일명: YYYY-MM-DD-slug.md
assets/style.css       스타일(읽기 최적화, JS 없음)
```

## 새 글 쓰기
`_posts/`에 `YYYY-MM-DD-제목slug.md` 추가:
```markdown
---
layout: post
title: "제목"
date: 2026-06-27
series: "코어 이탈 · 5편 중 2편"   # 선택
description: "한 줄 요약"
---
본문(Markdown). 근거는 인라인 링크로: [리얼미터 6월 3주](https://...)
```
커밋 후 push → 자동 발행.

## 배포 현황
- repo: **geekslife/newsstand** (public), remote=origin(SSH), 브랜치 main ✅ push 완료
- GitHub Pages: ✅ 활성(main/root), 커스텀 도메인 = middl.news (CNAME)
- **남은 1단계 — DNS** (도메인 구입처):
  - apex `@`: A 레코드 → `185.199.108.153` / `.109.153` / `.110.153` / `.111.153`
  - (선택) `www`: CNAME → `geekslife.github.io`
  - DNS 전파 후 Settings → Pages → **Enforce HTTPS** 체크
- 이후 발행: `_posts/`에 Markdown 추가 → `git push` (origin=geekslife/newsstand)

## 로컬 미리보기(선택)
```
gem install bundler jekyll
jekyll serve   # http://localhost:4000
```

## 원칙(과설계 금지)
- **repo는 public**(무료 GitHub Pages 조건). 소스 공개는 투명성과도 맞음 — 단 비밀(키·이메일 리스트) 절대 커밋 금지.
- **초안 = Obsidian 볼트(비공개) / 발행 = 이 public repo.** 미발행 글은 repo에 올리지 않는다(public이라 미리 노출됨). 확정된 글만 `_posts/`에 push.
- 댓글 기능 없음 — 1차 반례 채널은 Threads/X 답글·DM.
- 이메일 수집 = Tally(https://tally.so/r/b5DqZe), 발송은 초기 수동(Gmail BCC)→나중 도구.
- 화자는 "하영"(person-first), 브랜드 간판은 middl.news.
- 운영·편집 규율: Obsidian 볼트 `1-Projects/믿을 뉴스/`(컨셉·사안·응대 규율·발행 카피).
