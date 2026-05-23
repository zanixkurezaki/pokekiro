import json
from discord.ext import commands
from utils.registered_checker import check_registration
from utils.constants import GENDER_EMOJIS

DATA_FILE = "data/trainers_collection_database.json"

class Select(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def select(self, ctx, order_number: int):
        if not await check_registration(ctx):
            return

        user_id = str(ctx.author.id)

        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        if user_id not in data or not data[user_id]["pokemon"]:
            return await ctx.send("You have no Pokémon.")

        pokemons = data[user_id]["pokemon"]

        if order_number < 1 or order_number > len(pokemons):
            return await ctx.send("Invalid Pokémon order number.")

        prev_selected = data[user_id].get("selected_pokemon")

        if prev_selected == order_number:
            return await ctx.send("That Pokémon is already selected.")

        selected = pokemons[order_number - 1]
        data[user_id]["selected_pokemon"] = order_number

        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

        gender_emoji = GENDER_EMOJIS.get(selected['gender'].lower(), "")
        msg = (
            f"You selected your **Level {selected['level']} {selected['name']}** "
            f"{gender_emoji} **({selected['stats']['total_iv_percent']:.2f}%) "
            f"No. {order_number}**"
        )

        if prev_selected:
            prev_poke = pokemons[prev_selected - 1]
            msg += f" (from {prev_poke['name']} No. {prev_selected})."

        await ctx.send(msg)

    @commands.command()
    async def unselect(self, ctx):
        if not await check_registration(ctx):
            return

        user_id = str(ctx.author.id)

        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        selected_no = data.get(user_id, {}).get("selected_pokemon")
        if not selected_no:
            return await ctx.send("You have no Pokémon selected.")

        poke = data[user_id]["pokemon"][selected_no - 1]
        data[user_id]["selected_pokemon"] = None

        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

        gender_emoji = GENDER_EMOJIS.get(poke['gender'].lower(), "")
        await ctx.send(
            f"You unselected **Level {poke['level']} {poke['name']}** "
            f"{gender_emoji} **({poke['stats']['total_iv_percent']:.2f}%) "
            f"No. {selected_no}**"
        )

async def setup(bot):
    await bot.add_cog(Select(bot))
