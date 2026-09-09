# sql2widget 운영 배포

로컬은 기존 `docker compose up --build`를 사용합니다.
운영은 `compose.production.yml`로 별도 구성합니다. DB/API는 외부 포트를 열지 않으며,
프런트만 `127.0.0.1:3003`에서 정적 화면과 `/api` 프록시를 제공합니다.

## GitHub Actions

`.github/workflows/deploy.yml`:
1. PR 및 main push: 프런트 빌드, DB를 포함한 백엔드 테스트, 로그인/채팅 smoke.
2. main push 또는 수동 실행: frontend/backend의 amd64 이미지를 GHCR에 커밋 SHA 태그로 게시.
3. production 환경의 VPS에 배포 파일 업로드, 이미지 pull, health 확인.
4. 배포 실패 시 직전 이미지로 복구. DB 마이그레이션은 자동 되돌리지 않습니다.

필요한 production 환경 변수: `VPS_HOST`, `VPS_PORT`, `VPS_USER`, `DEPLOY_PATH`.
필요한 비밀값: `VPS_SSH_PRIVATE_KEY`, `VPS_HOST_KEY`.
서버의 배포 경로는 배포 사용자가 쓸 수 있어야 합니다.

## 서버 초기 설정

배포 폴더의 `.env`에 아래 항목을 설정합니다. 파일 권한은 600으로 유지합니다.
비밀번호는 URL에 사용할 수 있는 긴 임의 문자열을 사용합니다.

```dotenv
POSTGRES_PASSWORD=<random-password>
APP_SECRET=<at-least-32-random-characters>
ADMIN_PASSWORD=<at-least-16-random-characters>
VIEWER_PASSWORD=<at-least-16-random-characters>
PUBLIC_ORIGIN=https://your-domain
APP_PORT=3003
```

운영 초기 계정의 이메일은 `admin@example.com`, `viewer@example.com`이며,
비밀번호는 위 환경 변수로만 초기화합니다. 기존 계정 비밀번호를 매번 덮어쓰지 않습니다.
로그인 후 Admin → AI 연결에 Gemini API 키를 입력합니다.
현재 API 키는 해당 브라우저 localStorage에 저장됩니다. 채팅 요청에만 전달되고,
제공자별 고정 API 주소로 호출합니다. 사용자는 Gemini 모델을 직접 지정할 수 있습니다.

외부 접근에는 DNS와 호스트 Nginx HTTPS reverse proxy가 추가로 필요합니다.
Nginx는 해당 도메인을 `http://127.0.0.1:3003`으로 전달하고 응답 제한 시간을 180초로 둡니다.
운영에 개발용 기본 비밀번호를 사용하지 마세요.

## 현재 검증 상태

로컬 Docker에서 기존 테스트 15개와 mock 로그인/채팅 smoke 4개를 통과했습니다.
실제 Gemini 호출은 유효한 사용자 키로 추가 확인해야 합니다.
GitHub Actions 첫 실행과 VPS 배포 결과는 완료 후 기록합니다.
