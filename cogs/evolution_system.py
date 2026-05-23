import io
import re
import json
import os
import discord
from discord.ext import commands
from PIL import Image

from database.pokemons_database import pokemons
from utils.stat_generator import calculate_stats
from utils.registered_checker import check_registration
from utils.artwork_handler import get_artwork_url, fetch_artwork, get_pokemon_artwork
from cogs.timezone import get_time_period, get_user_location

DATA_FILE          = "data/trainers_collection_database.json"
EVOLUTION_GIF_PATH = "assets/evolution.gif"
STATS = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]

TIME_MAP = {
    "day time": "day", "day": "day",
    "night time": "night", "night": "night",
    "evening time": "evening", "evening": "evening",
    "morning time": "morning", "morning": "morning",
    "afternoon": "afternoon",
}


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_evolution_text(text: str) -> list:
    if not text:
        return []
    results = []
    sentences = [s.strip().rstrip('.') for s in re.split(r'\.\s*', text) if s.strip()]

    def extract_time(s):
        for k, v in TIME_MAP.items():
            if f"during {k}" in s.lower():
                return v
        return None

    for s in sentences:
        sl = s.lower()

        if "does not evolve" in sl:
            results.append({"type": "none"})
            continue

        # transforms into X through Item
        m = re.match(r'.+? transforms into (.+?) through (.+)', s, re.IGNORECASE)
        if m:
            results.append({"type": "transform_into", "target": m.group(1).strip(), "item": m.group(2).strip()})
            continue

        # transforms from X through Item
        m = re.match(r'.+? transforms from (.+?) through (.+)', s, re.IGNORECASE)
        if m:
            results.append({"type": "transform_from", "source": m.group(1).strip(), "item": m.group(2).strip()})
            continue

        # evolves to X while trade holding Item
        m = re.match(r'.+? evolves to (.+?) while trade holding (.+)', s, re.IGNORECASE)
        if m:
            results.append({"type": "evolves_to", "target": m.group(1).strip(),
                            "conditions": {"trade": True, "held_item": m.group(2).strip()}})
            continue

        # evolves to X through high Friendship during time
        m = re.match(r'.+? evolves to (.+?) through high friendship during (.+)', s, re.IGNORECASE)
        if m:
            t = TIME_MAP.get(m.group(2).strip().lower(), m.group(2).strip().lower())
            results.append({"type": "evolves_to", "target": m.group(1).strip(),
                            "conditions": {"friendship": 220, "time": t}})
            continue

        # evolves to X through high Friendship
        m = re.match(r'.+? evolves to (.+?) through high friendship', s, re.IGNORECASE)
        if m:
            results.append({"type": "evolves_to", "target": m.group(1).strip(),
                            "conditions": {"friendship": 220}})
            continue

        # evolves to X through trade
        m = re.match(r'.+? evolves to (.+?) through trade', s, re.IGNORECASE)
        if m:
            results.append({"type": "evolves_to", "target": m.group(1).strip(),
                            "conditions": {"trade": True}})
            continue

        # evolves to X through level up during time
        m = re.match(r'.+? evolves to (.+?) through level up during (.+)', s, re.IGNORECASE)
        if m:
            t = TIME_MAP.get(m.group(2).strip().lower(), m.group(2).strip().lower())
            results.append({"type": "evolves_to", "target": m.group(1).strip(),
                            "conditions": {"level_up": True, "time": t}})
            continue

        # evolves to X through Item during time
        m = re.match(r'.+? evolves to (.+?) through (.+?) during (.+)', s, re.IGNORECASE)
        if m:
            t = TIME_MAP.get(m.group(3).strip().lower(), m.group(3).strip().lower())
            results.append({"type": "evolves_to", "target": m.group(1).strip(),
                            "conditions": {"item": m.group(2).strip(), "time": t}})
            continue

        # evolves to X through Item
        m = re.match(r'.+? evolves to (.+?) through (.+)', s, re.IGNORECASE)
        if m:
            results.append({"type": "evolves_to", "target": m.group(1).strip(),
                            "conditions": {"item": m.group(2).strip()}})
            continue

        # evolves to X at level N during time
        m = re.match(r'.+? evolves to (.+?) at level (\d+) during (.+)', s, re.IGNORECASE)
        if m:
            t = TIME_MAP.get(m.group(3).strip().lower(), m.group(3).strip().lower())
            results.append({"type": "evolves_to", "target": m.group(1).strip(),
                            "conditions": {"level": int(m.group(2)), "time": t}})
            continue

        # evolves to X at level N
        m = re.match(r'.+? evolves to (.+?) at level (\d+)', s, re.IGNORECASE)
        if m:
            results.append({"type": "evolves_to", "target": m.group(1).strip(),
                            "conditions": {"level": int(m.group(2))}})
            continue

        # evolves from X (reverse info)
        m = re.match(r'.+? evolves from (.+)', s, re.IGNORECASE)
        if m:
            results.append({"type": "evolves_from", "source": m.group(1).strip()})
            continue

    return results


# ── Evolution Check ───────────────────────────────────────────────────────────

def check_evolution_conditions(poke: dict, conditions: dict, user_id: str,
                                being_traded: bool = False) -> bool:
    if poke.get("held_item", "").lower() == "everstone":
        return False

    # Level
    if "level" in conditions:
        if poke.get("level", 0) < conditions["level"]:
            return False

    # Level up (time-gated level up — just needs level up trigger)
    if "level_up" in conditions:
        pass  # caller confirms level up happened

    # Item (stone/held item given)
    if "item" in conditions:
        held = poke.get("held_item", "")
        if held.lower() != conditions["item"].lower():
            return False

    # Trade
    if "trade" in conditions and conditions["trade"]:
        if not being_traded:
            return False

    # Trade + held item
    if "held_item" in conditions:
        held = poke.get("held_item", "")
        if held.lower() != conditions["held_item"].lower():
            return False

    # Friendship
    if "friendship" in conditions:
        if poke.get("friendship", 0) < conditions["friendship"]:
            return False

    # Time
    if "time" in conditions:
        loc = get_user_location(user_id)
        if loc:
            period = get_time_period(loc["lat"], loc["lon"])[0]
            if period != conditions["time"]:
                return False

    return True


def get_evolved_poke(poke: dict, user_id: str, trigger: str = "level",
                     being_traded: bool = False) -> dict | None:
    if poke.get("held_item", "").lower() == "everstone":
        return None

    base = next((p for p in pokemons if p["name"] == poke["name"]), None)
    if not base:
        return None

    evo_text = base.get("evolution", "")
    if not evo_text:
        return None

    parsed = parse_evolution_text(evo_text)
    if not parsed:
        return None

    for evo in parsed:
        if evo["type"] != "evolves_to":
            continue

        conditions = evo.get("conditions", {})

        # Match trigger to condition type
        if trigger == "level":
            if "level" not in conditions and "level_up" not in conditions:
                continue
        elif trigger == "item":
            if "item" not in conditions and "held_item" not in conditions:
                continue
        elif trigger == "trade":
            if "trade" not in conditions:
                continue
        elif trigger == "friendship":
            if "friendship" not in conditions:
                continue

        if not check_evolution_conditions(poke, conditions, user_id, being_traded):
            continue

        new_name = evo["target"]
        new_base = next((p for p in pokemons if p["name"] == new_name), None)
        if not new_base:
            continue

        ivs       = {stat: poke["stats"].get(f"{stat}_iv", 0) for stat in STATS}
        new_stats = calculate_stats(new_base["base_stats"], ivs, poke["level"], poke["nature"])

        evolved       = dict(poke)
        evolved["name"]  = new_name
        evolved["stats"] = new_stats
        evolved["held_item"] = ""
        return evolved

    return None


def get_transform_options(poke: dict) -> list:
    """Return list of transform targets for item-based transforms (megas, gmax)."""
    base = next((p for p in pokemons if p["name"] == poke["name"]), None)
    if not base:
        return []
    parsed = parse_evolution_text(base.get("evolution", ""))
    return [e for e in parsed if e["type"] == "transform_into"]


# ── GIF ───────────────────────────────────────────────────────────────────────

def overlay_artwork_on_gif(artwork: Image.Image) -> io.BytesIO:
    gif    = Image.open(EVOLUTION_GIF_PATH)
    gif_w, gif_h = gif.size
    target = int(min(gif_w, gif_h) * 0.35)
    art_w  = target
    art_h  = int(art_w * artwork.height / artwork.width)
    artwork = artwork.resize((art_w, art_h), Image.LANCZOS)
    x, y   = (gif_w - art_w) // 2, (gif_h - art_h) // 2
    frames = []
    try:
        while True:
            frame = gif.copy().convert("RGBA")
            frame.paste(artwork, (x, y), artwork)
            frames.append(frame)
            gif.seek(gif.tell() + 1)
    except EOFError:
        pass
    out = io.BytesIO()
    frames[0].save(out, format="GIF", save_all=True, append_images=frames[1:],
                   loop=0, duration=gif.info.get("duration", 100))
    out.seek(0)
    return out


# ── Discord UI ────────────────────────────────────────────────────────────────

async def send_evolution_prompt(channel, user_id: str, poke_index: int,
                                 old_poke: dict, evolved: dict):
    old_base = next((p for p in pokemons if p["name"] == old_poke["name"]), None)
    is_shiny = old_poke.get("shiny", False)
    gender   = old_poke.get("gender", "")

    artwork_file, _ = get_pokemon_artwork(old_base, gender, is_shiny) if old_base else (None, False)
    artwork_img     = await fetch_artwork(artwork_file, shiny=is_shiny) if artwork_file else None

    embed = discord.Embed(
        title="✨ Your Pokémon wants to evolve!",
        description=f"**{old_poke['name']}** is evolving into **{evolved['name']}**!\nDo you want to proceed?",
        color=discord.Color.gold()
    )
    file = None
    if artwork_img:
        gif_bytes = overlay_artwork_on_gif(artwork_img)
        file      = discord.File(gif_bytes, filename="evolution.gif")
        embed.set_image(url="attachment://evolution.gif")

    view = EvolutionView(user_id=user_id, poke_index=poke_index, evolved=evolved)
    if file:
        await channel.send(embed=embed, file=file, view=view)
    else:
        await channel.send(embed=embed, view=view)


class EvolutionView(discord.ui.View):
    def __init__(self, user_id: str, poke_index: int, evolved: dict):
        super().__init__(timeout=60)
        self.user_id    = user_id
        self.poke_index = poke_index
        self.evolved    = evolved

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your evolution!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        with open(DATA_FILE) as f:
            data = json.load(f)
        data[self.user_id]["pokemon"][self.poke_index] = self.evolved
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

        new_base     = next((p for p in pokemons if p["name"] == self.evolved["name"]), None)
        artwork_file, _ = get_pokemon_artwork(new_base, self.evolved.get("gender", ""),
                                               self.evolved.get("shiny", False)) if new_base else (None, False)
        artwork_img  = await fetch_artwork(artwork_file) if artwork_file else None

        if artwork_img:
            gif_bytes = overlay_artwork_on_gif(artwork_img)
            file      = discord.File(gif_bytes, filename="evolution.gif")
            embed     = discord.Embed(
                title=f"🎉 {self.evolved['name']}!",
                description=f"Your Pokémon evolved into **{self.evolved['name']}**!",
                color=discord.Color.gold()
            )
            embed.set_image(url="attachment://evolution.gif")
            await interaction.response.send_message(embed=embed, file=file)
        else:
            await interaction.response.send_message(
                f"🎉 Your Pokémon evolved into **{self.evolved['name']}**!"
            )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Evolution cancelled.", ephemeral=True)
        self.stop()


# ── Cog ───────────────────────────────────────────────────────────────────────

class EvolutionSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="evolve")
    async def evolve(self, ctx, order_number: int = None):
        if not await check_registration(ctx):
            return
        user_id = str(ctx.author.id)
        with open(DATA_FILE) as f:
            data = json.load(f)
        user_data    = data.get(user_id, {})
        pokemon_list = user_data.get("pokemon", [])
        selected_no  = order_number or user_data.get("selected_pokemon")

        if selected_no is None or not (1 <= selected_no <= len(pokemon_list)):
            return await ctx.reply("Invalid Pokémon or none selected.")

        poke    = pokemon_list[selected_no - 1]
        evolved = get_evolved_poke(poke, user_id, trigger="level")

        if not evolved:
            return await ctx.send(f"**{poke['name']}** cannot evolve right now.")

        await send_evolution_prompt(ctx.channel, user_id, selected_no - 1, poke, evolved)


async def setup(bot):
    await bot.add_cog(EvolutionSystem(bot))