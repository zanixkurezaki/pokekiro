import discord, json, os

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
from utils.constants import (
    CURRENCY_EXCHANGE_AND_BALANCE,
    XP_BOOSTERS_AND_CANDIES_EMOJIS,
    EVOLUTION_ITEMS_EMOJIS,
    FORM_CHANGING_ITEMS_EMOJIS,
    HELD_ITEMS_EMOJIS,
    NATURE_MINTS_EMOJIS,
    HUNTING_ITEMS_EMOJIS,
    BATTLE_ITEMS_EMOJIS,
)
from utils.registered_checker import check_registration

INVENTORY_FILE = "data/trainers_inventory_database.json"
PAGE_SIZE = 20

PAGE_TITLES = {
    1: "Page 1 - XP Boosters & Candies",
    2: "Page 2 - Evolution Items",
    3: "Page 3 - Form Changing Items",
    4: "Page 4 - Held Items",
    5: "Page 5 - Nature Mints",
    6: "Page 6 - Hunting Items",
    7: "Page 7 - Battle Items",
    8: "Page 8 - Balance"
}

PAGE_EMOJI_DICTS = {
    1: XP_BOOSTERS_AND_CANDIES_EMOJIS,
    2: EVOLUTION_ITEMS_EMOJIS,
    3: FORM_CHANGING_ITEMS_EMOJIS,
    4: HELD_ITEMS_EMOJIS,
    5: NATURE_MINTS_EMOJIS,
    6: HUNTING_ITEMS_EMOJIS,
    7: BATTLE_ITEMS_EMOJIS,
    8: CURRENCY_EXCHANGE_AND_BALANCE,
}

def name_to_key(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")

def get_item_emoji(page: int, item_name: str) -> str:
    emoji_dict = PAGE_EMOJI_DICTS.get(page, {})
    key = name_to_key(item_name)
    return emoji_dict.get(key, "")

def make_embed(title: str, user) -> discord.Embed:
    embed = discord.Embed(title=title, color=discord.Color.gold())
    embed.set_author(name=user.name, icon_url=user.display_avatar.url)
    return embed

def build_item_pages(page: int, user_inv: dict, user) -> list:
    """Build paginated embeds for item pages (1-7)."""
    items = user_inv.get("items", {})
    item_list = list(items.items())
    total_items = len(item_list)

    if total_items == 0:
        embed = make_embed(PAGE_TITLES[page], user)
        embed.description = f"Total items: **{total_items}**"
        return [embed]

    pages = []
    for i in range(0, total_items, PAGE_SIZE):
        embed = make_embed(PAGE_TITLES[page], user)
        lines = []
        for idx, (name, count) in enumerate(item_list[i:i + PAGE_SIZE], start=i + 1):
            emoji = get_item_emoji(page, name)
            prefix = f"{emoji} " if emoji else ""
            lines.append(f"{idx}    {prefix}**{name}** x{count}")
        embed.description = f"Total items: **{total_items}**\n\n" + "\n".join(lines)
        embed.set_footer(text=f"Showing {i+1}-{min(i+PAGE_SIZE, total_items)} of {total_items}")
        pages.append(embed)

    return pages

def build_balance_embed(user_inv: dict, user) -> discord.Embed:
    pokecoin_emoji = CURRENCY_EXCHANGE_AND_BALANCE.get("pokecoin", "")
    shard_emoji = CURRENCY_EXCHANGE_AND_BALANCE.get("shard", "")

    embed = make_embed(PAGE_TITLES[8], user)
    embed.add_field(name=f"{pokecoin_emoji} Pokécoins", value=str(user_inv.get("pokecoins", 0)), inline=False)
    embed.add_field(name=f"{shard_emoji} Shards", value=str(user_inv.get("shards", 0)), inline=False)
    return embed

class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user_inv(self, user_id):
        if not os.path.exists(INVENTORY_FILE):
            return None
        with open(INVENTORY_FILE, "r") as f:
            data = json.load(f)
        return data.get(str(user_id))

    @commands.command(aliases=["inv"])
    async def inventory(self, ctx, page: int = None):
        if not await check_registration(ctx):
            return

        user_inv = self.get_user_inv(ctx.author.id)
        if not user_inv:
            with open(INVENTORY_FILE, "r") as f:
                inv_data = json.load(f)
            inv_data[str(ctx.author.id)] = {
                "pokecoins": 0,
                "shards": 0,
                "items": {}
            }
            with open(INVENTORY_FILE, "w") as f:
                json.dump(inv_data, f, indent=4)
            user_inv = inv_data[str(ctx.author.id)]

        if page == 8:
            return await self.show_balance(ctx, user_inv)
        elif page in range(1, 8):
            return await self.show_page(ctx, page, user_inv)

        embed = make_embed("Inventory 📦", ctx.author)
        embed.description = (
            "Use `@Pokékiro#4959 inventory <page>` to view different pages.\n\n"
            "Page 1\nXP Boosters & Candies\n\n"
            "Page 2\nEvolution Items\n\n"
            "Page 3\nForm Changing Items\n\n"
            "Page 4\nHeld Items\n\n"
            "Page 5\nNature Mints\n\n"
            "Page 6\nHunting Items\n\n"
            "Page 7\nBattle Items\n\n"
            "Page 8\nBalance"
        )
        await ctx.send(embed=embed, view=InventoryPageSelect(ctx, None))

    async def show_page(self, ctx, page, user_inv):
        pages = build_item_pages(page, user_inv, ctx.author)
        view = InventoryPageSelect(ctx, page)
        msg = await ctx.send(embed=pages[0], view=view)
        if len(pages) > 1:
            await msg.edit(view=Paginator(ctx, pages))

    async def show_balance(self, ctx, user_inv):
        embed = build_balance_embed(user_inv, ctx.author)
        await ctx.send(embed=embed, view=InventoryPageSelect(ctx, 8))

class InventoryPageSelect(discord.ui.View):
    def __init__(self, ctx, current_page):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.current_page = current_page

        options = [
            discord.SelectOption(label=f"Page {i}", value=str(i), description=desc)
            for i, desc in {
                1: "XP Boosters & Candies",
                2: "Evolution Items",
                3: "Form Changing Items",
                4: "Held Items",
                5: "Nature Mints",
                6: "Hunting Items",
                7: "Battle Items",
                8: "Balance"
            }.items()
        ]
        select = discord.ui.Select(placeholder="Open a page", options=options)
        select.callback = self.callback
        self.add_item(select)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your inventory!", ephemeral=True)

        page = int(interaction.data['values'][0]) if interaction.data and 'values' in interaction.data else 1
        cog = self.ctx.bot.get_cog("Inventory")
        user_inv = cog.get_user_inv(interaction.user.id) or {}

        if page == 8:
            embed = build_balance_embed(user_inv, interaction.user)
            await interaction.response.send_message(embed=embed, view=InventoryPageSelect(self.ctx, 8))

        elif page in range(1, 8):
            pages = build_item_pages(page, user_inv, interaction.user)
            view = InventoryPageSelect(self.ctx, page)
            await interaction.response.send_message(embed=pages[0], view=view)

            if len(pages) > 1:
                msg = await interaction.original_response()
                await msg.edit(view=Paginator(self.ctx, pages))

async def setup(bot):
    await bot.add_cog(Inventory(bot))
