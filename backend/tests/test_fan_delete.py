import asyncio

from app.services.store import MemoryStore


def test_delete_removes_only_that_fan():
    st = MemoryStore()

    async def run():
        await st.upsert_fan("f_gone", handle="gone")
        await st.upsert_fan("f_keep", handle="keep")
        await st.grant_relic("f_gone", "r_first_upload", "web")
        await st.grant_relic("f_keep", "r_first_upload", "web")
        await st.record_purchase("f_gone", "odyssey_pass", 499)
        return await st.delete_fan_data("f_gone")

    out = asyncio.run(run())
    assert out["fan"] is True and out["relics"] == 1 and out["purchases"] == 1
    assert "f_gone" not in st.fans and "f_keep" in st.fans
    assert "f_gone" not in st.fan_relics and "f_keep" in st.fan_relics
