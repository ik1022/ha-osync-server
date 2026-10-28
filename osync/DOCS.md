# 설치 및 운영

이 버전은 새 설치용 실험 패키지입니다. 기존 운영 데이터를 바로 옮기지 말고
빈 테스트 볼트에서 검증한 뒤 사용하세요. 기존 Compose 볼륨 자동 이관은 제공하지 않습니다.

## Home Assistant에 등록

1. Home Assistant OS의 설정 → Apps → 앱 스토어 → 저장소를 엽니다.
2. `https://github.com/ik1022/ha-osync-server`를 추가합니다.
3. Osync All-in-One을 설치합니다. 로컬 빌드 방식이라 MinIO 컴파일 시간이 필요합니다.
4. 아래 설정을 입력한 다음 시작합니다.

로컬 App 개발 환경에서는 `osync/` 폴더를 로컬 Apps 디렉터리에 넣고 스토어를 새로고침할 수도 있습니다.
설치/시작 메뉴 표기는 Home Assistant 버전에 따라 달라질 수 있습니다.

## 설정

```yaml
public_url: https://osync.example.com
s3_public_endpoint: https://osync-s3.example.com
language: ko
admin_email: admin@example.com
admin_password: "최초-설정용-긴-비밀번호"
```

| 설정 | 의미 |
|---|---|
| public_url | 브라우저와 Obsidian이 사용하는 API 원점 주소. 경로 없이 지정 |
| s3_public_endpoint | Obsidian이 직접 접근하는 MinIO 주소. 경로 없이 지정 |
| language | `ko` 또는 `en` |
| admin_email | 최초 관리자 계정 이메일 |
| admin_password | 최초 관리자 비밀번호, 12자 이상. 생성 성공 후 빈 문자열로 변경 가능 |

기본 포트는 API `3000`, S3 `9000`입니다. App 네트워크 설정에서 호스트 포트를 바꿀 수 있습니다.
설정한 URL도 실제 연결 방식에 맞춰 변경해야 합니다. `localhost`나 컨테이너 내부 이름을
클라이언트용 주소로 지정하면 다른 기기에서 연결할 수 없습니다.

내부망 테스트에는 `http://HA의-IP:3000`, `http://HA의-IP:9000`을 사용할 수 있습니다.
다만 암호화 관련 브라우저 기능은 HTTPS 보안 컨텍스트가 필요할 수 있으므로 실제 사용은 HTTPS로 검증하세요.

## HTTPS와 동기화

리버스 프록시에 두 호스트를 설정합니다.

- `osync.example.com` → Home Assistant 장치의 API 매핑 포트 (기본 3000)
- `osync-s3.example.com` → Home Assistant 장치의 S3 매핑 포트 (기본 9000)

API는 WebSocket을 허용해야 하고, S3 프록시는 원래 Host 및 쿼리 문자열을 보존해야 합니다.
큰 파일 전송 시 요청/응답 버퍼링과 업로드 크기 제한을 확인하세요.
외부에는 HTTPS 프록시를 통해 접속하고 DB/MinIO 콘솔은 공개하지 않습니다.
MinIO는 내부 `127.0.0.1:9000` 주소와 클라이언트용 주소를 구분해서 사용합니다.

Home Assistant 원격 접속 주소가 있다고 해서 Osync API/S3까지 자동 공개되지는 않습니다.
VPN 사용 시에도 두 주소가 모든 동기화 기기에서 접근 가능해야 합니다.

웹 관리 화면은 `public_url` 뒤에 `/admin/`을 붙여 접속합니다.
App의 “웹 UI 열기” 버튼은 HA 호스트의 HTTP 매핑 포트를 열므로 HTTPS 배포에서는
설정한 공개 URL을 브라우저에서 직접 여세요. Osync 자체 로그인은 유지합니다.
Ingress는 아직 없으며 HA 로그인으로 Osync 관리자 인증을 우회하지 않습니다.

로그에 `All services ready`가 나타나면 관리자 로그인 → 초대 코드 생성 → 사용자 가입 →
Obsidian 플러그인에 `public_url` 설정 → 로그인 → 테스트 볼트 연결 순서로 확인합니다.

## 저장 및 백업

| 경로 | 내용 |
|---|---|
| /data/postgres | 계정·메타데이터 |
| /data/minio | 암호화된 파일 |
| /data/coordinators | 동기화 상태 |
| /data/secrets.json | 내부 DB/S3 인증 정보, 인증 서명 키, MinIO 저장 암호화 키 |
| /data/admin-initialized | 최초 관리자 생성 완료 표시 |

Home Assistant 백업에 이 App을 포함하세요. `cold` 백업 동안 App과 동기화가 잠시 중지됩니다.
DB·파일·키는 반드시 함께 복원해야 합니다. `secrets.json`이 사라지면 기존 데이터를
새 키로 열 수 없으므로 App은 자동 키 재생성 대신 시작을 거부합니다.
Osync 볼트 비밀번호는 별도로 보관해야 하며 App 백업으로 복구할 수 없습니다.

관리자 생성 완료 후 옵션의 `admin_password`를 비워 저장합니다. 이후 재시작은
관리자 비밀번호를 초기화하지 않습니다. 비밀번호 변경은 Osync 관리 UI에서 하세요.

PostgreSQL 주 버전은 16으로 유지합니다. 향후 주 버전 변경에는 별도 DB 이관이 필요합니다.
업데이트 전 전체 App 백업을 만들고, 스키마 변경 후 이전 이미지로만 되돌리지 마세요.

## 검증 상태 및 출시 전 남은 확인

amd64 Docker에서 초기 기동, 관리자 로그인, S3 파일 쓰기/읽기,
재시작 후 키·계정·파일 보존, 중지된 볼륨 복사 후 새 컨테이너 복원을 확인했습니다.
설정 및 키 보존 단위 테스트 6개도 통과했습니다.
아래는 실제 장치에서 추가로 확인해야 할 항목입니다.

- aarch64에서 이미지 빌드와 초기 기동
- Home Assistant OS App 설치 및 시작/중지/업데이트
- 초대 가입, Obsidian 장치 인증
- 두 클라이언트 간 업로드/다운로드, 삭제/복원, WebSocket 재연결
- 실제 Obsidian 볼트의 재시작 후 동기화
- App cold backup을 새 인스턴스에 복원 후 동기화
- 큰 첨부파일과 장시간 운영 시 RAM/디스크 사용량

MinIO 커뮤니티 저장소는 보관 상태이므로 장기 운영을 위한 유지보수/대체 S3 검토가 필요합니다.
참조: https://github.com/minio/minio
