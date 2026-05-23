import discord
from discord.ext import commands
from discord.ui import View, Button
import json
import os
import math
from datetime import datetime

from utils.registered_checker import check_registration
from utils.constants import GENDER_EMOJIS, UI_EMOJIS
from utils.artwork_handler import get_artwork_url



DATA_FILE = "data/trainers_collection_database.json"
INVENTORY_FILE = "data/trainers_inventory_database.json"
MARKET_FILE = "data/market_database.json"

def load_market():
    if os.path.exists(MARKET_FILE):
        try:
            with open(MARKET_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"listings": []}

def save_market(market_data):
    os.makedirs("data", exist_ok=True)
    try:
        with open(MARKET_FILE, "w") as f:
            json.dump(market_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving market: {e}")
        return False

def load_collection():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_collection(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_inventory():
    try:
        with open(INVENTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_inventory(data):
    with open(INVENTORY_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def format_gender(gender):
    """Convert gender string to display emoji using constants.py"""
    g = str(gender).lower().strip()
    if g in ["male", "♂"]:
        return GENDER_EMOJIS["male"]
    elif g in ["female", "♀"]:
        return GENDER_EMOJIS["female"]
    else:
        return GENDER_EMOJIS["unknown"]

def get_pokemon_by_order(trainer_data, order_number):
    """Return pokemon dict at given 1-based order number, or None"""
    pokemon_list = trainer_data.get("pokemon", [])
    if 1 <= order_number <= len(pokemon_list):
        return pokemon_list[order_number - 1]
    return None

def remove_pokemon_by_order(trainer_data, order_number):
    """Remove and return pokemon at given 1-based order number"""
    pokemon_list = trainer_data.get("pokemon", [])
    if 1 <= order_number <= len(pokemon_list):
        return pokemon_list.pop(order_number - 1)
    return None

def add_pokemon_to_collection(trainer_data, pokemon):
    """Add pokemon back to trainer's collection"""
    if "pokemon" not in trainer_data:
        trainer_data["pokemon"] = []
    trainer_data["pokemon"].append(pokemon)

class MarketplacePagination(View):
    def __init__(self, listings, page=0, per_page=20, timeout=300):
        super().__init__(timeout=timeout)
        self.listings = listings
        self.page = page
        self.per_page = per_page
        self.max_pages = max(1, math.ceil(len(listings) / per_page))

    def get_page_listings(self):
        start = self.page * self.per_page
        return self.listings[start:start + self.per_page]

    def create_embed(self):
        embed = discord.Embed(title="Pokékiro Marketplace", color=0xFFD700)

        if not self.listings:
            embed.description = "No Pokémon available in the marketplace."
            return embed

        lines = []
        for listing in self.get_page_listings():
            poke = listing.get("pokemon", {})
            name = poke.get("name", "Unknown").title()
            level = poke.get("level", 1)
            gender = format_gender(poke.get("gender", ""))
            iv = poke.get("stats", {}).get("total_iv_percent", 0)
            price = listing.get("price", 0)
            mid = listing.get("market_id", "?")
            shiny_prefix = f"{UI_EMOJIS['spark']} " if poke.get("shiny", False) else ""
            lines.append(f"`{mid}`    {shiny_prefix}**{name}** {gender}    •    Lvl. {level}    •    {iv}%    •    {price:,}")
        end = min(start + self.per_page, len(self.listings))
        if self.max_pages > 1:
            embed.set_footer(text=f"Showing {start+1}–{end} of {len(self.listings)} | Page {self.page+1}/{self.max_pages}")
        else:
            embed.set_footer(text=f"Showing {start+1}–{end} of {len(self.listings)}")
        return embed

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: Button):
        self.page = (self.page - 1) % self.max_pages
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        self.page = (self.page + 1) % self.max_pages
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

class MarketAddConfirmView(View):
    def __init__(self, user_id, username, order_number, pokemon, price, timeout=180):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.username = username
        self.order_number = order_number
        self.pokemon = pokemon
        self.price = price
        self.processed = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
        if self.processed:
            return await interaction.response.send_message("Already processed.", ephemeral=True)
        self.processed = True

        collection = load_collection()
        user_id_str = str(self.user_id)
        trainer = collection.get(user_id_str)

        if not trainer:
            return await interaction.response.edit_message(content="Trainer data not found.", view=None)

        if trainer.get("selected_pokemon") == self.order_number:
            return await interaction.response.edit_message(
                content="You cannot list your selected Pokémon in the market.", view=None
            )

        poke = get_pokemon_by_order(trainer, self.order_number)
        if not poke or poke.get("name", "").lower() != self.pokemon.get("name", "").lower():
            return await interaction.response.edit_message(content=f"Pokémon #{self.order_number} no longer found.", view=None)

        removed = remove_pokemon_by_order(trainer, self.order_number)
        save_collection(collection)

        market_data = load_market()
        market_id = len(market_data["listings"]) + 1
        listing = {
            "market_id": market_id,
            "seller": self.username,
            "seller_id": user_id_str,
            "price": self.price,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "active",
            "pokemon": removed
        }
        market_data["listings"].append(listing)

        if not save_market(market_data):
            trainer["pokemon"].insert(self.order_number - 1, removed)
            save_collection(collection)
            return await interaction.response.edit_message(content="Failed to save market listing.", view=None)

        poke_name = removed.get("name", "Unknown").title()
        level = removed.get("level", 1)
        gender = format_gender(removed.get("gender", ""))
        iv = removed.get("stats", {}).get("total_iv_percent", 0)

        await interaction.response.edit_message(view=None)
        await interaction.channel.send(
            f"Listed your **Level {level} {poke_name}{gender} ({iv}%) No. {self.order_number}** "
            f"on the market for **{self.price:,}** Pokécoins (Listing #{market_id})."
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
        await interaction.response.edit_message(content="Aborted.", view=None)

class MarketRemoveConfirmView(View):
    def __init__(self, user_id, username, listing, timeout=180):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.username = username
        self.listing = listing
        self.processed = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
        if self.processed:
            return await interaction.response.send_message("Already processed.", ephemeral=True)
        self.processed = True

        market_data = load_market()
        mid = self.listing["market_id"]
        market_data["listings"] = [l for l in market_data["listings"] if l["market_id"] != mid]
        save_market(market_data)

        collection = load_collection()
        user_id_str = str(self.user_id)
        trainer = collection.get(user_id_str)
        if trainer:
            add_pokemon_to_collection(trainer, self.listing["pokemon"])
            save_collection(collection)

        poke = self.listing["pokemon"]
        poke_name = poke.get("name", "Unknown").title()
        level = poke.get("level", 1)
        gender = format_gender(poke.get("gender", ""))
        iv = poke.get("stats", {}).get("total_iv_percent", 0)

        await interaction.response.edit_message(view=None)
        await interaction.channel.send(
            f"Removed your **Level {level} {poke_name}{gender} ({iv}%)** from the market."
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
        await interaction.response.edit_message(content="Aborted.", view=None)

class MarketEditPriceConfirmView(View):
    def __init__(self, user_id, listing, old_price, new_price, timeout=180):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.listing = listing
        self.old_price = old_price
        self.new_price = new_price
        self.processed = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
        if self.processed:
            return await interaction.response.send_message("Already processed.", ephemeral=True)
        self.processed = True

        market_data = load_market()
        new_id = len(market_data["listings"]) + 1

        for l in market_data["listings"]:
            if l["market_id"] == self.listing["market_id"]:
                l["price"] = self.new_price
                l["market_id"] = new_id
                l["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break

        save_market(market_data)

        poke = self.listing.get("pokemon", {})
        poke_name = poke.get("name", "Unknown").title()
        level = poke.get("level", 1)
        gender = format_gender(poke.get("gender", ""))
        iv = poke.get("stats", {}).get("total_iv_percent", 0)

        await interaction.response.edit_message(view=None)
        await interaction.channel.send(
            f"Edited price of your **Level {level} {poke_name}{gender} ({iv}%)** "
            f"from {self.old_price:,} to **{self.new_price:,}** Pokécoins (New ID: #{new_id})."
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
        await interaction.response.edit_message(content="Aborted.", view=None)

class MarketBuyConfirmView(View):
    def __init__(self, buyer_id, listing, timeout=60):
        super().__init__(timeout=timeout)
        self.buyer_id = buyer_id
        self.listing = listing
        self.processed = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.buyer_id:
            return await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
        if self.processed:
            return await interaction.response.send_message("Already processed.", ephemeral=True)
        self.processed = True

        market_data = load_market()
        mid = self.listing["market_id"]

        found = next((l for l in market_data["listings"] if l["market_id"] == mid), None)
        if not found:
            return await interaction.response.edit_message(content="This listing is no longer available.", view=None)

        inv_data = load_inventory()
        buyer_inv = inv_data.get(str(self.buyer_id), {})
        buyer_coins = buyer_inv.get("pokecoins", 0)

        if buyer_coins < found["price"]:
            return await interaction.response.edit_message(
                content=f"You don't have enough Pokécoins! Need **{found['price']:,}** but have **{buyer_coins:,}**.",
                view=None
            )

        buyer_inv["pokecoins"] = buyer_coins - found["price"]
        inv_data[str(self.buyer_id)] = buyer_inv
        save_inventory(inv_data)

        collection = load_collection()
        buyer_data = collection.get(str(self.buyer_id))
        if not buyer_data:
            return await interaction.response.edit_message(content="Buyer's trainer data not found.", view=None)

        add_pokemon_to_collection(buyer_data, found["pokemon"])
        save_collection(collection)

        market_data["listings"] = [l for l in market_data["listings"] if l["market_id"] != mid]
        save_market(market_data)

        poke = found["pokemon"]
        poke_name = poke.get("name", "Unknown").title()
        level = poke.get("level", 1)
        gender = format_gender(poke.get("gender", ""))
        iv = poke.get("stats", {}).get("total_iv_percent", 0)

        await interaction.response.edit_message(view=None)
        await interaction.channel.send(
            f"<@{self.buyer_id}> You purchased **Level {level} {poke_name}{gender} ({iv}%)** "
            f"from the market (Listing #{mid}) for **{found['price']:,}** Pokécoins!"
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.buyer_id:
            return await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
        await interaction.response.edit_message(content="Aborted.", view=None)

class Market(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="market", invoke_without_command=True)
    async def market(self, ctx):
        """Browse the marketplace"""
        market_data = load_market()
        active = [l for l in market_data["listings"] if l.get("status", "active") == "active"]
        view = MarketplacePagination(active)
        await ctx.send(embed=view.create_embed(), view=view)

    @market.command(name="add")
    async def market_add(self, ctx, order_number: int = None, price: int = None):
        """List a Pokémon on the marketplace"""
        if not await check_registration(ctx):
            return

        if order_number is None or price is None:
            return await ctx.send(
                "Usage: `@Pokékiro market add <order_number> <price>`\n"
                "Example: `@Pokékiro market add 3 5000`"
            )

        if price <= 0:
            return await ctx.send("Price must be a positive number.")

        collection = load_collection()
        trainer = collection.get(str(ctx.author.id))
        if not trainer:
            return await ctx.send("Trainer data not found.")

        selected_no = trainer.get("selected_pokemon")
        if selected_no == order_number:
            return await ctx.send("You cannot list your selected Pokémon in the market.")

        pokemon = get_pokemon_by_order(trainer, order_number)
        if not pokemon:
            total = len(trainer.get("pokemon", []))
            return await ctx.send(
                f"You don't have a Pokémon at position #{order_number}. "
                f"You have {total} Pokémon."
            )

        name = pokemon.get("name", "Unknown").title()
        level = pokemon.get("level", 1)
        gender = format_gender(pokemon.get("gender", ""))
        iv = pokemon.get("stats", {}).get("total_iv_percent", 0)

        confirm_text = (
            f"Are you sure you want to list your **Level {level} {name}{gender} ({iv}%) No. {order_number}** "
            f"for **{price:,}** Pokécoins?"
        )
        view = MarketAddConfirmView(ctx.author.id, ctx.author.name, order_number, pokemon, price)
        await ctx.reply(confirm_text, view=view)

    @market.command(name="remove")
    async def market_remove(self, ctx, market_id: int = None):
        """Remove your Pokémon listing from the marketplace"""
        if not await check_registration(ctx):
            return

        if market_id is None:
            return await ctx.send(
                "Usage: `@Pokékiro market remove <market_id>`\n"
                "Example: `@Pokékiro market remove 5`"
            )

        market_data = load_market()
        listing = next((l for l in market_data["listings"] if l["market_id"] == market_id), None)

        if not listing:
            return await ctx.send(f"Listing #{market_id} not found.")

        if listing.get("seller_id") != str(ctx.author.id) and listing.get("seller") != ctx.author.display_name:
            return await ctx.send("You can only remove your own listings!")

        poke = listing["pokemon"]
        name = poke.get("name", "Unknown").title()
        level = poke.get("level", 1)
        gender = format_gender(poke.get("gender", ""))
        iv = poke.get("stats", {}).get("total_iv_percent", 0)

        confirm_text = (
            f"Are you sure you want to remove your **Level {level} {name}{gender} ({iv}%)** "
            f"from the market?"
        )
        view = MarketRemoveConfirmView(ctx.author.id, ctx.author.name, listing)
        await ctx.reply(confirm_text, view=view)

    @market.group(name="edit", invoke_without_command=True)
    async def market_edit(self, ctx):
        await ctx.send("Usage: `@Pokékiro market edit price <market_id> <new_price>`")

    @market_edit.command(name="price")
    async def market_edit_price(self, ctx, market_id: int = None, new_price: int = None):
        """Edit the price of your market listing"""
        if not await check_registration(ctx):
            return

        if market_id is None or new_price is None:
            return await ctx.send(
                "Usage: `@Pokékiro market edit price <market_id> <new_price>`\n"
                "Example: `@Pokékiro market edit price 5 2000`"
            )

        if new_price <= 0:
            return await ctx.send("Price must be greater than 0.")

        market_data = load_market()
        listing = next((l for l in market_data["listings"] if l["market_id"] == market_id), None)

        if not listing:
            return await ctx.send(f"Listing #{market_id} not found.")

        if listing.get("seller_id") != str(ctx.author.id) and listing.get("seller") != ctx.author.display_name:
            return await ctx.send("You can only edit your own listings!")

        old_price = listing["price"]
        if old_price == new_price:
            return await ctx.send("New price is the same as the current price.")

        poke = listing.get("pokemon", {})
        name = poke.get("name", "Unknown").title()
        level = poke.get("level", 1)
        gender = format_gender(poke.get("gender", ""))
        iv = poke.get("stats", {}).get("total_iv_percent", 0)

        confirm_text = (
            f"Are you sure you want to change the price of your **Level {level} {name}{gender} ({iv}%)** "
            f"from **{old_price:,}** to **{new_price:,}** Pokécoins? This will change the listing ID."
        )
        view = MarketEditPriceConfirmView(ctx.author.id, listing, old_price, new_price)
        await ctx.reply(confirm_text, view=view)

    @market.command(name="buy")
    async def market_buy(self, ctx, market_id: int = None):
        """Buy a Pokémon from the marketplace"""
        if not await check_registration(ctx):
            return

        if market_id is None:
            return await ctx.send(
                "Usage: `@Pokékiro market buy <market_id>`\n"
                "Example: `@Pokékiro market buy 5`"
            )

        market_data = load_market()
        listing = next((l for l in market_data["listings"] if l["market_id"] == market_id and l.get("status", "active") == "active"), None)

        if not listing:
            return await ctx.send(f"Listing #{market_id} not found or no longer available.")

        if listing.get("seller_id") == str(ctx.author.id):
            return await ctx.send("You cannot buy your own listing!")

        inv_data = load_inventory()
        buyer_coins = inv_data.get(str(ctx.author.id), {}).get("pokecoins", 0)

        poke = listing["pokemon"]
        name = poke.get("name", "Unknown").title()
        level = poke.get("level", 1)
        gender = format_gender(poke.get("gender", ""))
        iv = poke.get("stats", {}).get("total_iv_percent", 0)
        price = listing["price"]

        confirm_text = (
            f"Are you sure you want to buy **Level {level} {name}{gender} ({iv}%)** "
            f"for **{price:,}** Pokécoins?\n"
            f"Your balance: **{buyer_coins:,}** Pokécoins"
        )
        view = MarketBuyConfirmView(ctx.author.id, listing)
        await ctx.reply(confirm_text, view=view)

    @market.command(name="info")
    async def market_info(self, ctx, market_id: int = None):
        """View details of a specific market listing"""
        if market_id is None:
            return await ctx.send("Usage: `@Pokékiro market info <market_id>`")

        market_data = load_market()
        listing = next((l for l in market_data["listings"] if l["market_id"] == market_id), None)

        if not listing:
            return await ctx.send(f"Listing #{market_id} not found.")

        poke = listing["pokemon"]
        name = poke.get("name", "Unknown").title()
        level = poke.get("level", 1)
        gender = format_gender(poke.get("gender", ""))
        nature = poke.get("nature", "Unknown")
        stats = poke.get("stats", {})
        total_iv = stats.get("total_iv_percent", 0)
        seller_id = listing.get("seller_id", None)

        xp_raw = poke.get("xp", "0/0")
        xp_needed = level * 50 if level < 100 else 5000
        if level >= 100:
            xp_display = "Max"
        elif isinstance(xp_raw, str) and "/" in xp_raw:
            xp_display = xp_raw
        else:
            xp_display = f"{xp_raw}/{xp_needed}"

        moves = poke.get("current_moves", poke.get("moves", []))
        move_lines = ""
        for i in range(4):
            if i < len(moves) and moves[i]:
                move_lines += f"{moves[i].replace('-', ' ').title()}\n"
            else:
                move_lines += "None\n"
        move_lines = move_lines.strip()

        shiny_prefix = f"{UI_EMOJIS['spark']} " if poke.get("shiny", False) else ""
        embed = discord.Embed(
            title=f"{shiny_prefix}Level {level} {name}",
            color=0xFFD700
        )

        try:
            if seller_id:
                seller_user = await self.bot.fetch_user(int(seller_id))
                embed.set_author(name=seller_user.name, icon_url=seller_user.display_avatar.url)
        except Exception:
            embed.set_author(name=listing.get("seller", "Unknown"))

        embed.add_field(
            name="Details",
            value=(
                f"**XP:** {xp_display}\n"
                f"**Nature:** {nature}\n"
                f"**Gender:** {gender}"
            ),
            inline=False
        )

        embed.add_field(
            name="Stats",
            value=(
                f"**HP:** {stats.get('hp', 0)} – IV: {stats.get('hp_iv', 0)}/31\n"
                f"**Attack:** {stats.get('attack', 0)} – IV: {stats.get('attack_iv', 0)}/31\n"
                f"**Defense:** {stats.get('defense', 0)} – IV: {stats.get('defense_iv', 0)}/31\n"
                f"**Sp. Atk:** {stats.get('special_attack', 0)} – IV: {stats.get('special_attack_iv', 0)}/31\n"
                f"**Sp. Def:** {stats.get('special_defense', 0)} – IV: {stats.get('special_defense_iv', 0)}/31\n"
                f"**Speed:** {stats.get('speed', 0)} – IV: {stats.get('speed_iv', 0)}/31\n"
                f"**Total IV:** {total_iv}%"
            ),
            inline=False
        )

        embed.add_field(name="Current Moves", value=move_lines, inline=False)

        embed.add_field(
            name="Market Listing",
            value=(
                f"**ID:** {market_id}\n"
                f"**Price:** {listing['price']:,} pc"
            ),
            inline=False
        )

        from database.pokemons_database import pokemons as pokedex
        artwork_file = None
        shiny_artwork_file = None
        for db_p in pokedex:
            if db_p["name"].lower() == name.lower():
                artwork_file = db_p.get("artwork")
                shiny_artwork_file = db_p.get("shiny_artwork")
                break

        is_shiny = poke.get("shiny", False)
        if is_shiny and shiny_artwork_file:
            embed.set_image(url=get_artwork_url(shiny_artwork_file, shiny=True))
        elif artwork_file:
            embed.set_image(url=get_artwork_url(artwork_file))

        await ctx.send(embed=embed)

    @market.command(name="mylistings")
    async def market_mylistings(self, ctx):
        """View your own market listings"""
        if not await check_registration(ctx):
            return

        market_data = load_market()
        my_listings = [
            l for l in market_data["listings"]
            if l.get("seller_id") == str(ctx.author.id) or l.get("seller") == ctx.author.name
        ]

        if not my_listings:
            return await ctx.send("You have no active listings on the market.")

        view = MarketplacePagination(my_listings)

        lines = []
        for listing in my_listings[:view.per_page]:
            poke = listing.get("pokemon", {})
            name = poke.get("name", "Unknown").title()
            level = poke.get("level", 1)
            gender = format_gender(poke.get("gender", ""))
            iv = poke.get("stats", {}).get("total_iv_percent", 0)
            price = listing.get("price", 0)
            mid = listing.get("market_id", "?")
            shiny_prefix = f"{UI_EMOJIS['spark']} " if poke.get("shiny", False) else ""
            lines.append(f"`{mid}`    {shiny_prefix}**{name}** {gender}    •    Lvl. {level}    •    {iv}%    •    {price:,}")
        end = min(view.per_page, total)
        embed = discord.Embed(title="Your Market Listings", color=0xFFD700)
        embed.description = "\n".join(lines)
        if view.max_pages > 1:
            embed.set_footer(text=f"Showing 1\u2013{end} of {total} | Page 1/{view.max_pages}")
        else:
            embed.set_footer(text=f"Showing 1\u2013{end} of {total}")

        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Market(bot))
