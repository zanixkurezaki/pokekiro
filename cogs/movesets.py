import discord
from discord.ext import commands

from database.movesets_database import pokemon_movesets
from utils.constants import TYPE_EMOJIS, MOVE_CLASS_EMOJIS

PAGE_SIZE = 10

def get_type_emoji(type_name: str) -> str:
    return TYPE_EMOJIS.get(f"{type_name.lower()}_type", "")

def get_class_emoji(class_name: str) -> str:
    return MOVE_CLASS_EMOJIS.get(class_name.lower(), "")

def format_method(method: str) -> str:
    if method == "Breeding":
        return "Breeding"
    try:
        lvl = int(method)
        return f"Lv. {lvl}" if lvl > 0 else "Lv. 1"
    except ValueError:
        return method

def build_pages(pokemon_name: str, moves: list) -> list[discord.Embed]:
    total = len(moves)
    pages = []

    for i in range(0, total, PAGE_SIZE):
        chunk = moves[i:i + PAGE_SIZE]
        lines = []

        for idx, m in enumerate(chunk, start=i + 1):
            type_emoji = get_type_emoji(m["type"])
            class_emoji = get_class_emoji(m["class"])
            method_label = format_method(m["method"])
            lines.append(f"`{idx}` {type_emoji} {class_emoji} **{m['move']}**\n{method_label}")

        embed = discord.Embed(
            title=pokemon_name,
            description=f"**Total Moves:** `{total}`\n\n" + "\n\n".join(lines),
            color=discord.Color.gold()
        )
        start = i + 1
        end = min(i + PAGE_SIZE, total)
        embed.set_footer(text=f"Showing {start}–{end} out of {total}.")
        pages.append(embed)

    return pages

class MovesetPaginator(discord.ui.View):
    def __init__(self, ctx, pages: list[discord.Embed]):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.pages = pages
        self.current = 0

    async def update(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.pages[self.current])

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("You can't control this.", ephemeral=True)
        if self.current > 0:
            self.current -= 1
            await self.update(interaction)

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("You can't control this.", ephemeral=True)
        if self.current < len(self.pages) - 1:
            self.current += 1
            await self.update(interaction)

class Movesets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="movesets")
    async def movesets(self, ctx, *, pokemon_name: str = None):
        if not pokemon_name:
            return await ctx.reply("Usage: `@Pokékiro movesets <pokemon name>`")

        entry = next(
            (p for p in pokemon_movesets if p["name"].lower() == pokemon_name.strip().lower()),
            None
        )

        if not entry:
            return await ctx.reply(f"No moveset found for **{pokemon_name}**.")

        moves = entry["moves"]
        if not moves:
            return await ctx.reply(f"**{entry['name']}** has no moves in the database.")

        pages = build_pages(entry["name"], moves)

        msg = await ctx.send(embed=pages[0])
        if len(pages) > 1:
            await msg.edit(view=MovesetPaginator(ctx, pages))

async def setup(bot):
    await bot.add_cog(Movesets(bot))
