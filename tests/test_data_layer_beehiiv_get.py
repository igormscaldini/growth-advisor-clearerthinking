"""_beehiiv_get: retries on 429 / transient 5xx with backoff, and on connection errors."""
import requests

import data_layer as dl


class FakeResp:
    def __init__(self, status, headers=None):
        self.status_code = status
        self.headers = headers or {}


def _run(monkeypatch, outcomes):
    """Drive _beehiiv_get with a scripted requests.get: each outcome is a FakeResp to return or
    an exception to raise. Returns (result, sleeps)."""
    calls = iter(outcomes)
    sleeps = []

    def fake_get(url, **kwargs):
        out = next(calls)
        if isinstance(out, Exception):
            raise out
        return out

    monkeypatch.setattr(dl.requests, "get", fake_get)
    monkeypatch.setattr(dl.time, "sleep", lambda s: sleeps.append(s))
    return dl._beehiiv_get("https://api.beehiiv.com/v2/x"), sleeps


def test_success_first_try_does_not_sleep(monkeypatch):
    ok = FakeResp(200)
    resp, sleeps = _run(monkeypatch, [ok])
    assert resp is ok
    assert sleeps == []


def test_429_then_200_retries_with_exponential_backoff(monkeypatch):
    ok = FakeResp(200)
    resp, sleeps = _run(monkeypatch, [FakeResp(429), FakeResp(429), ok])
    assert resp is ok
    assert sleeps == [2.0, 4.0]  # 2 * 2**attempt


def test_retry_after_header_is_honoured_and_capped(monkeypatch):
    ok = FakeResp(200)
    resp, sleeps = _run(monkeypatch, [FakeResp(429, {"Retry-After": "7"}),
                                      FakeResp(429, {"Retry-After": "999"}), ok])
    assert resp is ok
    assert sleeps == [7.0, dl.BEEHIIV_MAX_BACKOFF_SECONDS]


def test_persistent_429_returns_last_response_after_max_attempts(monkeypatch):
    outcomes = [FakeResp(429) for _ in range(dl.BEEHIIV_MAX_ATTEMPTS + 3)]
    resp, sleeps = _run(monkeypatch, outcomes)
    assert resp is outcomes[dl.BEEHIIV_MAX_ATTEMPTS - 1]  # not more attempts than allowed
    assert len(sleeps) == dl.BEEHIIV_MAX_ATTEMPTS - 1
    assert resp.status_code == 429  # caller's raise_for_status() still sees the failure


def test_4xx_other_than_429_is_not_retried(monkeypatch):
    unauthorized = FakeResp(401)
    resp, sleeps = _run(monkeypatch, [unauthorized, FakeResp(200)])
    assert resp is unauthorized
    assert sleeps == []


def test_503_is_retried(monkeypatch):
    ok = FakeResp(200)
    resp, sleeps = _run(monkeypatch, [FakeResp(503), ok])
    assert resp is ok
    assert sleeps == [2.0]


def test_connection_error_then_success(monkeypatch):
    ok = FakeResp(200)
    resp, sleeps = _run(monkeypatch, [requests.exceptions.ConnectionError("boom"), ok])
    assert resp is ok
    assert sleeps == [1.5]


def test_connection_error_every_time_raises_after_max_attempts(monkeypatch):
    import pytest

    outcomes = [requests.exceptions.Timeout("slow") for _ in range(dl.BEEHIIV_MAX_ATTEMPTS)]
    with pytest.raises(requests.exceptions.Timeout):
        _run(monkeypatch, outcomes)


def test_backoff_helper_unparseable_retry_after_falls_back(monkeypatch):
    assert dl._beehiiv_backoff_seconds(FakeResp(429, {"Retry-After": "soon"}), 0) == 2.0
    assert dl._beehiiv_backoff_seconds(FakeResp(429), 3) == 16.0
    assert dl._beehiiv_backoff_seconds(FakeResp(429, {"Retry-After": "-5"}), 0) == 0.0
