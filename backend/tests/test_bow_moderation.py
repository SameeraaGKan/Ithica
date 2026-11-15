import asyncio

from app.services import oracle
from app.services.store import store as real_store


def test_fallback_bow_trial_is_not_put_on_leaderboard(monkeypatch):
    async def no_gemini(*a, **k):
        return None  # Gemini down: fallback path, so no safety check ran

    added = []

    class Recording:
        """Real store, except it records trial entries so we can check what reached the leaderboard."""
        def __getattr__(self, name):
            return getattr(real_store(), name)

        async def add_trial_entry(self, *a):
            added.append(a)

    monkeypatch.setattr(oracle.gemini, "generate_json", no_gemini)
    monkeypatch.setattr(oracle, "store", lambda: Recording())
    v = asyncio.run(oracle.judge(b"img", "image/jpeg", "bow_trial", fan_id="f1"))
    assert v.fallback is True
    assert added == []
