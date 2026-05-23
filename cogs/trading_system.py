import discord
import json
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
    GENDER_EMOJIS,
    UI_EMOJIS,
)
from utils.registered_checker import check_registration

DATA_FILE = "data/trainers_collection_database.json"
INVENTORY_FILE = "data/trainers_inventory_database.json"

ALL_ITEM_EMOJIS = {
    **XP_BOOSTERS_AND_CANDIES_EMOJIS,
    **EVOLUTION_ITEMS_EMOJIS,
    **FORM_CHANGING_ITEMS_EMOJIS,
    **HELD_ITEMS_EMOJIS,
    **NATURE_MINTS_EMOJIS,
    **HUNTING_ITEMS_EMOJIS,
    **BATTLE_ITEMS_EMOJIS,
}

POKECOIN_EMOJI = CURRENCY_EXCHANGE_AND_BALANCE.get("pokecoin", "")
SHARD_EMOJI = CURRENCY_EXCHANGE_AND_BALANCE.get("shard", "")
SHINY_EMOJI = UI_EMOJIS.get("spark", "")

active_trades: dict = {}

def load_collection():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_collection(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_inventory():
    with open(INVENTORY_FILE, "r") as f:
        return json.load(f)

def save_inventory(data):
    with open(INVENTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def name_to_key(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")

def get_item_emoji(item_name: str) -> str:
    key = name_to_key(item_name)
    return ALL_ITEM_EMOJIS.get(key, "")

def build_trade_embed(session) -> discord.Embed:
    embed = discord.Embed(
        title=f"Trade between {session.requester.display_name} and {session.accepter.display_name}.",
        color=discord.Color.gold()
    )

    def dot(confirmed):
        return "🟢" if confirmed else "⚪"

    coll = load_collection()

    def format_offer(offer: dict, user_id: str) -> str:
        lines = []
        poke_list = coll.get(user_id, {}).get("pokemon", [])
        for idx in offer.get("pokemon_indices", []):
            if idx >= len(poke_list):
                lines.append(f"`{idx + 1}` *(invalid)*")
                continue
            p = poke_list[idx]
            stats = p.get("stats", {})
            iv = stats.get("total_iv_percent", 0)
            gender_emoji = GENDER_EMOJIS.get(p.get("gender", "").lower(), "")
            shiny_prefix = f"{SHINY_EMOJI} " if p.get("shiny", False) else ""
            lines.append(f"`{idx + 1}`    **{shiny_prefix}{p['name']}** {gender_emoji}    •    Lvl. {p['level']}    •    {iv}%")
        if offer.get("pokecoins", 0) > 0:
            lines.append(f"{offer['pokecoins']} Pokécoins {POKECOIN_EMOJI}")
        if offer.get("shards", 0) > 0:
            lines.append(f"{offer['shards']} Shards {SHARD_EMOJI}")
        for item_name, amount in offer.get("items", {}).items():
            emoji = get_item_emoji(item_name)
            lines.append(f"{amount} {item_name} {emoji}")
        return "\n".join(lines) if lines else "None"

    r_id = str(session.requester.id)
    a_id = str(session.accepter.id)

    r_offer = format_offer(session.offers[r_id], r_id)
    a_offer = format_offer(session.offers[a_id], a_id)

    total_pokemon = (
        len(session.offers[r_id].get("pokemon_indices", [])) +
        len(session.offers[a_id].get("pokemon_indices", []))
    )

    embed.add_field(
        name=f"{dot(session.confirmed[r_id])} {session.requester.display_name}",
        value=r_offer,
        inline=False
    )
    embed.add_field(
        name=f"{dot(session.confirmed[a_id])} {session.accepter.display_name}",
        value=a_offer,
        inline=False
    )
    embed.set_footer(text=f"Showing page 1 out of {total_pokemon}.")
    return embed

class TradeSession:
    def __init__(self, requester: discord.Member, accepter: discord.Member):
        self.requester = requester
        self.accepter = accepter
        self.offers = {
            str(requester.id): {
                "pokemon_indices": [],
                "pokecoins": 0,
                "shards": 0,
                "items": {}
            },
            str(accepter.id): {
                "pokemon_indices": [],
                "pokecoins": 0,
                "shards": 0,
                "items": {}
            }
        }
        self.confirmed = {
            str(requester.id): False,
            str(accepter.id): False
        }
        self.trade_message = None

class TradeRequestView(discord.ui.View):
    def __init__(self, ctx, requester: discord.Member, accepter: discord.Member):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.requester = requester
        self.accepter = accepter

    async def on_timeout(self):
        try:
            await self.message.edit(content="The request to trade has timed out.", view=None)
        except Exception:
            pass
        active_trades.pop(self.ctx.channel.id, None)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.accepter.id:
            return await interaction.response.send_message("This isn't your trade request!", ephemeral=True)

        self.stop()
        await interaction.message.edit(view=None)

        session = TradeSession(self.requester, self.accepter)
        active_trades[self.ctx.channel.id] = session

        trade_view = TradeActiveView(self.ctx, session)
        embed = build_trade_embed(session)
        await interaction.response.send_message(embed=embed, view=trade_view)
        session.trade_message = await interaction.original_response()
        trade_view.message = session.trade_message

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.requester.id, self.accepter.id]:
            return await interaction.response.send_message("This isn't your trade request!", ephemeral=True)

        self.stop()
        await interaction.message.edit(content="Trade request cancelled.", view=None)
        active_trades.pop(self.ctx.channel.id, None)

class TradeActiveView(discord.ui.View):
    def __init__(self, ctx, session: TradeSession):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.session = session
        self.message = None

    async def update_embed(self, interaction: discord.Interaction):
        embed = build_trade_embed(self.session)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        user_id = str(interaction.user.id)

        if interaction.user.id not in [session.requester.id, session.accepter.id]:
            return await interaction.response.send_message("This isn't your trade!", ephemeral=True)

        if session.confirmed[user_id]:
            return await interaction.response.send_message("You have already confirmed!", ephemeral=True)

        session.confirmed[user_id] = True

        if all(session.confirmed.values()):
            self.stop()

            success, error = execute_trade(session)
            if not success:
                await interaction.response.edit_message(embed=build_trade_embed(session), view=self)
                await interaction.followup.send(f"Trade failed: {error}")
                return

            await interaction.response.edit_message(embed=build_trade_embed(session), view=None)
            await interaction.followup.send(
                f"Trade between {session.requester.mention} and {session.accepter.mention} has been successfully completed."
            )
            active_trades.pop(self.ctx.channel.id, None)
        else:
            await self.update_embed(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session

        if interaction.user.id not in [session.requester.id, session.accepter.id]:
            return await interaction.response.send_message("This isn't your trade!", ephemeral=True)

        self.stop()
        await interaction.response.edit_message(embed=build_trade_embed(session), view=None)
        await interaction.followup.send("Trade has been cancelled.")
        active_trades.pop(self.ctx.channel.id, None)

def execute_trade(session: TradeSession):
    try:
        coll = load_collection()
        inv = load_inventory()

        r_id = str(session.requester.id)
        a_id = str(session.accepter.id)

        r_offer = session.offers[r_id]
        a_offer = session.offers[a_id]

        r_inv = inv.get(r_id, {})
        a_inv = inv.get(a_id, {})

        if r_inv.get("pokecoins", 0) < r_offer["pokecoins"]:
            return False, f"{session.requester.display_name} doesn't have enough Pokécoins."
        if r_inv.get("shards", 0) < r_offer["shards"]:
            return False, f"{session.requester.display_name} doesn't have enough Shards."
        if a_inv.get("pokecoins", 0) < a_offer["pokecoins"]:
            return False, f"{session.accepter.display_name} doesn't have enough Pokécoins."
        if a_inv.get("shards", 0) < a_offer["shards"]:
            return False, f"{session.accepter.display_name} doesn't have enough Shards."

        for item_name, amount in r_offer["items"].items():
            if r_inv.get("items", {}).get(item_name, 0) < amount:
                return False, f"{session.requester.display_name} doesn't have enough {item_name}."
        for item_name, amount in a_offer["items"].items():
            if a_inv.get("items", {}).get(item_name, 0) < amount:
                return False, f"{session.accepter.display_name} doesn't have enough {item_name}."

        r_pokemon_list = coll[r_id]["pokemon"]
        a_pokemon_list = coll[a_id]["pokemon"]

        r_giving = sorted(r_offer["pokemon_indices"], reverse=True)
        a_giving = sorted(a_offer["pokemon_indices"], reverse=True)

        r_pokemons_to_give = [r_pokemon_list[i] for i in r_offer["pokemon_indices"]]
        a_pokemons_to_give = [a_pokemon_list[i] for i in a_offer["pokemon_indices"]]

        for i in r_giving:
            r_pokemon_list.pop(i)
        for i in a_giving:
            a_pokemon_list.pop(i)

        r_pokemon_list.extend(a_pokemons_to_give)
        a_pokemon_list.extend(r_pokemons_to_give)

        coll[r_id]["pokemon"] = r_pokemon_list
        coll[a_id]["pokemon"] = a_pokemon_list

        for uid in [r_id, a_id]:
            plist = coll[uid]["pokemon"]
            sel = coll[uid].get("selected_pokemon", 1)
            if sel is None or sel > len(plist):
                coll[uid]["selected_pokemon"] = len(plist) if plist else None

        r_inv["pokecoins"] = r_inv.get("pokecoins", 0) - r_offer["pokecoins"] + a_offer["pokecoins"]
        r_inv["shards"] = r_inv.get("shards", 0) - r_offer["shards"] + a_offer["shards"]
        a_inv["pokecoins"] = a_inv.get("pokecoins", 0) - a_offer["pokecoins"] + r_offer["pokecoins"]
        a_inv["shards"] = a_inv.get("shards", 0) - a_offer["shards"] + r_offer["shards"]

        r_items = r_inv.get("items", {})
        a_items = a_inv.get("items", {})

        for item_name, amount in r_offer["items"].items():
            r_items[item_name] = r_items.get(item_name, 0) - amount
            if r_items[item_name] <= 0:
                del r_items[item_name]
            a_items[item_name] = a_items.get(item_name, 0) + amount

        for item_name, amount in a_offer["items"].items():
            a_items[item_name] = a_items.get(item_name, 0) - amount
            if a_items[item_name] <= 0:
                del a_items[item_name]
            r_items[item_name] = r_items.get(item_name, 0) + amount

        r_inv["items"] = r_items
        a_inv["items"] = a_items
        inv[r_id] = r_inv
        inv[a_id] = a_inv

        save_collection(coll)
        save_inventory(inv)
        return True, None

    except Exception as e:
        return False, str(e)

class TradingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="trade", invoke_without_command=True)
    async def trade(self, ctx, member: discord.Member = None):
        if not await check_registration(ctx):
            return

        if member is None:
            return await ctx.reply("Usage: `@Pokékiro trade <@username>`")

        if member.id == ctx.author.id:
            return await ctx.reply("You can't trade with yourself!")

        if member.bot:
            return await ctx.reply("You can't trade with a bot!")

        if ctx.channel.id in active_trades:
            return await ctx.reply("There is already an active trade in this channel!")

        view = TradeRequestView(ctx, ctx.author, member)
        msg = await ctx.send(
            content=f"Requesting a trade with {member.mention}. Click the accept button to accept!",
            view=view
        )
        view.message = msg

    @trade.command(name="add")
    async def trade_add(self, ctx, *, args: str = None):
        if not await check_registration(ctx):
            return

        if ctx.channel.id not in active_trades:
            return await ctx.reply("There is no active trade in this channel!")

        session = active_trades[ctx.channel.id]
        user_id = str(ctx.author.id)

        if ctx.author.id not in [session.requester.id, session.accepter.id]:
            return await ctx.reply("You are not part of this trade!")

        if session.confirmed[user_id]:
            return await ctx.reply("You have already confirmed the trade! You can't add more items.")

        if args is None:
            return await ctx.reply("Usage: `@Pokékiro trade add <order_number>` or `trade add Pokécoins/Shards <amount>` or `trade add <item> <amount>`")

        parts = args.strip().split()
        offer = session.offers[user_id]

        if len(parts) == 1 and parts[0].isdigit():
            order = int(parts[0])
            coll = load_collection()
            poke_list = coll.get(user_id, {}).get("pokemon", [])
            if order < 1 or order > len(poke_list):
                return await ctx.reply(f"Invalid order number. You have {len(poke_list)} Pokémon.")
            idx = order - 1
            if idx in offer["pokemon_indices"]:
                return await ctx.reply("That Pokémon is already in the trade!")
            offer["pokemon_indices"].append(idx)

        elif len(parts) == 2 and parts[0].lower() in ["pokécoins", "pokecoins", "shards"] and parts[1].isdigit():
            amount = int(parts[1])
            if amount <= 0:
                return await ctx.reply("Amount must be greater than 0!")

            inv = load_inventory()
            user_inv = inv.get(user_id, {})

            if parts[0].lower() in ["pokécoins", "pokecoins"]:
                if user_inv.get("pokecoins", 0) < amount:
                    return await ctx.reply("You don't have enough Pokécoins!")
                offer["pokecoins"] = amount
            else:
                if user_inv.get("shards", 0) < amount:
                    return await ctx.reply("You don't have enough Shards!")
                offer["shards"] = amount

        elif len(parts) >= 2 and parts[-1].isdigit():
            amount = int(parts[-1])
            item_name = " ".join(parts[:-1])
            if amount <= 0:
                return await ctx.reply("Amount must be greater than 0!")

            inv = load_inventory()
            user_inv = inv.get(user_id, {})
            user_items = user_inv.get("items", {})

            matched_key = next(
                (k for k in user_items if k.lower() == item_name.lower()),
                None
            )
            if not matched_key:
                return await ctx.reply(f"You don't have **{item_name}** in your inventory!")
            if user_items[matched_key] < amount:
                return await ctx.reply(f"You don't have enough **{matched_key}**! You have {user_items[matched_key]}.")
            offer["items"][matched_key] = amount

        else:
            return await ctx.reply("Invalid usage. Use `trade add <order_number>`, `trade add Pokécoins/Shards <amount>`, or `trade add <item> <amount>`.")

        session.confirmed[str(session.requester.id)] = False
        session.confirmed[str(session.accepter.id)] = False

        embed = build_trade_embed(session)
        trade_view = TradeActiveView(ctx, session)

        try:
            await session.trade_message.delete()
        except Exception:
            pass

        new_msg = await ctx.send(embed=embed, view=trade_view)
        trade_view.message = new_msg
        session.trade_message = new_msg

async def setup(bot):
    await bot.add_cog(TradingSystem(bot))
