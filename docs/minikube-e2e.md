# Minikube E2E 검증

이 문서는 GitHub push webhook부터 Jenkins 빌드까지의 로컬 검증 경로를
기록합니다.

```text
GitHub push
  -> POST /v1/hooks/github
  -> GitHub Compare API
  -> YAML 정책 판정
  -> SQLite 중복 실행 방지
  -> Jenkins buildWithParameters
```

Jenkins는 `deploy/minikube/jenkins.yaml`로 배포하고, Router는
`config/policies.minikube.yaml` 정책을 사용합니다. 실제 운영 환경에서는
`admin/admin`, CSRF 비활성화, 임시 HTTPS tunnel 설정을 사용하면 안 됩니다.

