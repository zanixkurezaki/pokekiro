import discord
import json
from discord.ext import commands
from utils.constants import GENDER_EMOJIS, CURRENCY_EXCHANGE_AND_BALANCE

DATA_FILE = "data/trainers_collection_database.json"
INVENTORY_FILE = "data/trainers_inventory_database.json"

from utils.registered_checker import check_registration

class Release(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def release(self, ctx, order_number: int):
        if not await check_registration(ctx):
            return

        user_id = str(ctx.author.id)

        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        if user_id not in data or not data[user_id].get("pokemon"):
            return await ctx.reply("You have no Pokémon.")

        pokemon_list = data[user_id]["pokemon"]

        if not (1 <= order_number <= len(pokemon_list)):
            return await ctx.reply("Invalid Pokémon order number.")

        selected_no = data[user_id].get("selected_pokemon")
        if order_number == selected_no:
            return await ctx.reply(
                "You cannot release your selected Pokémon! Unselect it first."
            )

        poke = pokemon_list[order_number - 1]
        iv_percent = poke["stats"].get("total_iv_percent", 0)

        gender_emoji = GENDER_EMOJIS.get(poke.get('gender', '').lower(), "")
        pokecoin_emoji = CURRENCY_EXCHANGE_AND_BALANCE.get("pokecoin", "")

        text = (
            f"Are you sure you want to **release** your "
            f"**Level {poke['level']} {poke['name']} {gender_emoji} "
            f"({iv_percent:.2f}%) No. {order_number}** for **5 {pokecoin_emoji} Pokécoins**?"
        )

        view = ReleaseConfirmView(ctx, order_number)
        message = await ctx.reply(text, view=view)
        view.message = message

class ReleaseConfirmView(discord.ui.View):
    def __init__(self, ctx, order_number):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.order_number = order_number
        self.message = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "This is not your request!", ephemeral=True
            )

        user_id = str(self.ctx.author.id)

        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        if self.order_number - 1 >= len(data[user_id]["pokemon"]):
            return await interaction.response.edit_message(
                content="That Pokémon no longer exists.", view=None
            )

        selected = data[user_id].get("selected_pokemon")
        if selected and selected > self.order_number:
            data[user_id]["selected_pokemon"] -= 1

        data[user_id]["pokemon"].pop(self.order_number - 1)

        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

        with open(INVENTORY_FILE, "r") as f:
            inv_data = json.load(f)

        if user_id not in inv_data:
            inv_data[user_id] = {"pokecoins": 0}

        inv_data[user_id]["pokecoins"] += 5

        with open(INVENTORY_FILE, "w") as f:
            json.dump(inv_data, f, indent=4)

        self.stop()

        await interaction.response.edit_message(view=None)

        pokecoin_emoji = CURRENCY_EXCHANGE_AND_BALANCE.get("pokecoins", "")
        await self.ctx.send(
            f"You released **1** pokémon. You received **5 {pokecoin_emoji} Pokécoins!**"
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "This is not your request!", ephemeral=True
            )

        self.stop()

        await interaction.response.edit_message(view=None)
        await self.ctx.send("Aborted.")

    async def on_timeout(self):
        await self.message.edit(
            content="Time's up. Aborted.",
            view=None
        )

async def setup(bot):
    await bot.add_cog(Release(bot))
