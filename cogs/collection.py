import discord, json

class Paginator(discord.ui.View):
    def __init__(self, ctx, pages, timeout=120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.pages = pages
        self.current = 0

    async def update_message(self, interaction):
        await interaction.response.edit_message(embed=self.pages[self.current])

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("You can't control this.", ephemeral=True)
        if self.current > 0:
            self.current -= 1
            await self.update_message(interaction)

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("You can't control this.", ephemeral=True)
        if self.current < len(self.pages) - 1:
            self.current += 1
            await self.update_message(interaction)

from discord.ext import commands
from utils.constants import GENDER_EMOJIS, UI_EMOJIS

DATA_FILE = "data/trainers_collection_database.json"
PAGE_SIZE = 10

from utils.registered_checker import check_registration

class Collection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def collection(self, ctx):
        if not await check_registration(ctx):
            return

        user_id = str(ctx.author.id)

        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        if user_id not in data or not data[user_id]["pokemon"]:
            return await ctx.reply("You have no Pokémon in your collection.")

        pokes = data[user_id]["pokemon"]
        pages = []

        for i in range(0, len(pokes), PAGE_SIZE):
            embed = discord.Embed(title="Your Collection", color=discord.Color.gold())
            lines = []

            for idx, p in enumerate(pokes[i:i + PAGE_SIZE], start=i + 1):
                stats = p.get('stats', {})
                iv_percent = stats.get('total_iv_percent', 0)
                gender_emoji = GENDER_EMOJIS.get(p['gender'].lower(), "")
                shiny_prefix = f"{UI_EMOJIS['spark']} " if p.get("shiny", False) else ""
                lines.append(
                    f"`{idx}`    **{shiny_prefix}{p['name']}** {gender_emoji}    •    Lvl. {p['level']}    •    {iv_percent}%"
                )

            embed.description = "\n".join(lines)
            embed.set_footer(
                text=f"Showing {i+1}–{min(i+PAGE_SIZE, len(pokes))} of {len(pokes)}"
            )
            pages.append(embed)

        if not pages:
            return

        msg = await ctx.send(embed=pages[0])
        if len(pages) > 1:
            await msg.edit(view=Paginator(ctx, pages))

async def setup(bot):
    await bot.add_cog(Collection(bot))
