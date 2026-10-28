"""Docker integration test on disposable named volumes; never use an existing container."""
import datetime
import hashlib
import hmac
import http.cookiejar
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_ready(url, container):
    for _ in range(180):
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as r:
                if r.status == 200:
                    return
        except OSError:
            pass
        if docker("inspect", "-f", "{{.State.Running}}", container) != "true":
            raise AssertionError("Container exited before becoming ready")
        time.sleep(1)
    raise AssertionError("API startup timed out")


def s3_request(endpoint, keys, method, path, body=b""):
    now = datetime.datetime.now(datetime.timezone.utc)
    stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    digest = hashlib.sha256(body).hexdigest()
    headers = {"host": urlsplit(endpoint).netloc, "x-amz-content-sha256": digest, "x-amz-date": stamp}
    signed = ";".join(sorted(headers))
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    canonical = "\n".join((method, path, "", canonical_headers, signed, digest))
    scope = f"{day}/us-east-1/s3/aws4_request"
    string = f"AWS4-HMAC-SHA256\n{stamp}\n{scope}\n{hashlib.sha256(canonical.encode()).hexdigest()}"
    key = ("AWS4" + keys["s3_secret_key"]).encode()
    for part in (day, "us-east-1", "s3", "aws4_request"):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, string.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = (f"AWS4-HMAC-SHA256 Credential={keys['s3_access_key']}/{scope}, "
                                f"SignedHeaders={signed}, Signature={signature}")
    req = urllib.request.Request(endpoint + path, method=method,
                                 data=body if method == "PUT" else None, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read()


def login(url, email, password):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    req = urllib.request.Request(url + "/api/auth/sign-in/email",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"Content-Type": "application/json", "Origin": url})
    with opener.open(req, timeout=10) as r:
        assert r.status == 200
    with opener.open(url + "/api/auth/get-session", timeout=10) as r:
        assert json.load(r)["user"]["role"] == "admin", "Admin session unavailable"


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else "osync-ha:test"
    name = "osync-smoke-" + secrets.token_hex(6)
    volume = name + "-data"
    restored = name + "-restored"
    api_port, s3_port = free_port(), free_port()
    while s3_port == api_port:
        s3_port = free_port()
    api, s3 = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{s3_port}"
    password = secrets.token_urlsafe(24)
    options = {"public_url": api, "s3_public_endpoint": s3, "language": "en",
               "admin_email": "smoke@example.com", "admin_password": password}
    docker("volume", "create", volume)
    try:
        docker("create", "--name", name, "--init", "--mount", f"type=volume,src={volume},dst=/data",
               "-p", f"127.0.0.1:{api_port}:3000", "-p", f"127.0.0.1:{s3_port}:9000", image)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "options.json"
            path.write_text(json.dumps(options))
            docker("cp", str(path), name + ":/data/options.json")
            docker("start", name)
            wait_ready(api, name)
            login(api, options["admin_email"], password)
            keys = json.loads(docker("exec", name, "cat", "/data/secrets.json"))
            try:
                s3_request(s3, keys, "PUT", "/smoke-test")
            except urllib.error.HTTPError as exc:
                if exc.code != 409:
                    raise
            payload = secrets.token_bytes(4096)
            s3_request(s3, keys, "PUT", "/smoke-test/persistence", payload)
            assert s3_request(s3, keys, "GET", "/smoke-test/persistence") == payload
            docker("stop", "--time", "110", name)
            assert docker("inspect", "-f", "{{.State.ExitCode}}", name) == "0", "Unclean shutdown"
            options["admin_password"] = ""
            path.write_text(json.dumps(options))
            docker("cp", str(path), name + ":/data/options.json")
            docker("start", name)
            wait_ready(api, name)
            assert json.loads(docker("exec", name, "cat", "/data/secrets.json")) == keys
            login(api, options["admin_email"], password)
            assert s3_request(s3, keys, "GET", "/smoke-test/persistence") == payload
            # Copy only after all services have stopped: equivalent storage semantics
            # to a cold backup, but not a test of Supervisor's backup implementation.
            docker("stop", "--time", "110", name)
            assert docker("inspect", "-f", "{{.State.ExitCode}}", name) == "0"
            docker("volume", "create", restored)
            docker("run", "--rm", "--entrypoint", "sh",
                   "--mount", f"type=volume,src={volume},dst=/source,readonly",
                   "--mount", f"type=volume,src={restored},dst=/target",
                   image, "-c", "cp -a /source/. /target/")
            docker("rm", name)
            docker("run", "-d", "--name", name, "--init",
                   "--mount", f"type=volume,src={restored},dst=/data",
                   "-p", f"127.0.0.1:{api_port}:3000", "-p", f"127.0.0.1:{s3_port}:9000", image)
            wait_ready(api, name)
            login(api, options["admin_email"], password)
            assert s3_request(s3, keys, "GET", "/smoke-test/persistence") == payload
            print("PASS: startup, admin login, S3 write/read, clean shutdown, restart and cold-copy restore")
    except Exception:
        log = subprocess.run(["docker", "logs", "--tail", "100", name], text=True, capture_output=True)
        for line in (log.stdout + log.stderr).splitlines():
            if any(word in line.lower() for word in ("[app]", "error", "fatal", "permission denied")):
                print(line.replace(password, "<redacted>"), file=sys.stderr)
        raise
    finally:
        # Only resources created under the random per-test name are removed.
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL)
        subprocess.run(["docker", "volume", "rm", volume], stdout=subprocess.DEVNULL)
        subprocess.run(["docker", "volume", "rm", restored], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
