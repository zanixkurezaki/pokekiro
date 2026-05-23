import json
import discord
from datetime import datetime
from discord.ext import commands

from database.pokemons_database import pokemons
from database.movesets_database import pokemon_movesets
from utils.stat_generator import calculate_stats
from cogs.evolution_system import get_evolved_poke, send_evolution_prompt
from utils.artwork_handler import get_artwork_url, get_pokemon_artwork

DATA_FILE = "data/trainers_collection_database.json"

MAX_LEVEL = 100

STATS = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]

BASE_XP = 1

def get_booster_multiplier(poke: dict) -> int:
    """Return active booster bonus XP for a pokemon, or 0 if expired/none."""
    booster = poke.get("xp_booster")
    if not booster:
        return 0
    end_time = datetime.fromisoformat(booster["ends_at"])
    if datetime.now() >= end_time:
        return 0
    return booster.get("multiplier", 0)

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        prefixes = await self.bot.get_prefix(message)
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        if any(message.content.startswith(p) for p in prefixes):
            return

        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return

        user_id = str(message.author.id)
        user_data = data.get(user_id)
        if not user_data:
            return

        selected_no = user_data.get("selected_pokemon")
        pokemon_list = user_data.get("pokemon", [])

        if selected_no is None or not (1 <= selected_no <= len(pokemon_list)):
            return

        poke = pokemon_list[selected_no - 1]

        raw_xp = poke.get("xp", 0)
        if isinstance(raw_xp, str) and "/" in raw_xp:
            try:
                current_xp = int(raw_xp.split("/")[0])
            except ValueError:
                current_xp = 0
        else:
            try:
                current_xp = int(raw_xp)
            except (ValueError, TypeError):
                current_xp = 0

        current_level = poke.get("level", 1)
        new_level = current_level
        leveled_up = False

        if current_level >= MAX_LEVEL:
            new_level = MAX_LEVEL
            new_xp = 5000
        else:
            current_xp += BASE_XP + get_booster_multiplier(poke)

            while new_level < MAX_LEVEL:
                xp_needed = new_level * 50
                if current_xp >= xp_needed:
                    current_xp -= xp_needed
                    new_level += 1
                    leveled_up = True

                    base = next((p for p in pokemons if p["name"] == poke["name"]), None)
                    if base:
                        current_stats = poke.get("stats", {})
                        ivs_only = {stat: current_stats.get(f"{stat}_iv", 0) for stat in STATS}

                        poke["stats"] = calculate_stats(
                            base["base_stats"],
                            ivs_only,
                            new_level,
                            poke["nature"]
                        )
                else:
                    break

            new_xp = current_xp

        xp_needed_display = new_level * 50 if new_level < MAX_LEVEL else 5000
        xp_display = f"{new_xp}/{xp_needed_display}"

        poke["level"] = new_level
        poke["xp"] = xp_display

        newly_unlocked = []
        if leveled_up:
            moveset_entry = next((p for p in pokemon_movesets if p["name"].lower() == poke["name"].lower()), None)
            if moveset_entry:
                current_available = poke.get("available_moves", [])
                for m in moveset_entry["moves"]:
                    method = m["method"]
                    if method == "Breeding":
                        continue
                    try:
                        if int(method) == new_level and m["move"] not in current_available:
                            current_available.append(m["move"])
                            newly_unlocked.append(m["move"])
                        elif int(method) <= new_level and m["move"] not in current_available:
                            current_available.append(m["move"])
                    except ValueError:
                        continue
                poke["available_moves"] = current_available

        pokemon_list[selected_no - 1] = poke
        user_data["pokemon"] = pokemon_list
        data[user_id] = user_data

        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

        if leveled_up:
            embed = discord.Embed(
                title="Level Up!",
                description=f"Your **{poke['name']}** is now level **{new_level}**.",
                color=discord.Color.gold()
            )

            artwork_file = None
            shiny_artwork_file = None
            for db_p in pokemons:
                if db_p["name"].lower() == poke["name"].lower():
                    artwork_file, _ = get_pokemon_artwork(db_p, poke.get("gender", ""), False)
                    shiny_artwork_file, _ = get_pokemon_artwork(db_p, poke.get("gender", ""), True)
                    break

            is_shiny = poke.get("shiny", False)
            file = None
            if is_shiny and shiny_artwork_file:
                embed.set_thumbnail(url=get_artwork_url(shiny_artwork_file, shiny=True))
            elif artwork_file:
                embed.set_thumbnail(url=get_artwork_url(artwork_file))

            if newly_unlocked:
                unlocked_lines = "\n".join(
                    f"Congratulations {message.author.display_name}! Your **{poke['name']}** has unlocked **{m}**!"
                    for m in newly_unlocked
                )
                embed.add_field(name="", value=unlocked_lines, inline=False)

            await message.channel.send(embed=embed)

            evolved = get_evolved_poke(poke)
            if evolved:
                await send_evolution_prompt(message.channel, user_id, selected_no - 1, poke, evolved)

async def setup(bot):
    await bot.add_cog(XPSystem(bot))
