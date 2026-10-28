"""Supervise the three services; persistent state lives only under /data."""
import base64
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit

SECRET_KEYS = ("postgres_password", "s3_access_key", "s3_secret_key",
               "auth_secret", "sync_secret", "minio_kms_key")


def origin(value, name):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError(f"{name}: enter an http(s) origin without whitespace")
    u = urlsplit(value)
    if (u.scheme not in ("http", "https") or not u.hostname or u.username
            or u.password or u.path not in ("", "/") or u.query or u.fragment):
        raise ValueError(f"{name}: use http(s)://hostname[:port], without a path")
    _ = u.port  # Reject malformed ports.
    return value.rstrip("/")


def validate_options(options, needs_admin):
    result = dict(options)
    for name in ("public_url", "s3_public_endpoint"):
        result[name] = origin(options.get(name, ""), name)
    if options.get("language", "ko") not in ("ko", "en"):
        raise ValueError("language must be ko or en")
    result["language"] = options.get("language", "ko")
    if needs_admin:
        email = options.get("admin_email", "")
        password = options.get("admin_password", "")
        if not isinstance(email, str) or "@" not in email or any(c.isspace() for c in email):
            raise ValueError("admin_email is required on first start")
        if not isinstance(password, str) or len(password) < 12 or "\x00" in password:
            raise ValueError("admin_password must have at least 12 characters")
    return result


def load_secrets(data):
    path = data / "secrets.json"
    if path.exists():
        values = json.loads(path.read_text())
        if any(not isinstance(values.get(k), str) or not values[k] for k in SECRET_KEYS):
            raise ValueError("secrets.json is incomplete; restore the complete App backup")
        return values
    if any((data / d).exists() and any((data / d).iterdir())
           for d in ("postgres", "minio", "coordinators")):
        raise ValueError("Existing data has no secrets.json; restore it, do not generate new keys")
    values = {k: secrets.token_hex(32) for k in SECRET_KEYS}
    values["s3_access_key"] = secrets.token_hex(10)
    values["minio_kms_key"] = "osync-key:" + base64.b64encode(secrets.token_bytes(32)).decode()
    temporary = data / ".secrets.tmp"
    with temporary.open("w", encoding="utf-8") as f:
        os.chmod(temporary, 0o600)
        json.dump(values, f)
        f.flush()
        os.fsync(f.fileno())
    temporary.replace(path)
    return values


def environments(options, keys):
    # Do not pass Supervisor tokens or unrelated environment variables to children.
    common = {k: os.environ[k] for k in ("PATH", "TZ", "LANG") if k in os.environ}
    common["HOME"] = "/tmp"
    pg = dict(common, PGDATA="/data/postgres", POSTGRES_USER="osync",
              POSTGRES_DB="osync", POSTGRES_PASSWORD=keys["postgres_password"],
              POSTGRES_INITDB_ARGS="--auth-host=scram-sha-256")
    for name in ("PG_MAJOR", "PG_VERSION"):
        if name in os.environ:
            pg[name] = os.environ[name]
    s3 = dict(common, MINIO_ROOT_USER=keys["s3_access_key"],
              MINIO_ROOT_PASSWORD=keys["s3_secret_key"],
              MINIO_KMS_SECRET_KEY=keys["minio_kms_key"], MINIO_KMS_AUTO_ENCRYPTION="on",
              MINIO_SERVER_URL=options["s3_public_endpoint"], MINIO_BROWSER="off")
    api = dict(common, NODE_ENV="production", PORT="3000", SELF_HOSTED="true",
               PUBLIC_URL=options["public_url"], CORS_ORIGIN=options["public_url"],
               LANGUAGE=options["language"], COORDINATOR_DATA_DIR="/data/coordinators",
               DATABASE_URL=f"postgresql://osync:{keys['postgres_password']}@127.0.0.1:5432/osync",
               S3_ENDPOINT="http://127.0.0.1:9000",
               S3_PUBLIC_ENDPOINT=options["s3_public_endpoint"], S3_BUCKET="osync-bucket",
               S3_REGION="us-east-1", S3_ACCESS_KEY=keys["s3_access_key"],
               S3_SECRET_KEY=keys["s3_secret_key"], BETTER_AUTH_SECRET=keys["auth_secret"],
               SYNC_TOKEN_SECRET=keys["sync_secret"], SYNC_TOKEN_TTL_SECONDS="120")
    return pg, s3, api


def healthy(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


class Supervisor:
    def __init__(self):
        self.children = []

    def start(self, name, command, env, quiet=False):
        print(f"[app] Starting {name}", flush=True)
        p = subprocess.Popen(command, env=env, cwd="/app", start_new_session=True,
                             stdout=subprocess.DEVNULL if quiet else None,
                             stderr=subprocess.DEVNULL if quiet else None)
        self.children.append((name, p))
        return p

    def check(self):
        for name, p in self.children:
            if p.poll() is not None:
                raise RuntimeError(f"{name} exited (code {p.returncode})")

    def ready(self, name, predicate, seconds=180):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.check()
            if predicate():
                return
            time.sleep(1)
        raise RuntimeError(f"{name} did not become ready within {seconds}s")

    def command(self, name, command, env, quiet=False):
        p = self.start(name, command, env, quiet=quiet)
        try:
            code = p.wait(timeout=180)
            if code:
                raise RuntimeError(f"{name} failed (code {code})")
        finally:
            if p.poll() is not None:
                self.children.remove((name, p))

    def stop(self):
        # Reverse dependency order. Fast PostgreSQL shutdown flushes data for cold backups.
        for name, p in reversed(self.children):
            if p.poll() is not None:
                continue
            print(f"[app] Stopping {name}", flush=True)
            try:
                p.send_signal(signal.SIGINT if name == "PostgreSQL" else signal.SIGTERM)
                p.wait(timeout=25)
            except subprocess.TimeoutExpired:
                print(f"[app] {name} shutdown timed out", flush=True)
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            except ProcessLookupError:
                pass


def main():
    os.umask(0o077)
    data = Path("/data")
    data.mkdir(exist_ok=True)
    os.chmod(data, 0o711)  # Service users can reach their private subdirectories.
    marker = data / "admin-initialized"
    options = validate_options(json.loads((data / "options.json").read_text()), not marker.exists())
    keys = load_secrets(data)
    import pwd
    for dirname, user in (("postgres", "postgres"), ("minio", "minio"), ("coordinators", "osync")):
        folder = data / dirname
        folder.mkdir(exist_ok=True)
        account = pwd.getpwnam(user)
        os.chown(folder, account.pw_uid, account.pw_gid)
        os.chmod(folder, 0o700)
    pg, s3, api = environments(options, keys)
    services = Supervisor()

    def shutdown(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        services.start("PostgreSQL", ["docker-entrypoint.sh", "postgres", "-c", "listen_addresses=127.0.0.1"], pg)
        services.ready("PostgreSQL", lambda: subprocess.run(
            ["pg_isready", "-h", "127.0.0.1", "-U", "osync", "-d", "osync"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0)
        services.start("MinIO", ["su-exec", "minio", "minio", "server", "/data/minio",
                                 "--address", ":9000", "--console-address", "127.0.0.1:9001"], s3)
        services.ready("MinIO", lambda: healthy("http://127.0.0.1:9000/minio/health/live"))
        services.command("Database migrations", ["su-exec", "osync", "./osync", "setup"], api)
        if not marker.exists():
            bootstrap = dict(api, ADMIN_EMAIL=options["admin_email"], ADMIN_PASSWORD=options["admin_password"])
            services.command("Admin bootstrap", ["su-exec", "osync", "./osync", "create-admin"], bootstrap, quiet=True)
            marker.write_text("initialized\n")
            print("[app] Admin initialized. You may now clear admin_password in App options.")
        services.start("Osync", ["su-exec", "osync", "./osync"], api)
        services.ready("Osync", lambda: healthy("http://127.0.0.1:3000/health"))
        print("[app] All services ready.")
        failures = 0
        while True:
            services.check()
            ok = healthy("http://127.0.0.1:3000/health") and healthy("http://127.0.0.1:9000/minio/health/live")
            failures = 0 if ok else failures + 1
            if failures >= 6:
                raise RuntimeError("Service health checks failed for approximately one minute")
            time.sleep(10)
    except KeyboardInterrupt:
        print("[app] Shutdown requested.")
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        services.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Do not print option values, credentials, or child environment.
        print(f"[app] Startup/runtime error: {exc}", file=sys.stderr)
        sys.exit(1)
