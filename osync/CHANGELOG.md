# 0.1.0

- 최초 통합형 실험 버전: Osync + PostgreSQL 16 + 소스 빌드 MinIO.
- 최초 실행 시 내부 인증 키 생성 및 영구 저장.
- 관리자 계정 일회성 생성, 서비스 준비 상태 확인, 장애 감지 및 순차 종료.
- Home Assistant cold backup 설정.
- amd64 빌드·로그인·S3 저장·재시작·cold-copy 복원 테스트 통과.
- aarch64 빌드 대상 포함. aarch64 실행, 실제 HA OS 및 Obsidian 동기화 검증 대기.
