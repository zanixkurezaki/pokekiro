import discord, json, os
from discord.ext import commands
import random
import asyncio
import math
from datetime import datetime, timedelta

from database.pokemons_database import pokemons
from utils.abilities_natures import get_random_nature as generate_nature, choose_ability
from utils.stat_generator import generate_ivs, calculate_stats
from utils.gender_ratio_generation import generate_gender
from utils.constants import GENDER_EMOJIS, CURRENCY_EXCHANGE_AND_BALANCE, UI_EMOJIS
from utils.registered_checker import check_registration
from utils.artwork_handler import get_artwork_url, get_pokemon_artwork



DATA_FILE = "data/trainers_collection_database.json"
INVENTORY_FILE = "data/trainers_inventory_database.json"
SHINY_CHAINS_FILE = "data/trainers_shiny_chains_database.json"

def get_shiny_chain_data(user_id: str) -> dict:
    """Load user's shiny chain data."""
    if not os.path.exists(SHINY_CHAINS_FILE):
        return {}
    try:
        with open(SHINY_CHAINS_FILE, "r") as f:
            chains = json.load(f)
        return chains.get(user_id, {})
    except Exception:
        return {}

def has_active_charm(chain_data: dict) -> bool:
    """Check if user has an active Shiny Charm."""
    expires = chain_data.get("shiny_charm_expires")
    if not expires:
        return False
    try:
        return datetime.now() < datetime.fromisoformat(expires)
    except Exception:
        return False

def is_shiny(chain: int, has_charm: bool) -> bool:
    """Pokétwo formula: (1 + sqrt(chain) / 7) / 4096"""
    chance = (1 + math.sqrt(chain) / 7) / 4096
    if has_charm:
        chance *= (4096 / 3413.3)
    return random.random() < chance

def generate_spawn_level() -> int:
    ranges = [
        (1,  10,  2.0),
        (10, 20,  5.0),
        (20, 30,  10.0),
        (30, 40,  18.0),
        (40, 50,  25.0),
        (50, 60,  25.0),
        (60, 70,  10.0),
        (70, 80,  3.0),
        (80, 90,  1.5),
        (90, 100, 0.5),
    ]
    chosen = random.choices(ranges, weights=[r[2] for r in ranges])[0]
    return random.randint(chosen[0], chosen[1])

active_spawns: dict = {}
active_incenses: dict = {}

caught_spawns: set = set()

MESSAGES_PER_SPAWN = 24
_message_count: int = 0
_last_message_time: float = 0.0
_last_user_times: dict = {}

def find_pokemon(name: str):
    """Case-insensitive search, only catchable pokemon."""
    return next(
        (p for p in pokemons
         if p["name"].lower() == name.lower() and p.get("catchable", "No") == "Yes"),
        None
    )

def generate_pokemon_data(pokemon: dict) -> dict:
    """Generate full stats/nature/ability/gender for a spawned pokemon."""
    level = generate_spawn_level()
    nature = generate_nature()
    ivs = generate_ivs()
    stats = calculate_stats(pokemon["base_stats"], ivs, level, nature)
    ability = choose_ability(pokemon["ability"], pokemon["hidden_ability"])
    gender = generate_gender(pokemon["gender_ratio"])

    return {
        "name": pokemon["name"],
        "level": level,
        "xp": f"0/{level * 50}",
        "nature": nature,
        "ability": ability,
        "gender": gender,
        "stats": stats,
        "shiny": False,
        "friendship_points": 0,
        "friendship_points": 0,
    }

def make_spawn_embed(pokemon_name: str, footer_text: str = None, title: str = None, is_shiny: bool = False) -> discord.Embed:
    """Create a standard 'wild pokemon appeared' embed."""
    embed = discord.Embed(
        title=title or "A wild pokémon has appeared!",
        description=(
            f"Guess the pokémon and type "
            f"`@Pokékiro#4959 catch {pokemon_name}` to catch it!"
        ),
        color=discord.Color.gold()
    )
    if footer_text:
        embed.set_footer(text=footer_text)

    artwork_file = None
    shiny_artwork_file = None
    for db_p in pokemons:
        if db_p["name"].lower() == pokemon_name.lower():
            artwork_file, _ = get_pokemon_artwork(db_p, pokemon.get("gender", ""), False)
            shiny_artwork_file = db_p.get("shiny_artwork").replace("shiny_artwork_file = db_p.get(\"shiny_artwork\")", "shiny_artwork_file = db_p.get(\"shiny_artwork\") if not pokemon.get(\"shiny\") else get_pokemon_artwork(db_p, pokemon.get(\"gender\", \"\"), True)[0]")
            break

    if is_shiny and shiny_artwork_file:
        embed.set_image(url=get_artwork_url(shiny_artwork_file, shiny=True))
    elif artwork_file:
        embed.set_image(url=get_artwork_url(artwork_file))

    return embed

def get_spawn_title(channel_id: int) -> str:
    """Return correct title for new spawn embed based on previous spawn state."""
    prev = active_spawns.get(channel_id)
    if prev and channel_id not in caught_spawns:
        return f"Wild {prev['name']} fled. A new wild pokémon has appeared!"
    return "A wild pokémon has appeared!"

DURATION_MAP = {"30m": (1800, "30 minutes"), "1h": (3600, "1 hour"), "2h": (7200, "2 hours"),
                "3h": (10800, "3 hours"), "1d": (86400, "1 day")}
INTERVAL_MAP = {"10s": (10, "10 seconds"), "20s": (20, "20 seconds"), "30s": (30, "30 seconds")}

def calc_incense(duration_key, interval_key):
    dur_sec = DURATION_MAP[duration_key][0]
    int_sec = INTERVAL_MAP[interval_key][0]
    total   = dur_sec // int_sec
    price   = math.ceil(total * 0.25)
    return total, price

def fmt_time_remaining(end_time: datetime) -> str:
    diff = end_time - datetime.now()
    secs = max(0, int(diff.total_seconds()))
    h, rem = divmod(secs, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    elif m:
        return f"{m}m {s}s"
    return f"{s}s"

class IncenseSettingsView(discord.ui.View):
    def __init__(self, ctx, timeout=60):
        super().__init__(timeout=timeout)
        self.ctx      = ctx
        self.duration = "1h"
        self.interval = "20s"
        self.msg      = None
        self.btn_msg  = None
        self._build_selects()

    def _build_selects(self):
        self.clear_items()

        dur_select = discord.ui.Select(
            placeholder="Duration",
            options=[
                discord.SelectOption(label="30 minutes", value="30m"),
                discord.SelectOption(label="1 hour",     value="1h", default=True),
                discord.SelectOption(label="2 hours",    value="2h"),
                discord.SelectOption(label="3 hours",    value="3h"),
                discord.SelectOption(label="1 day",      value="1d"),
            ],
            row=0
        )
        dur_select.callback = self._dur_callback
        self.add_item(dur_select)

        int_select = discord.ui.Select(
            placeholder="Interval",
            options=[
                discord.SelectOption(label="10 seconds", value="10s"),
                discord.SelectOption(label="20 seconds", value="20s", default=True),
                discord.SelectOption(label="30 seconds", value="30s"),
            ],
            row=1
        )
        int_select.callback = self._int_callback
        self.add_item(int_select)

        confirm_btn = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success, row=2)
        confirm_btn.callback = self._confirm_callback
        self.add_item(confirm_btn)

        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
        cancel_btn.callback = self._cancel_callback
        self.add_item(cancel_btn)

    def _get_content(self):
        total, price = calc_incense(self.duration, self.interval)
        dur_label = DURATION_MAP[self.duration][1]
        int_label = INTERVAL_MAP[self.interval][1]
        lines = [
            "### Please choose the Duration and Interval of your Incense",
            f"**Total Spawns**: {total:,}",
            f"**Duration**: {dur_label}",
            f"**Interval**: {int_label}",
            f"**Price**: {price} Shards",
            "",
            "**The incense will instantly be activated in this channel. Are you sure?**",
        ]
        return "\n".join(lines)

    async def _dur_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your incense!", ephemeral=True)
        self.duration = interaction.data["values"][0]
        self._build_selects()
        await interaction.response.edit_message(content=self._get_content(), view=self)

    async def _int_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your incense!", ephemeral=True)
        self.interval = interaction.data["values"][0]
        self._build_selects()
        await interaction.response.edit_message(content=self._get_content(), view=self)

    async def _confirm_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your incense!", ephemeral=True)

        total, price = calc_incense(self.duration, self.interval)
        int_sec = INTERVAL_MAP[self.interval][0]

        with open(INVENTORY_FILE, "r") as f:
            inv_data = json.load(f)
        user_id = str(self.ctx.author.id)
        user_inv = inv_data.get(user_id, {})
        shards = user_inv.get("shards", 0)

        if shards < price:
            return await interaction.response.send_message(
                f"You don't have enough Shards! You need **{price}** but have **{shards}**.",
                ephemeral=True
            )

        inv_data[user_id]["shards"] = shards - price
        with open(INVENTORY_FILE, "w") as f:
            json.dump(inv_data, f, indent=4)

        await interaction.response.edit_message(view=None)

        self.stop()
        channel = interaction.channel
        end_time = datetime.now() + timedelta(seconds=DURATION_MAP[self.duration][0])
        active_incenses[channel.id] = {
            "remaining": total,
            "total":     total,
            "interval":  int_sec,
            "end_time":  end_time,
        }

        self.ctx.bot.loop.create_task(
            _run_incense(channel, total, int_sec, end_time)
        )

    async def _cancel_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your incense!", ephemeral=True)
        self.stop()
        await interaction.response.edit_message(content="Incense cancelled.", view=None)

    async def on_timeout(self):
        if self.msg:
            try:
                await self.msg.edit(content="Time's up! Incense setup cancelled.", view=None)
            except Exception:
                pass

async def _run_incense(channel, total_spawns, interval_sec, end_time):
    """Background task — spawns pokemon at interval until done."""
    remaining = total_spawns

    while remaining > 0 and channel.id in active_incenses:
        await asyncio.sleep(interval_sec)

        if channel.id not in active_incenses:
            break

        catchable = [p for p in pokemons if p.get("catchable") == "Yes" and "spawn_weight" in p]
        if not catchable:
            break
        weights = [p["spawn_weight"] for p in catchable]
        pokemon = random.choices(catchable, weights=weights, k=1)[0]
        poke_data = generate_pokemon_data(pokemon)

        title = get_spawn_title(channel.id)

        remaining -= 1
        if channel.id in active_incenses:
            active_incenses[channel.id]["remaining"] = remaining

        time_left = fmt_time_remaining(end_time)
        end_fmt   = end_time.strftime("%I:%M %p")
        interval_label = f"{interval_sec}s"
        footer_text = (
            f"Incense: Active.\n"
            f"Spawns Remaining: {remaining:,}.\n"
            f"Spawn Interval: {interval_label}.\n"
            f"Ends in {time_left} at | Today at {end_fmt}"
        )

        embed = make_spawn_embed(pokemon["name"], footer_text, title)
        sent_msg = await channel.send(embed=embed)

        active_spawns[channel.id] = {
            "name": pokemon["name"],
            "data": poke_data,
            "message": sent_msg
        }
        caught_spawns.discard(channel.id)

    active_incenses.pop(channel.id, None)

class SpawnSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        global _message_count, _last_message_time, _last_user_times

        if message.author.bot:
            return
        prefixes = await self.bot.get_prefix(message)
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        if any(message.content.startswith(p) for p in prefixes):
            return

        import time
        now = time.time()
        user_id = str(message.author.id)

        if now - _last_message_time < 1.0:
            return

        if now - _last_user_times.get(user_id, 0) < 1.5:
            return

        _last_message_time = now
        _last_user_times[user_id] = now
        _message_count += 1

        if _message_count >= MESSAGES_PER_SPAWN:
            _message_count = 0
            catchable = [p for p in pokemons if p.get("catchable") == "Yes" and "spawn_weight" in p]
            if not catchable:
                return
            weights = [p["spawn_weight"] for p in catchable]
            pokemon = random.choices(catchable, weights=weights, k=1)[0]
            poke_data = generate_pokemon_data(pokemon)

            title = get_spawn_title(message.channel.id)
            embed = make_spawn_embed(pokemon["name"], title=title)
            sent_msg = await message.channel.send(embed=embed)

            active_spawns[message.channel.id] = {
                "name": pokemon["name"],
                "data": poke_data,
                "message": sent_msg
            }
            caught_spawns.discard(message.channel.id)

    async def spawn_with_stone(self, ctx, actual_pokemon: str):
        """Called by use_item cog when Summoning Stone is used."""
        user_id = str(ctx.author.id)

        with open(INVENTORY_FILE, "r") as f:
            inv_data = json.load(f)

        user_inv = inv_data.get(user_id, {})
        items = user_inv.get("items", {})
        stone_count = items.get("Summoning Stone", 0)

        if stone_count < 1:
            return await ctx.reply("You don't have any **Summoning Stone**!")

        pokemon = find_pokemon(actual_pokemon)
        if not pokemon:
            return await ctx.reply(
                f"**{actual_pokemon}** doesn't exist or is not catchable!"
            )

        channel_id = ctx.channel.id

        items["Summoning Stone"] = stone_count - 1
        if items["Summoning Stone"] == 0:
            del items["Summoning Stone"]
        inv_data[user_id]["items"] = items
        with open(INVENTORY_FILE, "w") as f:
            json.dump(inv_data, f, indent=4)

        poke_data = generate_pokemon_data(pokemon)

        title = get_spawn_title(channel_id)
        embed = make_spawn_embed(pokemon["name"], title=title)
        await ctx.send(embed=embed)

        active_spawns[channel_id] = {
            "name": pokemon["name"],
            "data": poke_data,
        }
        caught_spawns.discard(channel_id)

    @commands.command(name="catch")
    async def catch(self, ctx, *, pokemon_name: str = None):
        if not await check_registration(ctx):
            return

        if not pokemon_name:
            return

        channel_id = ctx.channel.id
        spawn = active_spawns.get(channel_id)

        if not spawn:
            return

        if channel_id in caught_spawns:
            return

        if spawn["name"].lower() != pokemon_name.strip().lower():
            await ctx.send("That is the wrong pokémon!")
            return

        caught_spawns.add(channel_id)
        active_spawns.pop(channel_id, None)

        user_id = str(ctx.author.id)
        poke_data = spawn["data"]

        try:
            chain_data = get_shiny_chain_data(user_id)
            hunting = chain_data.get("pokemon", "")
            chain = chain_data.get("shiny_chain", 0) if hunting and hunting.lower() == poke_data["name"].lower() else 0
            charm = has_active_charm(chain_data)
            poke_data["shiny"] = is_shiny(chain, charm)
        except Exception:
            poke_data["shiny"] = False

        with open(DATA_FILE, "r") as f:
            coll_data = json.load(f)

        coll_data[user_id]["pokemon"].append(poke_data)

        with open(DATA_FILE, "w") as f:
            json.dump(coll_data, f, indent=4)

        with open(INVENTORY_FILE, "r") as f:
            inv_data = json.load(f)

        inv_data[user_id]["pokecoins"] = inv_data[user_id].get("pokecoins", 0) + 10

        with open(INVENTORY_FILE, "w") as f:
            json.dump(inv_data, f, indent=4)

        gender_emoji = GENDER_EMOJIS.get(poke_data["gender"].lower(), "")
        iv_percent = poke_data["stats"].get("total_iv_percent", 0)
        pokecoin_emoji = CURRENCY_EXCHANGE_AND_BALANCE.get("pokecoin", "")
        shiny_prefix = f"{UI_EMOJIS['spark']} " if poke_data["shiny"] else ""

        await ctx.send(
            f"Congratulations <@{ctx.author.id}>! "
            f"You caught a Level **{poke_data['level']}** "
            f"**{shiny_prefix}{poke_data['name']}**{gender_emoji} "
            f"(**{iv_percent}%**) ! "
            f"You received 10 {pokecoin_emoji} Pokécoins."
        )

        try:
            if os.path.exists(SHINY_CHAINS_FILE):
                with open(SHINY_CHAINS_FILE, "r") as f:
                    chains = json.load(f)

                user_chain = chains.get(user_id, {})
                hunting = user_chain.get("pokemon", "")

                if hunting and hunting.lower() == poke_data["name"].lower():
                    spark = "<a:spark:1407360333043208244>"

                    if poke_data["shiny"]:
                        old_chain = user_chain.get("shiny_chain", 0)
                        chains[user_id]["shiny_chain"] = 0

                        charm_exp = user_chain.get("shiny_charm_expires")
                        if charm_exp and datetime.now() >= datetime.fromisoformat(charm_exp):
                            chains[user_id].pop("shiny_charm_expires", None)

                        with open(SHINY_CHAINS_FILE, "w") as f:
                            json.dump(chains, f, indent=4)

                        await ctx.send(
                            f"Shiny streak reset. (**{old_chain}**)\n"
                            f"These colors seem unusual... {spark}"
                        )
                    else:
                        new_chain = user_chain.get("shiny_chain", 0) + 1
                        chains[user_id]["shiny_chain"] = new_chain

                        charm_exp = user_chain.get("shiny_charm_expires")
                        if charm_exp and datetime.now() >= datetime.fromisoformat(charm_exp):
                            chains[user_id].pop("shiny_charm_expires", None)

                        with open(SHINY_CHAINS_FILE, "w") as f:
                            json.dump(chains, f, indent=4)

                        await ctx.send(f"+1 Shiny chain! (**{new_chain}**)")
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(SpawnSystem(bot))
