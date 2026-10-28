import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("runtime", Path(__file__).parents[1] / "osync/runtime.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class ConfigurationTests(unittest.TestCase):
    def options(self):
        return {"public_url": "https://osync.example.com/", "s3_public_endpoint": "https://s3.example.com",
                "admin_email": "admin@example.com", "admin_password": "valid-test-password", "language": "ko"}

    def test_reject_invalid_origins(self):
        for value in ("", "ftp://example.com", "https://x/api", "https://u:p@x", "https://x?q=1",
                      "https://x/#a", "https://x\n", "https://x:invalid", "http://"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime.origin(value, "url")

    def test_first_start_needs_credentials_but_restart_does_not(self):
        options = self.options()
        options["admin_password"] = ""
        with self.assertRaises(ValueError):
            runtime.validate_options(options, True)
        self.assertEqual(runtime.validate_options(options, False)["public_url"], "https://osync.example.com")

    def test_secrets_are_stable_and_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            first = runtime.load_secrets(data)
            self.assertEqual(first, runtime.load_secrets(data))
            self.assertEqual(len(first), len(set(first.values())))
            self.assertEqual(len(runtime.base64.b64decode(first["minio_kms_key"].split(":")[1])), 32)

    def test_missing_keys_with_existing_storage_is_fatal(self):
        for folder in ("postgres", "minio", "coordinators"):
            with tempfile.TemporaryDirectory() as directory:
                data = Path(directory)
                (data / folder).mkdir()
                (data / folder / "existing").write_text("data")
                with self.assertRaises(ValueError):
                    runtime.load_secrets(data)
                self.assertFalse((data / "secrets.json").exists())

    def test_incomplete_secrets_are_not_rotated(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "secrets.json").write_text('{}')
            with self.assertRaises(ValueError):
                runtime.load_secrets(data)
            self.assertEqual(json.loads((data / "secrets.json").read_text()), {})

    def test_separate_service_credentials_and_external_s3_url(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(runtime.os.environ, {"SUPERVISOR_TOKEN": "do-not-forward"}):
            keys = runtime.load_secrets(Path(directory))
            options = runtime.validate_options(self.options(), True)
            pg, s3, api = runtime.environments(options, keys)
            for env in (pg, s3, api):
                self.assertNotIn("SUPERVISOR_TOKEN", env)
                self.assertNotIn("ADMIN_PASSWORD", env)
            self.assertEqual(api["S3_ENDPOINT"], "http://127.0.0.1:9000")
            self.assertEqual(api["S3_PUBLIC_ENDPOINT"], options["s3_public_endpoint"])
            self.assertEqual(s3["MINIO_SERVER_URL"], api["S3_PUBLIC_ENDPOINT"])
            self.assertNotIn("MINIO_KMS_SECRET_KEY", api)
            self.assertNotIn("DATABASE_URL", s3)


if __name__ == "__main__":
    unittest.main()
