"""C8 Phase-B gate for retry-safe terminal delivery."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import types
import unittest
from unittest.mock import patch

from PIL import Image


WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))


def load_worker_without_server_start():
    existing = sys.modules.get("worker")
    if existing is not None:
        return existing
    fake_runpod = types.ModuleType("runpod")
    fake_runpod.serverless = types.SimpleNamespace(start=lambda _config: None)
    with patch.dict(sys.modules, {"runpod": fake_runpod}), patch.dict(
        os.environ, {"DEEPCLEAN_PRELOAD": "0"}
    ):
        return importlib.import_module("worker")


worker = load_worker_without_server_start()


def response(status_code: int):
    return types.SimpleNamespace(status_code=status_code)


class WorkerNotificationTests(unittest.TestCase):
    def setUp(self):
        self.sent_payloads: list[str] = []
        self.delays: list[float] = []
        self.upload_calls = 0

    def run_job(self, statuses, *, processing_error: Exception | None = None):
        status_iter = iter(statuses)

        def fake_post(_url, *, data, headers, timeout):
            self.assertEqual(headers, {"content-type": "application/json"})
            self.assertEqual(timeout, 30)
            self.sent_payloads.append(data)
            item = next(status_iter)
            if isinstance(item, BaseException):
                raise item
            return response(item)

        def fake_download(_url, path):
            Image.new("RGB", (128, 128), (30, 60, 90)).save(path, format="PNG")

        private_reference = Image.new("RGB", (128, 128), (30, 60, 90))

        def fake_process(*, output_path, **_kwargs):
            if processing_error is not None:
                raise processing_error
            private_reference.save(output_path, format="PNG")
            return {
                "settings": {},
                "_quality_reference_image": private_reference,
                "public_detail": {"complete": True},
            }

        def fake_finalize(cleaned_path, output_path, **_kwargs):
            shutil.copyfile(cleaned_path, output_path)
            return {
                "photo_naturalization": {"enabled": False},
                "expert_refinement": {"applied": False},
            }

        def fake_upload(_storage_path, _path):
            self.upload_calls += 1

        payload = {
            "job_id": "notification-reliability",
            "webhook_url": "https://example.invalid/webhook",
            "webhook_secret": "test-webhook-secret",
            "input_url": "https://example.invalid/input.png",
            "input_path": "incoming/input.png",
            "output_path": "frozen/output.jpg",
            "profile": "standard",
            "output_mode": "stripped",
        }
        with patch.object(worker, "download", side_effect=fake_download), patch.object(
            worker, "identify_image", side_effect=[{"stage": "before"}, {"stage": "after"}]
        ), patch.object(
            worker, "run_deepclean", side_effect=fake_process
        ), patch.object(
            worker, "maybe_apply_neural_texture_lab", return_value={"enabled": False}
        ), patch.object(
            worker, "maybe_apply_content_repair_lab", return_value={"enabled": False}
        ), patch.object(
            worker, "quality_check", return_value={"ok": True, "reference_mode": "legacy_source_resized"}
        ), patch.object(
            worker, "finalize_output", side_effect=fake_finalize
        ), patch.object(
            worker, "upload_output", side_effect=fake_upload
        ), patch.object(
            worker, "delete_storage_object"
        ), patch.object(
            worker.requests, "post", side_effect=fake_post
        ), patch.object(
            worker.time, "sleep", side_effect=lambda delay: self.delays.append(delay)
        ):
            return worker.handler({"input": payload})

    def decoded_bodies(self):
        return [json.loads(item) for item in self.sent_payloads]

    def test_completed_500_then_success_reuses_body_and_never_sends_failed(self):
        result = self.run_job([500, 200])
        bodies = self.decoded_bodies()

        self.assertEqual(self.upload_calls, 1)
        self.assertEqual(len(bodies), 2)
        self.assertEqual(bodies[0], bodies[1])
        self.assertTrue(all(body["status"] == "completed" for body in bodies))
        self.assertEqual(result["delivery_status"], "acknowledged")
        self.assertEqual(result["processing_status"], "completed")

    def test_completed_429_then_success_uses_frozen_delay(self):
        result = self.run_job([429, 204])

        self.assertEqual(self.delays, [0.5])
        self.assertEqual(result["delivery_status"], "acknowledged")
        self.assertTrue(all(body["status"] == "completed" for body in self.decoded_bodies()))

    def test_completed_401_is_permanent_and_never_falls_back_to_failed(self):
        result = self.run_job([401])

        self.assertEqual(len(self.sent_payloads), 1)
        self.assertEqual(self.delays, [])
        self.assertEqual(self.decoded_bodies()[0]["status"], "completed")
        self.assertTrue(result["ok"])
        self.assertEqual(result["delivery_status"], "pending")
        self.assertEqual(result["delivery_error"], "HTTP 401 after 1 notification attempt(s)")

    def test_five_retryable_failures_preserve_uploaded_success(self):
        result = self.run_job([500, 500, 500, 500, 500])

        self.assertEqual(self.upload_calls, 1)
        self.assertEqual(self.delays, [0.5, 1.0, 2.0, 4.0])
        self.assertEqual(len(self.sent_payloads), 5)
        self.assertEqual(len(set(self.sent_payloads)), 1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["processing_status"], "completed")
        self.assertEqual(result["delivery_status"], "pending")
        self.assertRegex(result["output_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("test-webhook-secret", result["delivery_error"])

    def test_genuine_preupload_exception_sends_one_logical_failed_outcome(self):
        result = self.run_job([500, 200], processing_error=RuntimeError("processing broke"))
        bodies = self.decoded_bodies()

        self.assertEqual(self.upload_calls, 0)
        self.assertEqual(len(bodies), 2)
        self.assertEqual(bodies[0], bodies[1])
        self.assertTrue(all(body["status"] == "failed" for body in bodies))
        self.assertEqual(bodies[0]["failure_reason"], "processing broke")
        self.assertEqual(self.delays, [0.5])
        self.assertFalse(result["ok"])
        self.assertEqual(result["processing_status"], "failed")
        self.assertEqual(result["delivery_status"], "acknowledged")

    def test_completed_public_report_is_full_json_without_private_reference(self):
        result = self.run_job([200])
        body = self.decoded_bodies()[0]

        self.assertEqual(result["delivery_status"], "acknowledged")
        self.assertEqual(body["signature"], "test-webhook-secret")
        self.assertEqual(body["report"]["engine"]["public_detail"], {"complete": True})
        self.assertNotIn("_quality_reference_image", body["report"]["engine"])

    def test_connection_and_timeout_errors_retry_but_arbitrary_errors_do_not(self):
        with patch.object(worker.requests, "post", side_effect=[
            worker.requests.exceptions.ConnectionError("private-url"),
            worker.requests.exceptions.Timeout("secret"),
            response(200),
        ]) as post:
            outcome = worker.notify(
                "https://example.invalid/webhook",
                "secret-value",
                {"job_id": "retry-errors", "status": "failed"},
                sleeper=lambda delay: self.delays.append(delay),
            )
        self.assertEqual(post.call_count, 3)
        self.assertEqual(self.delays, [0.5, 1.0])
        self.assertEqual(outcome, {"attempts": 3, "status_code": 200})

        self.delays.clear()
        with patch.object(
            worker.requests,
            "post",
            side_effect=worker.requests.exceptions.InvalidURL("private-url"),
        ) as post:
            with self.assertRaises(worker.TerminalDeliveryError) as raised:
                worker.notify(
                    "https://example.invalid/webhook",
                    "secret-value",
                    {"job_id": "permanent-error", "status": "completed"},
                    sleeper=lambda delay: self.delays.append(delay),
                )
        self.assertEqual(post.call_count, 1)
        self.assertEqual(self.delays, [])
        self.assertEqual(raised.exception.error_class, "InvalidURL")
        self.assertNotIn("private-url", str(raised.exception))
        self.assertNotIn("secret-value", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
