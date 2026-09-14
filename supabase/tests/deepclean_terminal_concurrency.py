"""Database integration gate for concurrent identical DeepClean callbacks.

Requires a migrated disposable database via SUPABASE_DB_URL and psycopg 3.
The test opens two real transactions and proves row locking converges them on
one mutation and one terminal ledger effect.
"""

from __future__ import annotations

import os
import threading
from urllib.parse import urlparse
import uuid

import psycopg
from psycopg.types.json import Jsonb


DATABASE_URL = os.environ.get("SUPABASE_DB_URL")
if not DATABASE_URL:
    raise SystemExit("SUPABASE_DB_URL is required")
database_target = urlparse(DATABASE_URL)
if database_target.hostname not in {"127.0.0.1", "localhost", "::1"}:
    raise SystemExit("SUPABASE_DB_URL must target a disposable loopback database")

OUTPUT_SHA256 = "a" * 64
INPUT_SHA256 = "b" * 64
ENGINE_VERSION = "concurrency-test-v1"
RUNTIME_MS = 12
GPU_TYPE = "disposable-db"
REPORT = {"concurrency": True, "public": True}

user_id = uuid.uuid4()
job_id = uuid.uuid4()
barrier = threading.Barrier(2)
outcomes: list[str] = []
errors: list[BaseException] = []


def finalize() -> None:
    try:
        with psycopg.connect(DATABASE_URL) as connection:
            barrier.wait()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select public.finalize_deepclean_job_terminal(
                      %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        job_id,
                        "completed",
                        OUTPUT_SHA256,
                        INPUT_SHA256,
                        ENGINE_VERSION,
                        RUNTIME_MS,
                        GPU_TYPE,
                        None,
                        Jsonb(REPORT),
                    ),
                )
                outcomes.append(cursor.fetchone()[0]["outcome"])
    except BaseException as exc:  # surface failures after both threads join
        errors.append(exc)


with psycopg.connect(DATABASE_URL, autocommit=True) as setup:
    with setup.cursor() as cursor:
        cursor.execute("insert into auth.users (id) values (%s)", (user_id,))
        cursor.execute(
            """
            insert into public.deepclean_jobs
              (id, user_id, status, input_path, output_path, credits_reserved)
            values (%s, %s, 'processing', 'in/concurrent', 'out/concurrent', 1)
            """,
            (job_id, user_id),
        )

try:
    threads = [threading.Thread(target=finalize) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("concurrent terminal transactions did not finish")
    if errors:
        raise errors[0]
    if sorted(outcomes) != ["applied", "duplicate"]:
        raise AssertionError(f"unexpected concurrent outcomes: {outcomes!r}")

    with psycopg.connect(DATABASE_URL) as verification:
        with verification.cursor() as cursor:
            cursor.execute(
                "select status, output_sha256 from public.deepclean_jobs where id = %s",
                (job_id,),
            )
            if cursor.fetchone() != ("completed", OUTPUT_SHA256):
                raise AssertionError("concurrent callback terminal mutation drifted")
            cursor.execute(
                """
                select count(*) from public.credit_ledger
                where job_id = %s and kind in ('deepclean_capture', 'deepclean_release')
                """,
                (job_id,),
            )
            if cursor.fetchone()[0] != 1:
                raise AssertionError("concurrent callbacks created multiple terminal effects")
finally:
    with psycopg.connect(DATABASE_URL, autocommit=True) as cleanup:
        with cleanup.cursor() as cursor:
            cursor.execute("delete from auth.users where id = %s", (user_id,))

print("concurrent identical callbacks: applied + duplicate; one terminal ledger effect")
