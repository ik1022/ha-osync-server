# Osync Home Assistant App

**0.1.1 실험 버전 — x86-64 Docker 검증 및 사용자 HA OS 기동 확인, ARM·기기 간 동기화 검증 대기.**

`osync/` 폴더는 Home Assistant App 빌드 컨텍스트입니다.
[Osync-p](https://github.com/KORThomasJeong/Osync-p)의 서버 배포 이미지를 사용합니다.

Home Assistant OS의 앱 스토어 → 저장소에 다음 주소를 추가하세요.

```text
https://github.com/ik1022/ha-osync-server
```

Osync All-in-One을 설치한 뒤 공개 API/S3 주소와 최초 관리자 계정을 설정합니다.
설치 시 장치에서 이미지를 빌드합니다. 사전 빌드 이미지는 아직 게시하지 않았습니다.

## 포함된 구성

- `thomasjeong/osync:latest-baseline` 이미지에서 서버와 웹 UI를 가져옵니다.
- PostgreSQL 16 공식 이미지 기반. DB는 컨테이너 내부 loopback에서만 수신.
- MinIO 공식 마지막 보안 릴리스 소스를 빌드해 포함. 소스 commit 고정.
- Python 표준 라이브러리 기반 시작/종료 및 상태 관리.
- 관리자 계정 일회성 설정, 자동 생성 내부 키 영구 보관.
- `/data`에 DB, S3 파일, 동기화 상태, 암호화 키를 함께 저장.
- `backup: cold`로 데이터 쓰기를 멈춘 상태에서 백업.
- 외부 API/S3 URL 지정. Ingress는 이번 버전에 포함되지 않음.

## 검증 상태

2026-10-28 (한국 시간), WSL Ubuntu의 Docker 29.1.3에서 다음을 확인했습니다.

- 설정·키 보존 단위 테스트 6개 통과 및 YAML 4개 구문 확인
- amd64 통합 이미지 빌드 성공
- 세 서비스 초기 기동, 관리자 로그인 및 관리자 세션 확인
- 서명된 S3 요청으로 파일 업로드/다운로드
- 정상 종료 후 재시작: 내부 키, 관리자 계정, 파일 보존
- 중지 상태의 데이터 볼륨을 새 볼륨으로 복사한 뒤 새 컨테이너에서 로그인·파일 읽기 성공

마지막 항목은 cold backup과 같은 저장 상태에서의 복원 테스트이며,
Home Assistant Supervisor 자체의 백업 기능 테스트는 아닙니다.
사용자 HA OS/Proxmox 환경에서는 CPU 유형을 `kvm64`에서 `host`로 바꾼 후 기동 성공을 확인했습니다.
실제 Obsidian 두 기기 간 동기화, HA OS 백업·복원, aarch64 실행 검증은 남아 있습니다.
아키텍처별 CI 결과는 저장소의 [Actions](https://github.com/ik1022/ha-osync-server/actions)에서 확인할 수 있습니다.

0.1.1의 `latest-baseline`은 2026-10-28 확인 시 0.1.0에서 사용한
`sha256:86f6bbf73350477a46b61a49bbfcca3a85dae23dfea079b370c7d321e3c76918`과 동일했습니다.
태그 전환만으로 `kvm64` 호환성이 개선되지는 않습니다. 향후 태그 변경을 반영하려면
새 이미지를 가져와 App을 다시 빌드해야 하며 실행 중인 App이 자동 교체되지는 않습니다.

```sh
python -m unittest discover -s tests -v
docker build --build-arg BUILD_ARCH=amd64 -t osync-ha:test osync
python tests/smoke.py osync-ha:test
```

CI는 두 아키텍처에서 빌드/스모크 테스트만 실행하며 이미지를 게시하지 않습니다.
MinIO 컴파일 때문에 장치 내 첫 빌드는 시간과 메모리를 많이 사용할 수 있습니다.
배포용으로는 CI에서 검증한 다중 아키텍처 이미지를 별도 게시하고 `image:`를 지정하는 단계가 권장됩니다.

자세한 사용자 설치 방법은 [osync/DOCS.md](osync/DOCS.md)를 확인하세요.
