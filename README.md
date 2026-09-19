# CI/CD Hook Router

GitHub, Perforce, 다중 저장소 manifest에서 전달되는 hook을 저장소 도구에
종속되지 않는 공통 이벤트로 변환합니다. 변환된 이벤트가 YAML 정책에
부합하는지 판별하고, SQLite로 중복 실행을 방지한 다음 Jenkins 작업을
실행합니다.

## 빠른 시작

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp config/policies.example.yaml config/policies.yaml

export CICD_ROUTER_CONFIG=config/policies.yaml
export GITHUB_WEBHOOK_SECRET='a-long-random-value'
export GITHUB_TOKEN='github-token'
export JENKINS_USERNAME='ci-router'
export JENKINS_TOKEN='jenkins-api-token'

uvicorn cicd_router.main:app --reload
```

OpenAPI 문서는 `/docs`에서 확인할 수 있습니다.

## 환경변수

| 환경변수 | 필수 여부 | 설명 |
| --- | --- | --- |
| `CICD_ROUTER_CONFIG` | 선택 | 정책 YAML 파일 경로입니다. 기본값은 `config/policies.yaml`입니다. |
| `CICD_ROUTER_DB` | 선택 | 이벤트 처리 및 Jenkins 실행 요청을 기록할 SQLite 파일 경로입니다. 기본값은 `cicd-router.db`이며, 운영 환경에서는 영구 저장소에 배치해야 합니다. |
| `GITHUB_WEBHOOK_SECRET` | 운영 환경 필수 | GitHub Webhook 설정에 입력한 Secret입니다. `X-Hub-Signature-256` 서명 검증에 사용합니다. 설정하지 않으면 로컬 개발을 위해 검증을 생략합니다. |
| `GITHUB_TOKEN` | 비공개 저장소 필수 | GitHub Compare API 호출에 사용하는 Fine-grained PAT 또는 GitHub App Token입니다. 저장소의 `Contents: read` 권한이 필요합니다. 공개 저장소에서는 생략할 수 있지만 API 요청 제한이 더 낮습니다. |
| `GITHUB_API_URL` | GitHub Enterprise에서만 필요 | GitHub REST API 루트 주소입니다. 기본값은 `https://api.github.com`입니다. |
| `GITHUB_API_VERSION` | 선택 | 사용할 GitHub REST API 계약 버전입니다. 기본값은 `2026-03-10`입니다. |
| `JENKINS_USERNAME` | 필수 | HTTP Basic 인증에 사용할 Jenkins 서비스 계정 이름입니다. |
| `JENKINS_TOKEN` | 필수 | `JENKINS_USERNAME` 계정에서 발급한 Jenkins API Token입니다. 로그인 비밀번호가 아닙니다. |
| `HOOK_SECRET` | Perforce/manifest 운영 환경 필수 | `X-Hook-Signature`를 사용하는 비-GitHub adapter의 공통 HMAC-SHA256 Secret입니다. |

YAML의 `username_env`, `token_env`에는 인증 정보 자체가 아니라 인증 정보를
읽어 올 **환경변수 이름**을 입력합니다. 따라서 Secret을 저장소에 커밋하지
않으면서 정책마다 서로 다른 Jenkins 계정을 사용할 수 있습니다.

## GitHub 설정

저장소 또는 Organization Webhook을 다음과 같이 생성합니다.

- Payload URL: `https://router.example.com/v1/hooks/github`
- Content type: `application/json`
- Secret: `GITHUB_WEBHOOK_SECRET`과 동일한 값
- Events: `push`만 선택

GitHub adapter는 GitHub의 원본 push payload와 다음 헤더/API를 사용합니다.

- `X-GitHub-Delivery`: 재전송과 중복 실행을 방지하는 이벤트 고유 ID
- `X-GitHub-Event`: `push` 이벤트만 처리하고 `ping`과 관계없는 이벤트는 무시
- `X-Hub-Signature-256`: HMAC-SHA256 요청 서명 검증
- `GET /repos/{owner}/{repo}/compare/{before}...{after}`: 변경 파일 조회

GitHub Compare API는 변경 파일을 최대 300개까지 반환합니다. 이 한도에
도달하면 변경 경로 목록이 불완전한 것으로 처리합니다. 필요한 빌드를
누락하지 않도록 이 경우에는 경로 정책을 보수적으로 판단하여 Jenkins를
실행합니다.

새 브랜치는 이전 commit SHA가 모두 `0`이므로 Compare API를 사용할 수
없습니다. 이 경우에는 webhook payload의 commit 목록에서 변경 경로를
추출합니다.

참고 문서:

- [GitHub Webhook 헤더와 payload](https://docs.github.com/en/webhooks/webhook-events-and-payloads)
- [Webhook 서명 검증](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [Compare two commits API](https://docs.github.com/en/rest/commits/commits#compare-two-commits)

## 기타 Hook 엔드포인트

### Perforce

`POST /v1/hooks/perforce`

```json
{
  "changelist": 10425,
  "depot": "//Game/Main",
  "branch": "main",
  "changed_files": ["Source/Game.cpp", "Content/Hero.uasset"],
  "event_name": "submit",
  "actor": "build-user"
}
```

### Repo manifest

`POST /v1/hooks/repo-manifest`

```json
{
  "event_id": "manifest-run-891",
  "manifest": "default.xml",
  "branch": "main",
  "revision": "manifest-commit-sha",
  "projects": [
    {
      "name": "acme/backend",
      "revision": "project-commit-sha",
      "changed_files": ["src/app.py"]
    }
  ],
  "event_name": "sync"
}
```

`HOOK_SECRET`을 설정했다면 원본 요청 body로 계산한 서명을 다음 헤더로
전달해야 합니다.

```text
X-Hook-Signature: sha256=<원본-body의-HMAC>
```

## Jenkins 실행

조건에 부합하는 정책마다 다음 주소로 인증된 POST 요청을 전송합니다.

```text
JENKINS_URL/job/FOLDER/job/JOB/buildWithParameters
```

Jenkins 작업에는 전달받을 매개변수가 미리 선언되어 있어야 합니다. Router는
다음 값을 자동으로 전달합니다.

| Jenkins 매개변수 | 설명 |
| --- | --- |
| `HOOK_EVENT_ID` | 원본 hook의 고유 이벤트 ID |
| `HOOK_SOURCE` | `github`, `perforce`, `repo_manifest` 등의 이벤트 출처 |
| `HOOK_BRANCH` | 변경된 브랜치 |
| `HOOK_REVISION` | Git commit SHA, manifest revision 또는 Perforce changelist |
| `HOOK_REPOSITORIES` | 변경된 저장소 목록 |

YAML의 `parameters`에 정의한 고정 매개변수도 함께 전달합니다. Jenkins의
CSRF 보호와 안전하게 연동하려면 비밀번호 대신 API Token을 사용하는 것이
좋습니다. 자세한 내용은 [Jenkins Remote Access API](https://www.jenkins.io/doc/book/using/remote-access-api/)를
참고하세요.

## 정책 판정 방식

정책 예시는 [`config/policies.example.yaml`](config/policies.example.yaml)에서
확인할 수 있습니다.

- 서로 다른 조건 항목은 AND로 결합합니다.
- 같은 조건 안에 나열된 값은 OR로 결합합니다.
- 문자열 패턴은 shell-style glob을 사용합니다.
- 변경 경로는 `include_paths` 중 하나와 일치해야 합니다.
- `exclude_paths`와 일치하는 변경 경로는 제외합니다.

Jenkins를 호출하기 전에 `(source, event_id, policy_id)` 조합을 SQLite에
기록합니다. 동일한 hook이 다시 전달되면 Jenkins를 재실행하지 않고
`duplicate`를 반환합니다.

Jenkins 호출이 실패하거나 timeout으로 결과가 불확실하면 상태를 `failed`로
보존하며 자동으로 재시도하지 않습니다. timeout이 발생했더라도 Jenkins에는
이미 빌드가 등록되었을 수 있기 때문에 무조건 재시도하면 중복 빌드가 생길 수
있습니다.

## Bitbucket 또는 다른 저장소 도구 추가

저장소 연동은 code-level plugin 구조로 분리되어 있습니다.

1. `models.py`에 provider의 webhook payload 모델을 추가합니다.
2. `sources/` 아래에 `SourceAdapter.normalize()`를 구현한 provider 모듈을 추가합니다.
3. `main.py`의 `_build_runtime()`에 adapter를 등록합니다.
4. `Source` enum에 provider 값을 추가하고 YAML 정책에서 해당 값을 사용합니다.
5. 서명 검증, 원본 payload 정규화, 불완전한 변경 경로, 중복 delivery ID를 테스트합니다.

새로운 provider를 추가해도 정책 판정, trigger 이력 관리, Jenkins 연동 코드는
수정할 필요가 없습니다. 현재 등록된 adapter는 `GET /healthz` 응답의
`sources` 항목에서 확인할 수 있습니다.

## 운영 환경 참고사항

- HTTPS를 사용하고 사용하는 source에 맞는 webhook Secret을 설정하세요.
- `CICD_ROUTER_DB`를 영구 저장소에 배치하세요.
- 현재 SQLite 구성은 Router 인스턴스 하나를 전제로 합니다. 여러 인스턴스로
  확장하기 전에 PostgreSQL과 같은 공유 트랜잭션 저장소로 교체해야 합니다.
- GitHub는 webhook에 10초 이내 응답하는 것을 권장합니다. 대규모 운영에서는
  정규화된 이벤트를 durable queue에 저장하고 Jenkins를 비동기로 실행하세요.

## 검증

```bash
pytest
```
