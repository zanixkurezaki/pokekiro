import json
import os
from discord.ext import commands

DATA_FILE = "data/trainers_collection_database.json"


def load_collection() -> dict:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_collection(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_friendship_points(pokemon: dict) -> dict:
    if not isinstance(pokemon, dict):
        return pokemon
    try:
        fp = int(pokemon.get("friendship_points", 0))
    except (TypeError, ValueError):
        fp = 0
    pokemon["friendship_points"] = max(fp, 0)
    return pokemon


def add_friendship_points(pokemon: dict, amount: int = 5) -> int:
    ensure_friendship_points(pokemon)
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        amount = 0
    if amount < 0:
        amount = 0
    pokemon["friendship_points"] += amount
    return pokemon["friendship_points"]


def backfill_friendship(data: dict) -> bool:
    changed = False
    for user_data in data.values():
        if not isinstance(user_data, dict):
            continue
        for p in user_data.get("pokemon", []):
            if isinstance(p, dict):
                before = p.get("friendship_points")
                ensure_friendship_points(p)
                if before != p.get("friendship_points"):
                    changed = True
    return changed


class FriendshipSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        data = load_collection()
        if backfill_friendship(data):
            save_collection(data)


async def setup(bot):
    await bot.add_cog(FriendshipSystem(bot))
