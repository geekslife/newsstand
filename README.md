# middl.news (믿을 뉴스)

말보다 숫자, 주장보다 흐름 — 판세를 지켜보는 1인 뉴스 실험. GitHub Pages + Jekyll(빌드 액션 불필요).

## 구조
```
_config.yml            사이트 설정
CNAME                  커스텀 도메인(middl.news)
index.html             홈(사안 목록)
_layouts/default.html  공통 레이아웃(헤더·푸터·구독 링크)
_layouts/post.html     글 레이아웃(수치·자료 제보 CTA 포함)
_previews/             URL로만 접근하는 공개 미리보기(홈 목록·검색엔진 제외)
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

## 미리보기 배포
검토할 초안은 `_previews/slug.md`에 둔다. `_posts`와 달리 날짜를 파일명에 넣지 않아도 된다.

```markdown
---
layout: post
title: "제목"
date: 2026-08-17
description: "한 줄 요약"
unlisted: true
sitemap: false
robots: "noindex, nofollow, noarchive"
---
본문
```

push 후 `https://middl.news/preview/slug/`에서 확인한다. 미리보기 컬렉션은 `site.posts`에 포함되지 않아 홈 목록에는 나오지 않는다. `robots` 메타 태그로 검색엔진 색인도 막는다.

단, 저장소와 Pages가 모두 공개이므로 **비공개 기능은 아니다.** URL을 알거나 GitHub 저장소를 보는 사람은 읽을 수 있다. 외부에 공개되면 안 되는 원고는 Obsidian에만 보관한다. 검토가 끝나면 `_previews/slug.md`를 삭제하고 `_posts/YYYY-MM-DD-slug.md`로 옮겨 정식 발행한다.

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
- **비공개 초안 = Obsidian / URL 공유용 초안 = `_previews` / 정식 발행 = `_posts`.** `_previews`도 공개 저장소에 올라가므로 민감한 원고는 넣지 않는다.
- 댓글 기능 없음 — 수치 오류·자료 제보 채널은 X 답글·DM.
- 이메일 수집 = Tally(https://tally.so/r/b5DqZe), 발송은 초기 수동(Gmail BCC)→나중 도구.
- 화자는 실명 비노출 + 1인칭 개인 목소리(person-first), 브랜드 간판은 middl.news.
- 운영·편집 규율: Obsidian 볼트 `1-Projects/믿을 뉴스/`(컨셉·사안·응대 규율·발행 카피).
