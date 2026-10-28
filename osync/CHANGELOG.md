# 0.1.1

- Osync 이미지 참조를 `thomasjeong/osync:latest-baseline` 태그로 변경.
- 2026-10-28 확인 기준 이 태그는 0.1.0에서 고정했던 digest와 동일합니다. 이번 변경으로 CPU 요구사항이 낮아지는 것은 아닙니다.
- 태그의 향후 변경사항은 이미 실행 중인 App에 자동 적용되지 않습니다. 새 이미지를 가져와 다시 빌드해야 합니다.

# 0.1.0

- 최초 통합형 실험 버전: Osync + PostgreSQL 16 + 소스 빌드 MinIO.
- 최초 실행 시 내부 인증 키 생성 및 영구 저장.
- 관리자 계정 일회성 생성, 서비스 준비 상태 확인, 장애 감지 및 순차 종료.
- Home Assistant cold backup 설정.
- amd64 빌드·로그인·S3 저장·재시작·cold-copy 복원 테스트 통과.
- aarch64 빌드 대상 포함. aarch64 실행, 실제 HA OS 및 Obsidian 동기화 검증 대기.
