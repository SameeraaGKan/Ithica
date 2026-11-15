"""Tier system: the more relics a fan collects, the more rewards unlock.
Relic tiers are earned; the meet & greet is unlocked by the Odyssey Pass ($4.99).
Claims are logged as `reward_claim` events (so the War Room can count them) and kept per process."""
import hashlib
from typing import Optional

from app.services.store import relic_catalog, store

# (id, tier name, relics needed, reward title, description)
TIERS = [
    ("traveler", "Traveler", 1, "Ithaca badge + FaZe Discord role",
     "A profile badge on your Odyssey and a Traveler role in the FaZe Discord."),
    ("sailor", "Sailor", 5, "Era wallpaper pack",
     "Phone and desktop wallpapers for every era you've collected."),
    ("hero", "Hero", 10, "Early access to Era Drops + 15% off",
     "Shop the next era merch drop 24 hours before everyone else, with 15% off."),
    ("legend", "Legend", 20, "Limited Legend merch",
     "A numbered, Legends-only piece. Only fans at this tier can buy it."),
]

PASS_REWARD = ("meet_greet", "Meet your FaZe favorite",
               "Odyssey Pass holders are entered into the monthly virtual meet & greet with the FaZe member you pick.")

FAZE_MEMBERS = ["Rug", "Banks", "Apex", "Swagg", "Jarvis", "Adapt", "Kaysan", "Lacy", "Stable Ronaldo", "Silky"]

_claims: dict[str, dict[str, dict]] = {}  # fan_id -> reward_id -> claim


def _code(fan_id: str, reward_id: str) -> str:
    return "ITH-" + hashlib.sha1(f"{fan_id}:{reward_id}".encode()).hexdigest()[:6].upper()


async def status(fan_id: str) -> Optional[dict]:
    st = store()
    fan = await st.get_fan(fan_id)
    if not fan:
        return None
    relics = len(await st.list_fan_relics(fan_id))
    total = len(relic_catalog())
    has_pass = bool(fan.get("has_pass"))
    claimed = _claims.get(fan_id, {})

    current = None
    nxt = None
    rewards = []
    for rid, tier, need, title, desc in TIERS:
        unlocked = relics >= need
        if unlocked:
            current = {"id": rid, "name": tier, "relics_needed": need}
        elif nxt is None:
            nxt = {"id": rid, "name": tier, "relics_needed": need, "relics_to_go": need - relics}
        rewards.append({"id": rid, "tier": tier, "title": title, "description": desc, "relics_needed": need,
                        "requires_pass": False, "unlocked": unlocked, "claimed": rid in claimed,
                        "claim": claimed.get(rid)})
    pid, ptitle, pdesc = PASS_REWARD
    rewards.append({"id": pid, "tier": "Odyssey Pass", "title": ptitle, "description": pdesc, "relics_needed": 0,
                    "requires_pass": True, "unlocked": has_pass, "claimed": pid in claimed, "claim": claimed.get(pid)})
    return {
        "fan_id": fan_id,
        "relics": relics,
        "relics_total": total,
        "has_pass": has_pass,
        "tier": current,
        "next_tier": nxt,
        "rewards": rewards,
        "faze_members": FAZE_MEMBERS,
    }


async def claim(fan_id: str, reward_id: str, member: Optional[str] = None) -> dict:
    s = await status(fan_id)
    if s is None:
        raise LookupError("unknown fan")
    r = next((x for x in s["rewards"] if x["id"] == reward_id), None)
    if r is None:
        raise KeyError("unknown reward")
    if not r["unlocked"]:
        raise PermissionError("Get the Odyssey Pass to unlock this." if r["requires_pass"]
                              else f"Collect {r['relics_needed']} relics to unlock this.")
    if r["claimed"]:
        return r["claim"]
    if reward_id == "meet_greet":
        if member not in FAZE_MEMBERS:
            raise ValueError(f"pick a FaZe member: {', '.join(FAZE_MEMBERS)}")
        message = f"You're entered in this month's virtual meet & greet with FaZe {member}. Winners are told by iMessage."
    else:
        message = f"Unlocked: {r['title']}. Your code: {_code(fan_id, reward_id)}"
    c = {"reward_id": reward_id, "code": _code(fan_id, reward_id), "member": member, "message": message}
    _claims.setdefault(fan_id, {})[reward_id] = c
    await store().log_event(fan_id, "reward_claim", "web", {"reward_id": reward_id, "member": member})
    return c
