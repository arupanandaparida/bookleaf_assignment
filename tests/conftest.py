"""Integration tests run the real FastAPI app against an in-memory SQLite DB; only the outbound AI HTTP call is mocked."""
import os

os.environ["DB_PATH"] = ":memory:"
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["LOGIN_RATE_LIMIT"] = "1000"
os.environ["AI_BREAKER_THRESHOLD"] = "100"  # keep the breaker out of the way

import time

import pytest
from fastapi.testclient import TestClient

from app.ai import provider
from app.main import app


class FakeAI:
    mode = "ok"  # ok | down
    calls: list = []


@pytest.fixture(scope="session")
def client():
    async def fake_post_json(url, headers, body):
        FakeAI.calls.append(body)
        if FakeAI.mode == "down":
            raise provider.HttpStatusError(529, "overloaded")
        classify = "triage" in body["system"]
        text = ('{"category":"Royalty & Payments","priority":"High","reasoning":"Royalty overdue"}' if classify else
                'Hi Ananya,\n\nThank you for writing in about your royalty for "Between Two Temples". We are checking this now and will confirm within 48 hours.\n\nWarm regards,\nTeam BookLeaf')
        return {"content": [{"type": "text", "text": text}], "usage": {"input_tokens": 500, "output_tokens": 80}}

    provider.post_json = fake_post_json

    async def no_sleep(_): return None
    provider.asyncio.sleep = no_sleep  # skip retry backoff in tests

    with TestClient(app) as c:  # `with` keeps one event loop alive so background classification tasks run
        yield c


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    return r.json().get("token")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def wait_for(fn, seconds=3.0):
    end = time.time() + seconds
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.05)
    raise AssertionError("timeout waiting for condition")
