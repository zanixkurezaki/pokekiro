import json
import discord
from discord.ext import commands
from database.pokemons_database import pokemons
from utils.constants import GENDER_EMOJIS, UI_EMOJIS, HELD_ITEMS_EMOJIS, HUNTING_ITEMS_EMOJIS
from utils.registered_checker import check_registration
from utils.artwork_handler import get_artwork_url, get_pokemon_artwork
from cogs.friendship_system import ensure_friendship_points

DATA_FILE = "data/trainers_collection_database.json"


def get_item_emoji(item_name: str) -> str:
    key = item_name.lower().replace(" ", "_")
    for emoji_dict in [HELD_ITEMS_EMOJIS, HUNTING_ITEMS_EMOJIS]:
        if key in emoji_dict:
            return emoji_dict[key]
    return "🔮"


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def info(self, ctx, order_number: int = None):
        if not await check_registration(ctx):
            return

        user_id = str(ctx.author.id)

        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        if user_id not in data or not data[user_id].get("pokemon"):
            return await ctx.send("You have no Pokémon.")

        pokes = data[user_id]["pokemon"]

        if order_number is None:
            order_number = data[user_id].get("selected_pokemon")
            if not order_number:
                return await ctx.send(
                    "You have no Pokémon selected. "
                    "Please provide an order number or select a Pokémon first."
                )

        if order_number < 1 or order_number > len(pokes):
            return await ctx.send("Invalid Pokémon order number.")

        p = ensure_friendship_points(pokes[order_number - 1])

        name      = p["name"]
        level     = p["level"]
        gender    = p["gender"]
        nature    = p["nature"]
        ability   = p["ability"]
        if isinstance(ability, list):
            ability = ability[0] if ability else ""

        stats    = p["stats"]
        is_shiny = p.get("shiny", False)
        held_item = p.get("held_item")

        poke_xp = p.get("xp", 0)
        xp_needed = level * 50 if level < 100 else 5000
        if isinstance(poke_xp, str) and "/" in poke_xp:
            poke_xp = poke_xp.split("/")[0]

        def iv(stat):
            return stats.get(f"{stat}_iv", 0)

        gender_emoji = GENDER_EMOJIS.get(gender.lower(), "")
        shiny_prefix = f"{UI_EMOJIS['spark']} " if is_shiny else ""

        embed = discord.Embed(
            title=f"{shiny_prefix}Level {level} {name}",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="Details",
            value=(
                f"**XP:** {poke_xp}/{xp_needed}\n"
                f"**Nature:** {nature}\n"
                f"**Ability:** {ability}\n"
                f"**Gender:** {gender_emoji}"
            ),
            inline=False
        )

        embed.add_field(
            name="Stats",
            value=(
                f"**HP:** {stats['hp']} – IV: {iv('hp')}/31\n"
                f"**Attack:** {stats['attack']} – IV: {iv('attack')}/31\n"
                f"**Defense:** {stats['defense']} – IV: {iv('defense')}/31\n"
                f"**Sp. Attack:** {stats['special_attack']} – IV: {iv('special_attack')}/31\n"
                f"**Sp. Defense:** {stats['special_defense']} – IV: {iv('special_defense')}/31\n"
                f"**Speed:** {stats['speed']} – IV: {iv('speed')}/31\n"
                f"**Total IV:** {stats['total_iv_percent']}%"
            ),
            inline=False
        )

        # Held Item section — always shown
        if held_item:
            item_emoji = get_item_emoji(held_item)
            held_value = f"{item_emoji} {held_item}"
        else:
            held_value = "None"
        embed.add_field(name="Held Item", value=held_value, inline=False)
        embed.add_field(name="Friendship Points", value=str(p.get("friendship_points", 0)), inline=False)

        # Artwork — use database lookup by current name (handles mega forms too)
        db_p = next((p for p in pokemons if p["name"].lower() == name.lower()), None)
        artwork_file, _ = get_pokemon_artwork(db_p, p.get("gender", ""), False) if db_p else (None, False)
        shiny_artwork_file, _ = get_pokemon_artwork(db_p, p.get("gender", ""), True) if db_p else (None, True)

        if is_shiny and shiny_artwork_file:
            embed.set_image(url=get_artwork_url(shiny_artwork_file, shiny=True))
        elif artwork_file:
            embed.set_image(url=get_artwork_url(artwork_file))

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Info(bot))
