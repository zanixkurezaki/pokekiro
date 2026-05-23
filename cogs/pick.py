import discord, json, os
from discord.ext import commands
from datetime import date

from database.pokemons_database import pokemons
from utils.abilities_natures import get_random_nature as generate_nature, choose_ability
from utils.stat_generator import generate_ivs, calculate_stats
from utils.gender_ratio_generation import generate_gender

DATA_FILE      = "data/trainers_collection_database.json"
INVENTORY_FILE = "data/trainers_inventory_database.json"
LEVEL          = 1

STARTERS = {
    "bulbasaur", "charmander", "squirtle",
    "chikorita", "cyndaquil", "totodile",
    "treecko", "torchic", "mudkip",
    "turtwig", "chimchar", "piplup",
    "snivy", "tepig", "oshawott",
    "chespin", "fennekin", "froakie",
    "rowlet", "litten", "popplio",
    "grookey", "scorbunny", "sobble",
    "sprigatito", "fuecoco", "quaxly",
}


class Pick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        for file in [DATA_FILE, INVENTORY_FILE]:
            if not os.path.exists(file):
                if not os.path.exists("data"):
                    os.makedirs("data")
                with open(file, "w") as f:
                    json.dump({}, f)

    @commands.command()
    async def pick(self, ctx, *, pokemon_name: str):
        pokemon_name = pokemon_name.lower()
        user_id      = str(ctx.author.id)

        if pokemon_name not in STARTERS:
            return await ctx.reply(
                "You can only pick a starter Pokémon!\n"
                "Use `@Pokékiro starters` to see the available starters."
            )

        pokemon = next((p for p in pokemons if p["name"].lower() == pokemon_name), None)
        if not pokemon:
            return await ctx.reply("That Pokémon does not exist.")

        with open(DATA_FILE) as f:
            data = json.load(f)

        if user_id in data:
            return await ctx.reply("You have already chosen your starter Pokémon.")

        ivs    = generate_ivs()
        nature = generate_nature()
        ability = choose_ability(pokemon["ability"], pokemon["hidden_ability"])
        gender  = generate_gender(pokemon["gender_ratio"])
        stats   = calculate_stats(pokemon["base_stats"], ivs, LEVEL, nature)
        today   = date.today().isoformat()

        new_pokemon = {
            "name":   pokemon["name"],
            "level":  LEVEL,
            "xp":     f"0/{LEVEL * 50}",
            "nature": nature,
            "ability": ability,
            "gender": gender,
            "stats":  stats,
            "friendship_points": 0
        }

        data[user_id] = {
            "pokemon":          [new_pokemon],
            "selected_pokemon": 1,
            "date":             today
        }

        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

        with open(INVENTORY_FILE) as f:
            inv_data = json.load(f)

        inv_data[user_id] = {
            "pokecoins": 0,
            "shards":    0,
            "items":     {}
        }

        with open(INVENTORY_FILE, "w") as f:
            json.dump(inv_data, f, indent=4)

        await ctx.reply(
            f"🎉 **Starter Pokémon chosen!**\n"
            f"**{pokemon['name']}** is now with you and auto-selected.\n\n"
            f"Date: {today}"
        )


async def setup(bot):
    await bot.add_cog(Pick(bot))