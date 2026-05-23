import json
import os
import re
import discord
from datetime import datetime, timedelta
from discord.ext import commands

from database.pokemons_database import pokemons
from utils.stat_generator import calculate_stats
from utils.registered_checker import check_registration
from utils.artwork_handler import get_artwork_url, get_pokemon_artwork
from utils.constants import (
    GENDER_EMOJIS, UI_EMOJIS, HELD_ITEMS_EMOJIS,
    HUNTING_ITEMS_EMOJIS, FORM_CHANGING_ITEMS_EMOJIS
)

DATA_FILE      = "data/trainers_collection_database.json"
INVENTORY_FILE = "data/trainers_inventory_database.json"
ARCHIVE_FILE   = "data/trainers_old_unfused_untransformed_pokemons_database.json"

STATS     = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
MAX_LEVEL = 100

FUSION_ITEMS = {
    "n solarizer":      ("Dusk Mane Necrozma",  ["Necrozma", "Solgaleo"]),
    "n lunarizer":      ("Dawn Wings Necrozma", ["Necrozma", "Lunala"]),
    "dna splicers":     None,
    "ultranecrozium z": ("Ultra Necrozma",      ["Necrozma"]),
    "ruinous unity":    None,
}

DNA_SPLICER_COMBOS = {
    frozenset(["Kyurem", "Zekrom"]):      "Black Kyurem",
    frozenset(["Kyurem", "Reshiram"]):    "White Kyurem",
    frozenset(["Calyrex", "Glastrier"]):  "Ice Rider Calyrex",
    frozenset(["Calyrex", "Spectrier"]):  "Shadow Rider Calyrex",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_item_emoji(item_name: str) -> str:
    key = item_name.lower().replace(" ", "_").replace("-", "_")
    for d in [HELD_ITEMS_EMOJIS, HUNTING_ITEMS_EMOJIS, FORM_CHANGING_ITEMS_EMOJIS]:
        if key in d:
            return d[key]
    return ""


def poke_display(poke, order_no):
    gender_emoji = GENDER_EMOJIS.get(poke.get("gender", "").lower(), "")
    iv_percent   = poke.get("stats", {}).get("total_iv_percent", 0)
    shiny_prefix = f"{UI_EMOJIS['spark']} " if poke.get("shiny") else ""
    return f"**{shiny_prefix}Level {poke['level']} {poke['name']}{gender_emoji} ({iv_percent}%) No. {order_no}**"

def parse_stone_options(evo_text: str, item_name: str) -> list[str]:
    pattern = re.compile(
        r"evolves to\s+([^.]+?)\s+through\s+" + re.escape(item_name),
        re.IGNORECASE
    )
    results = []
    for m in pattern.finditer(evo_text or ""):
        name = m.group(1).strip().rstrip('.')
        if name not in results:
            results.append(name)
    return results

def parse_transform_options(evo_text: str, item_name: str) -> list[str]:
    pattern = re.compile(
        r"transforms into\s+([^.]+?)\s+through\s+" + re.escape(item_name),
        re.IGNORECASE
    )
    results = []
    for m in pattern.finditer(evo_text or ""):
        name = m.group(1).strip().rstrip('.')
        if name not in results:
            results.append(name)
    return results

# ── Dropdown View ─────────────────────────────────────────────────────────────

class EvolutionChoiceView(discord.ui.View):
    def __init__(self, cog, ctx, user_id, inv_data, coll_data,
                 found_key, poke_index, poke, options):
        super().__init__(timeout=30)
        self.cog        = cog
        self.ctx        = ctx
        self.user_id    = user_id
        self.inv_data   = inv_data
        self.coll_data  = coll_data
        self.found_key  = found_key
        self.poke_index = poke_index
        self.poke       = poke

        select = discord.ui.Select(
            placeholder="Select evolution #",
            options=[discord.SelectOption(label=opt, value=opt) for opt in options]
        )
        select.callback = self.on_select
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your choice!", ephemeral=True)
            return False
        return True

    async def on_select(self, interaction: discord.Interaction):
        chosen = interaction.data["values"][0]
        await interaction.response.defer()
        await self.cog._apply_transform(
            self.ctx, self.user_id, self.inv_data, self.coll_data,
            self.found_key, self.poke_index, self.poke, chosen
        )
        self.stop()


# ── Cog ───────────────────────────────────────────────────────────────────────

class ItemsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── summon ────────────────────────────────────────────────────────────────

    @commands.command(name="summon")
    async def summon(self, ctx, *, pokemon_name: str = None):
        if not await check_registration(ctx):
            return
        if not pokemon_name:
            return await ctx.reply("Usage: `@Pokékiro#4959 summon <pokémon>`")
        spawn_cog = self.bot.get_cog("SpawnSystem")
        await spawn_cog.spawn_with_stone(ctx, pokemon_name)

    # ── use ───────────────────────────────────────────────────────────────────

    @commands.command(name="use")
    async def use(self, ctx, *, args: str = None):
        if not await check_registration(ctx):
            return
        if not args:
            return await ctx.reply("Usage: `@Pokékiro use <incense | shiny charm | oval charm>`")

        item_name = args.strip()
        user_id   = str(ctx.author.id)

        if not os.path.exists(INVENTORY_FILE):
            return await ctx.reply("Inventory file not found!")

        with open(INVENTORY_FILE) as f:
            inv_data = json.load(f)

        items     = inv_data.get(user_id, {}).get("items", {})
        found_key = next((k for k in items if k.lower() == item_name.lower()), None)

        if not found_key or items[found_key] <= 0:
            return await ctx.reply(f"You don't have **{item_name}** in your inventory!")

        key_lower = found_key.lower()
        if key_lower == "shiny charm":
            await self._use_shiny_charm(ctx, user_id, inv_data, found_key)
        elif key_lower == "oval charm":
            await self._use_oval_charm(ctx, user_id, inv_data, found_key)
        elif key_lower == "incense":
            await self._use_incense(ctx, user_id, inv_data, found_key)
        else:
            await ctx.reply(
                f"**{found_key}** cannot be used this way. "
                f"Try `give` for items like Rare Candy, Mints, or Stones."
            )

    async def _use_shiny_charm(self, ctx, user_id, inv_data, found_key):
        SHINY_CHAINS_FILE = "data/trainers_shiny_chains_database.json"
        chains = {}
        if os.path.exists(SHINY_CHAINS_FILE):
            with open(SHINY_CHAINS_FILE) as f:
                chains = json.load(f)

        user_chain      = chains.get(user_id, {})
        existing_expires = user_chain.get("shiny_charm_expires")
        if existing_expires:
            end_time = datetime.fromisoformat(existing_expires)
            if datetime.now() < end_time:
                remaining = end_time - datetime.now()
                d = remaining.days
                h = remaining.seconds // 3600
                m = (remaining.seconds % 3600) // 60
                s = remaining.seconds % 60
                return await ctx.reply(
                    f"You already have a Shiny Charm active! It expires in "
                    f"**{d} days, {h} hours, {m} minutes and {s} seconds**."
                )

        end_time = datetime.now() + timedelta(weeks=1)
        if user_id not in chains:
            chains[user_id] = {"pokemon": None, "shiny_chain": 0}
        chains[user_id]["shiny_charm_expires"] = end_time.isoformat()
        os.makedirs("data", exist_ok=True)
        with open(SHINY_CHAINS_FILE, "w") as f:
            json.dump(chains, f, indent=4)

        self._deduct_item(inv_data, user_id, found_key)

        msg = (
            "You activated a Shiny Charm! It expires in **7 days, 0 hours, 0 minutes and 0 seconds**. "
            "Use `@Pokékiro shiny hunt` to check your remaining time."
        )
        try:
            await ctx.author.send(msg)
        except discord.Forbidden:
            await ctx.reply(msg)

    async def _use_oval_charm(self, ctx, user_id, inv_data, found_key):
        await ctx.reply("You used the **Oval Charm**! Its effects are now active.")
        self._deduct_item(inv_data, user_id, found_key)

    async def _use_incense(self, ctx, user_id, inv_data, found_key):
        await ctx.reply("You lit the **Incense**! Its effects are now active.")
        self._deduct_item(inv_data, user_id, found_key)

    # ── give ──────────────────────────────────────────────────────────────────

    @commands.command(name="give")
    async def give(self, ctx, *, args: str = None):
        if not await check_registration(ctx):
            return
        if not args:
            return await ctx.reply("Usage: `@Pokékiro give <item> <order_numbers...>`")

        user_id = str(ctx.author.id)
        with open(INVENTORY_FILE) as f:
            inv_data = json.load(f)
        items = inv_data.get(user_id, {}).get("items", {})

        tokens    = args.strip().split()
        num_end   = len(tokens)
        while num_end > 0 and tokens[num_end - 1].isdigit():
            num_end -= 1

        number_tokens = tokens[num_end:]
        name_tokens   = tokens[:num_end]

        if not name_tokens:
            return await ctx.reply("Usage: `@Pokékiro give <item> <order_numbers...>`")

        item_name    = " ".join(name_tokens)
        amount       = int(number_tokens[0]) if number_tokens else 1
        order_numbers = [int(x) for x in number_tokens[1:]] if len(number_tokens) > 1 else []

        if amount <= 0:
            return await ctx.reply("Amount must be at least 1!")

        found_key = next((k for k in items if k.lower() == item_name.lower()), None)
        if not found_key or items[found_key] <= 0:
            return await ctx.reply(f"You don't have **{item_name}** in your inventory!")

        key_lower = found_key.lower()

        if key_lower == "rare candy":
            await self._give_rare_candy(ctx, user_id, inv_data, found_key, amount, order_numbers)
        elif key_lower.endswith(" mint"):
            await self._give_nature_mint(ctx, user_id, inv_data, found_key, amount, order_numbers)
        elif key_lower in {"xp booster 1", "xp booster 2", "xp booster 3"}:
            await self._give_xp_booster(ctx, user_id, inv_data, found_key, int(key_lower[-1]), order_numbers)
        elif key_lower in FUSION_ITEMS or key_lower == "dna splicers":
            await self._give_fusion_item(ctx, user_id, inv_data, found_key, order_numbers)
        else:
            await self._give_transform_item(ctx, user_id, inv_data, found_key, order_numbers)

    # ── transform (stone / mega / gmax) ──────────────────────────────────────

    async def _give_transform_item(self, ctx, user_id, inv_data, found_key, order_numbers):
        with open(DATA_FILE) as f:
            coll_data = json.load(f)

        user_data    = coll_data.get(user_id, {})
        pokemon_list = user_data.get("pokemon", [])
        selected_no  = user_data.get("selected_pokemon")

        target = order_numbers[0] if order_numbers else selected_no
        if target is None or not (1 <= target <= len(pokemon_list)):
            return await ctx.reply("Invalid Pokémon order number or no Pokémon selected.")

        poke    = pokemon_list[target - 1]
        base_db = next((p for p in pokemons if p["name"].lower() == poke["name"].lower()), None)
        if not base_db:
            return await ctx.reply(f"**{poke['name']}** not found in database!")

        evo_text = base_db.get("evolution", "") or ""

        # Gather all matching options from plain text
        options = parse_stone_options(evo_text, found_key)
        options += [o for o in parse_transform_options(evo_text, found_key) if o not in options]

        if not options:
            return await ctx.reply(f"**{found_key}** cannot be used on **{poke['name']}**!")

        # Single option → apply directly
        if len(options) == 1:
            await self._apply_transform(
                ctx, user_id, inv_data, coll_data,
                found_key, target - 1, poke, options[0]
            )
            return

        # Multiple options → show dropdown
        embed = discord.Embed(
            title="Choose Evolution",
            description=f"Select which form **{poke['name']}** should evolve into:",
            color=discord.Color.gold()
        )
        view = EvolutionChoiceView(
            cog=self, ctx=ctx, user_id=user_id,
            inv_data=inv_data, coll_data=coll_data,
            found_key=found_key, poke_index=target - 1,
            poke=poke, options=options
        )
        await ctx.reply(embed=embed, view=view)

    async def _apply_transform(self, ctx, user_id, inv_data, coll_data,
                                found_key, poke_index, poke, new_form_name):
        new_base = next((p for p in pokemons if p["name"] == new_form_name), None)
        if not new_base:
            return await ctx.reply(f"**{new_form_name}** not found in database!")

        ivs       = {stat: poke["stats"].get(f"{stat}_iv", 0) for stat in STATS}
        new_stats = calculate_stats(new_base["base_stats"], ivs, poke["level"], poke["nature"])

        poke["held_item"] = found_key
        poke["name"]      = new_form_name
        poke["stats"]     = new_stats

        coll_data[user_id]["pokemon"][poke_index] = poke
        with open(DATA_FILE, "w") as f:
            json.dump(coll_data, f, indent=4)

        self._deduct_item(inv_data, user_id, found_key)

        item_emoji = get_item_emoji(found_key)
        await ctx.reply(
            f"{poke_display(poke, poke_index + 1)} is now holding {item_emoji} **{found_key}**."
        )

    # ── fusion ────────────────────────────────────────────────────────────────

    async def _give_fusion_item(self, ctx, user_id, inv_data, found_key, order_numbers):
        with open(DATA_FILE) as f:
            coll_data = json.load(f)

        user_data    = coll_data.get(user_id, {})
        pokemon_list = user_data.get("pokemon", [])
        key_lower    = found_key.lower()
        item_emoji   = get_item_emoji(found_key)

        # ── Ultranecrozium Z: single pokemon ──
        if key_lower == "ultranecrozium z":
            target = order_numbers[0] if order_numbers else user_data.get("selected_pokemon")
            if target is None or not (1 <= target <= len(pokemon_list)):
                return await ctx.reply("Invalid Pokémon order number or no Pokémon selected.")
            poke = pokemon_list[target - 1]
            if poke["name"] != "Necrozma":
                return await ctx.reply("**Ultranecrozium Z** can only be used on **Necrozma**!")

            fused_name = "Ultra Necrozma"
            fused_base = next((p for p in pokemons if p["name"] == fused_name), None)
            if not fused_base:
                return await ctx.reply(f"**{fused_name}** not found in database!")

            ivs       = {stat: poke["stats"].get(f"{stat}_iv", 0) for stat in STATS}
            new_stats = calculate_stats(fused_base["base_stats"], ivs, poke["level"], poke["nature"])

            self._archive_pokemon(user_id, poke)
            new_poke = dict(poke)
            new_poke["name"]      = fused_name
            new_poke["stats"]     = new_stats
            new_poke["held_item"] = found_key
            pokemon_list[target - 1] = new_poke

            coll_data[user_id]["pokemon"] = pokemon_list
            with open(DATA_FILE, "w") as f:
                json.dump(coll_data, f, indent=4)
            self._deduct_item(inv_data, user_id, found_key)
            await ctx.reply(f"{poke_display(new_poke, target)} is now holding {item_emoji} **{found_key}**.")
            return

        # ── Two-pokemon fusions ──
        if len(order_numbers) < 2:
            if key_lower == "dna splicers":
                return await ctx.reply(
                    "Usage: `give DNA Splicers <no1> <no2>`\n"
                    "Valid combos: Kyurem+Zekrom, Kyurem+Reshiram, Calyrex+Glastrier, Calyrex+Spectrier"
                )
            fusion_data = FUSION_ITEMS.get(key_lower)
            required    = fusion_data[1] if fusion_data else ["Pokémon 1", "Pokémon 2"]
            return await ctx.reply(
                f"Usage: `give {found_key} <{required[0]} order no.> <{required[1]} order no.>`"
            )

        no1, no2 = order_numbers[0], order_numbers[1]
        if not (1 <= no1 <= len(pokemon_list)) or not (1 <= no2 <= len(pokemon_list)):
            return await ctx.reply("Invalid order numbers!")
        if no1 == no2:
            return await ctx.reply("You need two different Pokémon!")

        poke1 = pokemon_list[no1 - 1]
        poke2 = pokemon_list[no2 - 1]

        if key_lower == "dna splicers":
            combo      = frozenset([poke1["name"], poke2["name"]])
            fused_name = DNA_SPLICER_COMBOS.get(combo)
            if not fused_name:
                return await ctx.reply(
                    f"**DNA Splicers** can't fuse **{poke1['name']}** and **{poke2['name']}**!"
                )
        else:
            fusion_data = FUSION_ITEMS.get(key_lower)
            if not fusion_data:
                return await ctx.reply(f"**{found_key}** is not a fusion item!")
            fused_name, required = fusion_data
            if set(required) != {poke1["name"], poke2["name"]}:
                return await ctx.reply(
                    f"**{found_key}** requires **{required[0]}** and **{required[1]}**!"
                )

        fused_base = next((p for p in pokemons if p["name"] == fused_name), None)
        if not fused_base:
            return await ctx.reply(f"**{fused_name}** not found in database!")

        ivs       = {stat: poke1["stats"].get(f"{stat}_iv", 0) for stat in STATS}
        new_stats = calculate_stats(fused_base["base_stats"], ivs, poke1["level"], poke1["nature"])

        higher, lower = (no1-1, no2-1) if no1 > no2 else (no2-1, no1-1)
        self._archive_pokemon(user_id, poke1, future_fused_name=fused_name)
        self._archive_pokemon(user_id, poke2, future_fused_name=fused_name)
        pokemon_list.pop(higher)
        pokemon_list.pop(lower)

        new_poke             = dict(poke1)
        new_poke["name"]     = fused_name
        new_poke["stats"]    = new_stats
        new_poke["held_item"] = found_key
        pokemon_list.append(new_poke)
        new_order = len(pokemon_list)

        coll_data[user_id]["pokemon"] = pokemon_list
        with open(DATA_FILE, "w") as f:
            json.dump(coll_data, f, indent=4)
        self._deduct_item(inv_data, user_id, found_key)

        await ctx.reply(
            f"{poke_display(poke1, no1)} and {poke_display(poke2, no2)} "
            f"is now holding {item_emoji} **{found_key}**.\n"
            f"**{fused_name}** has appeared as No. {new_order} in your collection!"
        )

    # ── rare candy ────────────────────────────────────────────────────────────

    async def _give_rare_candy(self, ctx, user_id, inv_data, found_key, amount, order_numbers):
        with open(DATA_FILE) as f:
            coll_data = json.load(f)

        user_data    = coll_data.get(user_id, {})
        pokemon_list = user_data.get("pokemon", [])
        selected_no  = user_data.get("selected_pokemon")

        targets = order_numbers if order_numbers else (
            [selected_no] if selected_no and 1 <= selected_no <= len(pokemon_list) else None
        )
        if not targets:
            return await ctx.reply("You don't have a Pokémon selected! Use `select` first.")

        invalid = [n for n in targets if not (1 <= n <= len(pokemon_list))]
        if invalid:
            return await ctx.reply(f"Invalid order number(s): {', '.join(map(str, invalid))}")

        total_needed = amount * len(targets)
        available    = inv_data[user_id].get("items", {}).get(found_key, 0)
        if available < total_needed:
            return await ctx.reply(
                f"You need **{total_needed}** Rare Candies but only have **{available}**!"
            )

        for order_no in targets:
            poke = pokemon_list[order_no - 1]
            for _ in range(amount):
                if poke.get("level", 1) >= MAX_LEVEL:
                    break
                new_level = poke["level"] + 1
                base = next((p for p in pokemons if p["name"] == poke["name"]), None)
                if base:
                    ivs = {stat: poke["stats"].get(f"{stat}_iv", 0) for stat in STATS}
                    poke["stats"] = calculate_stats(base["base_stats"], ivs, new_level, poke["nature"])
                poke["level"] = new_level
                poke["xp"]    = f"0/{new_level * 50 if new_level < MAX_LEVEL else 5000}"
            pokemon_list[order_no - 1] = poke

        coll_data[user_id]["pokemon"] = pokemon_list
        with open(DATA_FILE, "w") as f:
            json.dump(coll_data, f, indent=4)

        items = inv_data[user_id].get("items", {})
        items[found_key] -= total_needed
        if items[found_key] <= 0:
            del items[found_key]
        inv_data[user_id]["items"] = items
        with open(INVENTORY_FILE, "w") as f:
            json.dump(inv_data, f, indent=4)

        remaining = items.get(found_key, 0)
        for order_no in targets:
            poke  = pokemon_list[order_no - 1]
            db_p  = next((p for p in pokemons if p["name"].lower() == poke["name"].lower()), None)
            is_shiny = poke.get("shiny", False)
            artwork_file, _  = get_pokemon_artwork(db_p, poke.get("gender", ""), False) if db_p else (None, False)
            shiny_file, _    = get_pokemon_artwork(db_p, poke.get("gender", ""), True)  if db_p else (None, True)
            embed = discord.Embed(
                title="Level Up!",
                description=f"{ctx.author.display_name} your **{poke['name']}** is now level **{poke['level']}**!",
                color=discord.Color.gold()
            )
            if is_shiny and shiny_file:
                embed.set_thumbnail(url=get_artwork_url(shiny_file, shiny=True))
            elif artwork_file:
                embed.set_thumbnail(url=get_artwork_url(artwork_file))
            embed.set_footer(text=f"Remaining Rare Candies: {remaining}")
            await ctx.send(embed=embed)

    # ── nature mint ───────────────────────────────────────────────────────────

    async def _give_nature_mint(self, ctx, user_id, inv_data, found_key, amount, order_numbers):
        new_nature = found_key.replace(" Mint", "").replace(" mint", "").strip().lower()
        from utils.abilities_natures import is_valid_nature
        if not is_valid_nature(new_nature):
            return await ctx.reply(f"**{found_key}** is not a valid nature mint!")

        with open(DATA_FILE) as f:
            coll_data = json.load(f)

        user_data    = coll_data.get(user_id, {})
        pokemon_list = user_data.get("pokemon", [])
        selected_no  = user_data.get("selected_pokemon")

        targets = order_numbers if order_numbers else (
            [selected_no] if selected_no and 1 <= selected_no <= len(pokemon_list) else None
        )
        if not targets:
            return await ctx.reply("You don't have a Pokémon selected! Use `select` first.")

        invalid = [n for n in targets if not (1 <= n <= len(pokemon_list))]
        if invalid:
            return await ctx.reply(f"Invalid order number(s): {', '.join(map(str, invalid))}")

        total_needed = amount * len(targets)
        available    = inv_data[user_id].get("items", {}).get(found_key, 0)
        if available < total_needed:
            return await ctx.reply(f"You need **{total_needed}** {found_key}(s) but only have **{available}**!")

        for order_no in targets:
            poke = pokemon_list[order_no - 1]
            poke["nature"] = new_nature.capitalize()
            base = next((p for p in pokemons if p["name"] == poke["name"]), None)
            if base:
                ivs = {stat: poke["stats"].get(f"{stat}_iv", 0) for stat in STATS}
                poke["stats"] = calculate_stats(base["base_stats"], ivs, poke["level"], poke["nature"])
            pokemon_list[order_no - 1] = poke

        coll_data[user_id]["pokemon"] = pokemon_list
        with open(DATA_FILE, "w") as f:
            json.dump(coll_data, f, indent=4)

        items = inv_data[user_id].get("items", {})
        items[found_key] -= total_needed
        if items[found_key] <= 0:
            del items[found_key]
        inv_data[user_id]["items"] = items
        with open(INVENTORY_FILE, "w") as f:
            json.dump(inv_data, f, indent=4)

        for order_no in targets:
            poke = pokemon_list[order_no - 1]
            await ctx.send(f"You changed **{poke['name']}'s** nature to **{poke['nature']}**!")

    # ── xp booster ────────────────────────────────────────────────────────────

    async def _give_xp_booster(self, ctx, user_id, inv_data, found_key, multiplier, order_numbers):
        with open(DATA_FILE) as f:
            coll_data = json.load(f)

        user_data    = coll_data.get(user_id, {})
        pokemon_list = user_data.get("pokemon", [])
        selected_no  = user_data.get("selected_pokemon")

        target = order_numbers[0] if order_numbers else selected_no
        if target is None or not (1 <= target <= len(pokemon_list)):
            return await ctx.reply("Invalid Pokémon order number or no Pokémon selected.")
        if len(order_numbers) > 1:
            return await ctx.reply("XP Booster can only be given to one Pokémon at a time!")

        poke     = pokemon_list[target - 1]
        existing = poke.get("xp_booster")
        if existing:
            end_time = datetime.fromisoformat(existing["ends_at"])
            if datetime.now() < end_time:
                remaining = end_time - datetime.now()
                mins = int(remaining.total_seconds() // 60)
                secs = int(remaining.total_seconds() % 60)
                return await ctx.reply(
                    f"**{poke['name']}** already has an active XP Booster! Ends in **{mins}m {secs}s**."
                )

        end_time             = datetime.now() + timedelta(hours=multiplier)
        poke["xp_booster"]  = {"multiplier": multiplier, "ends_at": end_time.isoformat()}
        pokemon_list[target - 1] = poke

        coll_data[user_id]["pokemon"] = pokemon_list
        with open(DATA_FILE, "w") as f:
            json.dump(coll_data, f, indent=4)

        self._deduct_item(inv_data, user_id, found_key)
        await ctx.send(
            f"**XP Booster {multiplier}x** activated for **{poke['name']}**! "
            f"XP gain is now **{1 + multiplier} per message** for **{multiplier} hour(s)**."
        )

    # ── utils ─────────────────────────────────────────────────────────────────

    def _deduct_item(self, inv_data, user_id, found_key):
        items = inv_data[user_id].get("items", {})
        items[found_key] -= 1
        if items[found_key] <= 0:
            del items[found_key]
        inv_data[user_id]["items"] = items
        with open(INVENTORY_FILE, "w") as f:
            json.dump(inv_data, f, indent=4)

    def _archive_pokemon(self, user_id, poke, future_fused_name=None):
        os.makedirs("data", exist_ok=True)
        archive = {}
        if os.path.exists(ARCHIVE_FILE):
            with open(ARCHIVE_FILE) as f:
                archive = json.load(f)
        if user_id not in archive:
            archive[user_id] = []
        archive[user_id].append({
            "original_data": poke,
            "fused_into":    future_fused_name,
        })
        with open(ARCHIVE_FILE, "w") as f:
            json.dump(archive, f, indent=4)


async def setup(bot):
    await bot.add_cog(ItemsCommands(bot))