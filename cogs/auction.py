import discord
from discord.ui import View, Button
from discord.ext import commands
import json
import os
import math
import asyncio
from datetime import datetime, timedelta

from utils.registered_checker import check_registration
from utils.constants import GENDER_EMOJIS, UI_EMOJIS
from database.pokemons_database import pokemons
from utils.artwork_handler import get_artwork_url



COLLECTION_FILE = "data/trainers_collection_database.json"
INVENTORY_FILE  = "data/trainers_inventory_database.json"
AUCTION_DB_FILE = "data/auction_database.json"

def load_collection():
    try:
        with open(COLLECTION_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_collection(data):
    with open(COLLECTION_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_inventory():
    try:
        with open(INVENTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_inventory(data):
    with open(INVENTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_auctions():
    try:
        if os.path.exists(AUCTION_DB_FILE):
            with open(AUCTION_DB_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {"listings": []}

def save_auctions(data):
    os.makedirs("data", exist_ok=True)
    try:
        with open(AUCTION_DB_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving auctions: {e}")
        return False

def format_gender(gender):
    """Return gender emoji for display, given text gender."""
    g = str(gender).lower().strip()
    if g == "male":
        return GENDER_EMOJIS["male"]
    elif g == "female":
        return GENDER_EMOJIS["female"]
    else:
        return GENDER_EMOJIS["unknown"]

def format_duration(minutes):
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    rem   = minutes % 60
    return f"{hours}h {rem}m" if rem else f"{hours}h"

def calculate_time_remaining(end_time_str):
    try:
        end  = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
        diff = end - datetime.now()
        if diff.total_seconds() <= 0:
            return "Ended"
        return format_duration(int(diff.total_seconds() / 60))
    except:
        return "Unknown"

def get_end_time(listing):
    """Helper: get end time string from listing date dict."""
    return listing.get("date", {}).get("end", "")

def get_pokemon_iv(poke):
    return poke.get("stats", {}).get("total_iv_percent", 0)

def get_pokemon_by_order(trainer_data, order_number):
    """Return pokemon dict at position `order_number` (1-indexed)."""
    pokemon_list = trainer_data.get("pokemon", [])
    if 1 <= order_number <= len(pokemon_list):
        return pokemon_list[order_number - 1]
    return None

async def check_expired_auctions(bot):
    """Process expired auctions: give pokemon to winner or return to seller."""
    auction_data = load_auctions()
    now = datetime.now()
    changed = False

    for listing in auction_data.get("listings", []):
        if listing.get("status") != "active":
            continue
        try:
            end_time = datetime.strptime(get_end_time(listing), "%Y-%m-%d %H:%M:%S")
        except:
            continue

        if now < end_time:
            continue

        listing["status"] = "inactive"
        changed = True

        winner_id   = listing.get("auction_winner")
        seller_id   = listing.get("seller")
        pokemon     = listing.get("pokemon", {})

        coll = load_collection()

        if winner_id is None:
            if seller_id and str(seller_id) in coll:
                coll[str(seller_id)].setdefault("pokemon", []).append(pokemon)
                save_collection(coll)
        else:
            if str(winner_id) in coll:
                coll[str(winner_id)].setdefault("pokemon", []).append(pokemon)
                save_collection(coll)

            winning_bid = listing.get("winning_bid", 0)
            if seller_id and winning_bid > 0:
                inv = load_inventory()
                if str(seller_id) in inv:
                    inv[str(seller_id)]["pokecoins"] = inv[str(seller_id)].get("pokecoins", 0) + winning_bid
                    save_inventory(inv)

    if changed:
        save_auctions(auction_data)

class AuctionPagination(View):
    def __init__(self, listings, page=0, per_page=20, timeout=300):
        super().__init__(timeout=timeout)
        self.listings  = listings
        self.page      = page
        self.per_page  = per_page
        self.max_pages = max(1, math.ceil(len(listings) / per_page))

    def get_page_listings(self):
        start = self.page * self.per_page
        return self.listings[start:start + self.per_page]

    def create_embed(self):
        embed = discord.Embed(
            title="Auctions in Pokékiro Community",
            color=0xFFD700
        )

        if not self.listings:
            embed.description = "No Pokémon available in the auction house."
            return embed

        lines = []
        for listing in self.get_page_listings():
            poke          = listing.get("pokemon", {})
            name          = poke.get("name", "Unknown").title()
            level         = poke.get("level", 1)
            gender        = poke.get("gender", "unknown")
            gender_emoji  = format_gender(gender)
            iv            = poke.get("stats", {}).get("total_iv_percent", 0)
            winning_bid   = listing.get("winning_bid", listing.get("starting_bid", 0))
            bid_increment = listing.get("bid_increment", 0)
            time_left     = calculate_time_remaining(get_end_time(listing))
            bids_and_bidders = listing.get("bids_and_bidders", [])
            bid_display      = "No bids" if not bids_and_bidders else f"{len(bids_and_bidders)} bids"
            status        = listing.get("status", "active")
            status_emoji  = "🟢" if status == "active" else "🔴"

            shiny_prefix = f"{UI_EMOJIS['spark']} " if poke.get("shiny", False) else ""
            lines.append(
                f"`{listing['auction_id']}`　{shiny_prefix}**{name}**{gender_emoji}　•　Lvl. {level}　•　"
                f"{iv}%　•　CB: {winning_bid:,}　•　{time_left}"
            )

        embed.description = "\n".join(lines) if lines else "No active auctions."

        start = self.page * self.per_page
        end   = min(start + self.per_page, len(self.listings))
        if self.max_pages > 1:
            embed.set_footer(text=f"Showing {start+1}–{end} of {len(self.listings)}. Page {self.page+1} of {self.max_pages}.")
        else:
            embed.set_footer(text=f"Showing {start+1}–{end} of {len(self.listings)}.")

        return embed

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: Button):
        self.page = (self.page - 1) % self.max_pages
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        self.page = (self.page + 1) % self.max_pages
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

class AuctionConfirmationView(View):
    def __init__(self, user_id, order_number, pokemon, duration, starting_bid, bid_increment, timeout=180):
        super().__init__(timeout=timeout)
        self.user_id       = user_id
        self.order_number  = order_number
        self.pokemon       = pokemon
        self.duration      = duration
        self.starting_bid  = starting_bid
        self.bid_increment = bid_increment
        self.processed     = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
        if self.processed:
            return await interaction.response.send_message("Already processed.", ephemeral=True)
        self.processed = True

        coll = load_collection()
        user_id_str = str(self.user_id)

        if user_id_str not in coll:
            return await interaction.response.edit_message(content="Could not load your data.", view=None)

        trainer = coll[user_id_str]
        pokemon_list = trainer.get("pokemon", [])

        if self.order_number < 1 or self.order_number > len(pokemon_list):
            return await interaction.response.edit_message(
                content=f"Pokémon #{self.order_number} no longer exists.", view=None
            )

        poke = pokemon_list[self.order_number - 1]

        auction_data = load_auctions()
        auction_id   = len(auction_data["listings"]) + 1
        end_time     = datetime.now() + timedelta(minutes=self.duration)

        listing = {
            "auction_id":       auction_id,
            "seller":           user_id_str,
            "auction_winner":   None,
            "bids_and_bidders": [],
            "starting_bid":     self.starting_bid,
            "winning_bid":      self.starting_bid,
            "bid_increment":    self.bid_increment,
            "status":           "active",
            "date": {
                "start": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "end":   end_time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "pokemon":          poke
        }

        auction_data["listings"].append(listing)
        if not save_auctions(auction_data):
            return await interaction.response.edit_message(content="Failed to create auction.", view=None)

        trainer["pokemon"].pop(self.order_number - 1)
        coll[user_id_str] = trainer
        save_collection(coll)

        name   = poke.get("name", "Unknown").title()
        level  = poke.get("level", 1)
        iv     = poke.get("stats", {}).get("total_iv_percent", 0)
        gender_emoji = format_gender(poke.get("gender", "unknown"))

        await interaction.response.edit_message(view=None)
        await interaction.channel.send(
            f"Auctioning your **Level {level} {name}{gender_emoji} ({iv}%) No. {self.order_number}** "
            f"(Auction #{auction_id})."
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your confirmation.", ephemeral=True)
        await interaction.response.edit_message(content="Aborted.", view=None)

def build_auction_info_embed(auction, bot_user=None):
    poke   = auction.get("pokemon", {})
    name   = poke.get("name", "Unknown").title()
    level  = poke.get("level", 1)
    gender = poke.get("gender", "unknown")
    gender_emoji = format_gender(gender)
    iv     = poke.get("stats", {}).get("total_iv_percent", 0)
    stats  = poke.get("stats", {})

    shiny_prefix = f"{UI_EMOJIS['spark']} " if poke.get("shiny", False) else ""
    embed = discord.Embed(
        title=f"Auction #{auction['auction_id']} • {shiny_prefix}Level {level} {name}",
        color=0xFFD700
    )

    xp_str  = poke.get("xp", "0/50")
    nature  = poke.get("nature", "Unknown").title()
    ability = poke.get("ability", "Unknown")

    embed.add_field(
        name="Pokémon Details",
        value=(
            f"**XP:** {xp_str}\n"
            f"**Nature:** {nature}\n"
            f"**Ability:** {ability}\n"
            f"**Gender:** {gender_emoji}"
        ),
        inline=False
    )

    stat_map = [
        ("hp",               "HP"),
        ("attack",           "Attack"),
        ("defense",          "Defense"),
        ("special_attack",   "Sp. Atk"),
        ("special_defense",  "Sp. Def"),
        ("speed",            "Speed"),
    ]
    stats_lines = ""
    for key, label in stat_map:
        val = stats.get(key, 0)
        iv_val = stats.get(f"{key}_iv", 0)
        stats_lines += f"**{label}:** {val} – IV: {iv_val}/31\n"
    stats_lines += f"**Total IV:** {iv}%"
    embed.add_field(name="Stats", value=stats_lines, inline=False)

    winning_bid   = auction.get("winning_bid", auction.get("starting_bid", 0))
    bid_increment = auction.get("bid_increment", 0)
    winner_id     = auction.get("auction_winner")
    bidder_display = f"<@{winner_id}>" if winner_id else "None"

    end_time_str = get_end_time(auction)
    time_left = calculate_time_remaining(end_time_str)
    try:
        end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
        end_fmt = end_dt.strftime("%I:%M %p")
    except:
        end_fmt = "Unknown"

    embed.add_field(
        name="Auction Details",
        value=(
            f"**Winning Bid:** {winning_bid:,} Pokécoins\n"
            f"**Bidder:** {bidder_display}\n"
            f"**Bid Increment:** {bid_increment:,} Pokécoins\n\n"
            f"Bid with `@Pokékiro auction bid {auction['auction_id']} <bid>`\n"
            f"Ends in {time_left} at | Today at {end_fmt}"
        ),
        inline=False
    )

    artwork_file = None
    shiny_artwork_file = None
    for db_p in pokemons:
        if db_p["name"].lower() == poke.get("name", "").lower():
            artwork_file = db_p.get("artwork")
            shiny_artwork_file = db_p.get("shiny_artwork")
            break

    is_shiny = poke.get("shiny", False)
    if is_shiny and shiny_artwork_file:
        embed.set_image(url=get_artwork_url(shiny_artwork_file, shiny=True))
    elif artwork_file:
        embed.set_image(url=get_artwork_url(artwork_file))

    return embed

class Auction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def setup_hook(self):
        """Setup hook called when cog is loaded."""
        self.bot.loop.create_task(self._auction_check_loop())

    async def _auction_check_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await check_expired_auctions(self.bot)
            except Exception as e:
                print(f"Auction check error: {e}")
            await asyncio.sleep(300)

    @commands.group(name="auction", invoke_without_command=True)
    async def auction_root(self, ctx):
        """Show all active auctions."""
        auction_data = load_auctions()
        active = [
            l for l in auction_data.get("listings", [])
            if calculate_time_remaining(get_end_time(l)) != "Ended"
        ]
        view  = AuctionPagination(active)
        embed = view.create_embed()
        await ctx.send(embed=embed, view=view)

    @auction_root.command(name="start")
    async def auction_start(self, ctx, order_number: int = None, duration: int = None,
                            starting_bid: int = None, bid_increment: int = None):
        """Start an auction.
        Usage: auction start <order_number> <duration_minutes> <starting_bid> <bid_increment>"""
        if not await check_registration(ctx):
            return

        if None in (order_number, duration, starting_bid, bid_increment):
            return await ctx.reply(
                "Usage: `auction start <order_number> <duration_minutes> <starting_bid> <bid_increment>`\n"
                "Example: `auction start 1 300 1000 100` (5 hours = 300 minutes)"
            )

        if duration <= 0:
            return await ctx.reply("Duration must be a positive number (in minutes).")
        if starting_bid <= 0 or bid_increment <= 0:
            return await ctx.reply("Starting bid and bid increment must be positive numbers.")

        coll = load_collection()
        user_id_str = str(ctx.author.id)
        trainer = coll.get(user_id_str)
        if not trainer:
            return await ctx.reply("Could not load your trainer data.")

        poke = get_pokemon_by_order(trainer, order_number)
        if not poke:
            total = len(trainer.get("pokemon", []))
            return await ctx.reply(
                f"You don't have a Pokémon at position #{order_number}.\n"
                f"You have {total} Pokémon. Use `@Pokékiro pokémons` to see your collection."
            )

        selected_idx = trainer.get("selected_pokemon", 1)
        if order_number == selected_idx:
            return await ctx.reply("You cannot auction your currently selected Pokémon!")

        name   = poke.get("name", "Unknown").title()
        level  = poke.get("level", 1)
        iv     = poke.get("stats", {}).get("total_iv_percent", 0)
        gender_emoji = format_gender(poke.get("gender", "unknown"))

        hours = duration // 60
        mins  = duration % 60
        dur_text = ""
        if hours:
            dur_text = f"{hours}h"
            if mins:
                dur_text += f" {mins}m"
        else:
            dur_text = f"{mins}m"

        confirmation_text = (
            f"**Auction Confirmation**\n"
            f"You are auctioning your Level {level} **{name}**{gender_emoji} "
            f"({iv}%) No. {order_number}:\n"
            f"**Starting Bid:** {starting_bid:,} Pokécoins\n"
            f"**Bid Increment:** {bid_increment:,} Pokécoins\n"
            f"**Duration:** {dur_text}\n"
            f"Auctions are server-specific and cannot be canceled.\n"
            f"Are you sure?"
        )

        view = AuctionConfirmationView(
            ctx.author.id, order_number, poke,
            duration, starting_bid, bid_increment
        )
        await ctx.reply(confirmation_text, view=view)

    @auction_root.command(name="bid")
    async def auction_bid(self, ctx, auction_id: int = None, bid_amount: int = None):
        """Place a bid on an auction.
        Usage: auction bid <auction_id> <bid_amount>"""
        if not await check_registration(ctx):
            return

        if auction_id is None or bid_amount is None:
            return await ctx.reply(
                "Usage: `auction bid <auction_id> <bid_amount>`\n"
                "Example: `auction bid 1 500`"
            )

        auction_data = load_auctions()
        auction = next(
            (l for l in auction_data.get("listings", []) if l.get("auction_id") == auction_id),
            None
        )

        if not auction:
            return await ctx.reply(f"Auction #{auction_id} not found.")

        if calculate_time_remaining(get_end_time(auction)) == "Ended":
            return await ctx.reply(f"Auction #{auction_id} has already ended.")

        user_id_str = str(ctx.author.id)

        if user_id_str == str(auction.get("seller")):
            return await ctx.reply("You cannot bid on your own auction!")

        winning_bid   = auction.get("winning_bid", 0)
        bid_increment = auction.get("bid_increment", 0)
        minimum_bid   = winning_bid + bid_increment

        if bid_amount < minimum_bid:
            return await ctx.reply(
                f"Your bid must be at least **{minimum_bid:,} Pokécoins** "
                f"(Winning: {winning_bid:,} + Increment: {bid_increment:,})."
            )

        inv = load_inventory()
        if user_id_str not in inv:
            return await ctx.reply("Could not load your inventory data.")

        user_coins = inv[user_id_str].get("pokecoins", 0)
        if user_coins < bid_amount:
            return await ctx.reply(
                f"You don't have enough Pokécoins! "
                f"You have **{user_coins:,}** but need **{bid_amount:,}**."
            )

        inv[user_id_str]["pokecoins"] = user_coins - bid_amount
        save_inventory(inv)

        prev_winner_id  = auction.get("auction_winner")
        prev_bid        = auction.get("winning_bid", 0)

        auction["winning_bid"]    = bid_amount
        auction["auction_winner"] = user_id_str

        auction.setdefault("bids_and_bidders", []).append({
            "amount": bid_amount,
            "bidder": user_id_str
        })

        if not save_auctions(auction_data):
            inv[user_id_str]["pokecoins"] = user_coins
            save_inventory(inv)
            return await ctx.reply("Failed to save auction. Your bid has been refunded.")

        if prev_winner_id and prev_winner_id != user_id_str:
            inv = load_inventory()
            if str(prev_winner_id) in inv:
                inv[str(prev_winner_id)]["pokecoins"] = inv[str(prev_winner_id)].get("pokecoins", 0) + prev_bid
                save_inventory(inv)

            try:
                prev_user = await self.bot.fetch_user(int(prev_winner_id))
                poke = auction.get("pokemon", {})
                name  = poke.get("name", "Unknown").title()
                level = poke.get("level", 1)
                iv    = poke.get("stats", {}).get("total_iv_percent", 0)
                gender_emoji = format_gender(poke.get("gender", "unknown"))

                await prev_user.send(
                    f"You have been outbid on the **Level {level} {name}{gender_emoji} ({iv}%)** "
                    f"(Auction #{auction_id}). Your bid of {prev_bid:,} Pokécoins has been refunded. "
                    f"New bid: **{bid_amount:,}** Pokécoins."
                )
            except Exception as e:
                print(f"Failed to DM previous bidder: {e}")

        poke = auction.get("pokemon", {})
        name  = poke.get("name", "Unknown").title()
        level = poke.get("level", 1)
        iv    = poke.get("stats", {}).get("total_iv_percent", 0)
        gender_emoji = format_gender(poke.get("gender", "unknown"))

        await ctx.reply(
            f"✅ Bid placed successfully!\n"
            f"**Auction #{auction_id}:** Level {level} {name}{gender_emoji} ({iv}%)\n"
            f"**Current Bid:** {bid_amount:,} Pokécoins (Deducted)\n"
            f"**Bidder:** {ctx.author.display_name}"
        )

    @auction_root.command(name="info")
    async def auction_info(self, ctx, auction_id: int = None):
        """Get detailed info about a specific auction.
        Usage: auction info <auction_id>"""
        if not await check_registration(ctx):
            return

        if auction_id is None:
            return await ctx.reply("Usage: `@Pokékiro auction info <auction_id>`")

        auction_data = load_auctions()
        auction = next(
            (l for l in auction_data.get("listings", []) if l.get("auction_id") == auction_id),
            None
        )

        if not auction:
            return await ctx.reply(f"Auction #{auction_id} not found.")

        if calculate_time_remaining(get_end_time(auction)) == "Ended":
            return await ctx.reply(f"Auction #{auction_id} has already ended.")

        embed = build_auction_info_embed(auction, self.bot.user)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Auction(bot))
