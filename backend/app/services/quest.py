"""Athena's quest: the 7-step journey through ITHACA, computed from what the fan has actually done."""
from typing import Optional

from app.services.store import store

# key, title, Athena's line, CTA label, CTA target (a Hub path; {fan} = fan id, # = section on the map page)
STEPS = [
    ("bard", "Meet the Bard", "Tell the Bard where your voyage began, and he'll find your place in the saga.",
     "Talk to the Bard", "/onboard"),
    ("era", "Return to your era", "Your era glows on the map. Open a moment from it.",
     "Show my era", "/odyssey/{fan}#era-videos"),
    ("siren", "Hear the Siren", "Watch it on YouTube. The Siren will sing its story. Collect the relic she offers.",
     "Pick a video", "/odyssey/{fan}#era-videos"),
    ("oracle", "Prove it to the Oracle", "Words are cheap. Show the Oracle your FaZe merch and let her judge.",
     "Face the Oracle", "/oracle-cam?mode=argos"),
    ("song", "The Bard's song", "You've earned your song. Let the Bard sing your era.",
     "Play my episode", "/odyssey/{fan}#bard-song"),
    ("bow", "String the bow", "Only the true king strings the bow. Show the Oracle your best trickshot.",
     "Take the Bow Trial", "/oracle-cam?mode=bow_trial"),
    ("tier", "Claim your reward", "Your relics have raised you. Claim what you've earned.",
     "Open my tier", "/tiers"),
]

# Hub-side actions with no backend event of their own
# (visiting the Oracle or the Tiers page is enough to move the journey on: no extra click needed)
MARKABLE = {"era": "era_video", "song": "episode_play", "oracle": "oracle_visit", "bow": "trial_visit", "tier": "tiers_visit"}


async def progress(fan_id: str) -> Optional[dict]:
    st = store()
    fan = await st.get_fan(fan_id)
    if not fan:
        return None
    kinds = await st.fan_event_kinds(fan_id)
    types = {t for t, _ in kinds}
    relic_sources = {src for t, src in kinds if t == "relic"}
    manual = {t.removeprefix("quest_") for t in types if t.startswith("quest_")}  # Athena's "Done, next step"
    done = {
        "bard": bool(fan.get("path")) or "onboard" in types or "bard_onboard" in types,
        "era": "era_video" in types or "ext" in relic_sources or "watch" in types,
        "siren": "ext" in relic_sources,
        "oracle": "oracle_argos" in types or "oracle_visit" in types,
        "song": "episode_play" in types,
        "bow": "trial_entry" in types or "trial_visit" in types,
        "tier": "reward_claim" in types or "tiers_visit" in types,
    }
    done = {k: v or k in manual for k, v in done.items()}
    steps = [{"key": k, "title": t, "line": line, "cta": cta, "href": href.replace("{fan}", fan_id), "done": done[k]}
             for k, t, line, cta, href in STEPS]
    current = next((s for s in steps if not s["done"]), None)
    return {"fan_id": fan_id, "handle": fan.get("handle"), "steps": steps,
            "completed": sum(s["done"] for s in steps), "total": len(steps), "current": current}


async def mark(fan_id: str, step: str) -> bool:
    """Record a Hub-side step. Any step can also be ticked by hand (Athena's 'Done, next step')."""
    keys = {k for k, *_ in STEPS}
    if step not in keys:
        return False
    await store().upsert_fan(fan_id)
    await store().log_event(fan_id, MARKABLE.get(step, f"quest_{step}"), "web", {"quest": step})
    return True
