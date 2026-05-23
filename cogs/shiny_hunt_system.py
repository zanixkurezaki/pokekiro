import json
import os
import discord
from datetime import datetime
from discord.ext import commands
from discord.ui import View, Button

from database.pokemons_database import pokemons
from utils.registered_checker import check_registration
from utils.constants import UI_EMOJIS

SHINY_CHAINS_FILE = "data/trainers_shiny_chains_database.json"

def load_chains() -> dict:
    if not os.path.exists(SHINY_CHAINS_FILE):
        return {}
    with open(SHINY_CHAINS_FILE, "r") as f:
        return json.load(f)

def save_chains(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(SHINY_CHAINS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def find_pokemon(name: str):
    return next(
        (p for p in pokemons if p["name"].lower() == name.lower() and p.get("catchable") == "Yes"),
        None
    )

def fmt_remaining(end_iso: str) -> str | None:
    end_time = datetime.fromisoformat(end_iso)
    if datetime.now() >= end_time:
        return None
    remaining = end_time - datetime.now()
    days    = remaining.days
    hours   = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    seconds = remaining.seconds % 60
    return f"{days} days, {hours} hours and {minutes} minutes, {seconds} seconds"

class ShinyHuntConfirmView(View):
    def __init__(self, ctx, new_pokemon: str, user_id: str):
        super().__init__(timeout=60)
        self.ctx         = ctx
        self.new_pokemon = new_pokemon
        self.user_id     = user_id
        self.msg         = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your shiny hunt!", ephemeral=True)

        chains = load_chains()
        existing = chains.get(self.user_id, {})
        chains[self.user_id] = {
            "pokemon": self.new_pokemon,
            "shiny_chain": 0,
            "shiny_charm_expires": existing.get("shiny_charm_expires")
        }
        save_chains(chains)

        self.stop()
        await interaction.response.edit_message(view=None)
        await interaction.followup.send(f"You are now shiny hunting **{self.new_pokemon}**.")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your shiny hunt!", ephemeral=True)

        self.stop()
        await interaction.response.edit_message(view=None)
        await interaction.followup.send("Shiny hunt cancelled.")

    async def on_timeout(self):
        if self.msg:
            try:
                await self.msg.edit(view=None)
            except Exception:
                pass

class ShinyHuntSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="shiny", invoke_without_command=False)
    async def shiny(self, ctx):
        pass

    @shiny.command(name="hunt")
    async def shiny_hunt(self, ctx, *, pokemon_name: str = None):
        if not await check_registration(ctx):
            return

        user_id = str(ctx.author.id)
        chains  = load_chains()
        user_data = chains.get(user_id, {"pokemon": None, "shiny_chain": 0})
        spark = UI_EMOJIS["spark"]

        if not pokemon_name:
            current_poke = user_data.get("pokemon")
            chain        = user_data.get("shiny_chain", 0)
            charm_exp    = user_data.get("shiny_charm_expires")

            embed = discord.Embed(
                title=f"Shiny Hunt {spark}",
                color=discord.Color.gold()
            )
            embed.add_field(
                name="Currently Hunting",
                value=current_poke if current_poke else "None",
                inline=False
            )
            embed.add_field(
                name="Chain",
                value=str(chain),
                inline=False
            )

            if charm_exp:
                time_str = fmt_remaining(charm_exp)
                if time_str:
                    embed.add_field(
                        name="\u200b",
                        value=f"You have a Shiny Charm active that expires in {time_str}.",
                        inline=False
                    )

            return await ctx.send(embed=embed)

        pokemon = find_pokemon(pokemon_name.strip())
        if not pokemon:
            return await ctx.reply(f"**{pokemon_name}** doesn't exist or is not catchable!")

        actual_name = pokemon["name"]

        if not user_data.get("pokemon") or user_data.get("shiny_chain", 0) == 0:
            chains[user_id] = {
                "pokemon": actual_name,
                "shiny_chain": 0,
                "shiny_charm_expires": user_data.get("shiny_charm_expires")
            }
            save_chains(chains)
            return await ctx.reply(f"You are now shiny hunting **{actual_name}**.")

        if user_data["pokemon"].lower() != actual_name.lower():
            view = ShinyHuntConfirmView(ctx, actual_name, user_id)
            msg = await ctx.reply(
                "Are you sure you want to shiny hunt a different pokémon? Your streak will be reset.",
                view=view
            )
            view.msg = msg
        else:
            await ctx.reply(f"You are already shiny hunting **{actual_name}**.")

async def setup(bot):
    await bot.add_cog(ShinyHuntSystem(bot))
