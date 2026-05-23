import discord
from discord.ext import commands
from discord.ui import View, Button, Select
from database.pokemons_database import pokemons
from utils.constants import GENDER_EMOJIS, TYPE_EMOJIS
from utils.artwork_handler import get_artwork_url, get_pokemon_artwork


# ── Helpers ─────────────────────────────────────────────────

def get_type_str(types: list) -> str:
    return "\n".join(f"{TYPE_EMOJIS.get(f'{t.lower()}_type', '')} {t}" for t in types)

def get_variants(poke_id: str) -> list[dict]:
    return [p for p in pokemons if p["id"] == poke_id]

def build_embed(entry: dict, show_shiny: bool = False) -> discord.Embed:
    name       = entry["name"]
    poke_id    = entry["id"]
    dex_entry  = entry.get("pokedex_entry", "No data.")
    evolution  = entry.get("evolution", "Does not evolve.")
    types      = entry.get("types", [])
    region     = entry.get("region", "Unknown")
    catchable  = entry.get("catchable", "Unknown")
    bs         = entry.get("base_stats", {})
    appearance = entry.get("appearance", {})
    gr         = entry.get("gender_ratio", {})
    egg_groups = entry.get("egg_group", [])
    hatch_time = entry.get("hatch_time", "Unknown")

    male_e   = GENDER_EMOJIS.get("male", "♂")
    female_e = GENDER_EMOJIS.get("female", "♀")
    male_pct   = gr.get("male", "")
    female_pct = gr.get("female", "")

    if male_pct and female_pct:
        gender_str = f"{male_e} {male_pct} {female_e} {female_pct}"
    elif male_pct:
        gender_str = f"{male_e} {male_pct}"
    else:
        gender_str = "Genderless"

    embed = discord.Embed(
        title=f"#{poke_id} — {name}",
        description=dex_entry,
        color=discord.Color.gold()
    )

    embed.add_field(name="Evolution", value=evolution, inline=False)
    embed.add_field(name="Types", value=get_type_str(types), inline=False)
    embed.add_field(name="Region", value=region, inline=True)
    embed.add_field(name="Catchable", value=catchable, inline=True)

    embed.add_field(
        name="Base Stats",
        value=(
            f"**HP:** {bs.get('hp','?')}\n"
            f"**Attack:** {bs.get('attack','?')}\n"
            f"**Defense:** {bs.get('defense','?')}\n"
            f"**Sp. Atk:** {bs.get('special_attack','?')}\n"
            f"**Sp. Def:** {bs.get('special_defense','?')}\n"
            f"**Speed:** {bs.get('speed','?')}\n"
            f"**Total: {bs.get('total','?')}**"
        ),
        inline=False
    )

    embed.add_field(
        name="Appearance",
        value=f"Height: {appearance.get('height','?')}\nWeight: {appearance.get('weight','?')}",
        inline=False
    )

    embed.add_field(name="Gender Ratio", value=gender_str, inline=False)
    embed.add_field(name="Egg Groups", value=", ".join(egg_groups) or "?", inline=True)
    embed.add_field(name="Hatch Time", value=hatch_time, inline=True)

    artwork_file       = entry.get("artwork")
    shiny_artwork_file = entry.get("shiny_artwork")
    female_artwork_file = entry.get("female_variant_artwork")

    if show_shiny and shiny_artwork_file:
        url = get_artwork_url(shiny_artwork_file, shiny=True)
    elif artwork_file:
        url = get_artwork_url(artwork_file)
    else:
        url = None

    if url:
        embed.set_image(url=url)

    return embed


POKEMON_NAMES: list[str] = [p["name"] for p in pokemons]

# ── Views ─────────────────────────────────────────────────

class PokedexView(View):
    def __init__(self, index: int, active: str, show_shiny: bool = False):
        super().__init__(timeout=120)
        self.index = index
        self.active = active
        self.show_shiny = show_shiny
        self._update_variant_options()
        self._update_buttons()

    def _entry(self):
        return next((p for p in pokemons if p["name"] == self.active), None)

    def _base_id(self):
        return next((p["id"] for p in pokemons if p["name"] == self.active), "0000")

    def _update_buttons(self):
        entry = self._entry()
        if not entry:
            return
        gr = entry.get("gender_ratio", {})
        is_genderless = "unknown" in gr

        def pct_val(key):
            val = gr.get(key, "0%")
            try:
                return float(str(val).replace("%", ""))
            except ValueError:
                return 0.0

        male_val   = pct_val("male")
        female_val = pct_val("female")

        # Re-add both first (in case they were removed previously)
        if self.male_btn not in self.children:
            self.add_item(self.male_btn)
        if self.female_btn not in self.children:
            self.add_item(self.female_btn)

        # Remove buttons that don't apply
        if is_genderless or male_val == 0.0:
            self.remove_item(self.male_btn)
        if is_genderless or female_val == 0.0:
            self.remove_item(self.female_btn)

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary, row=1)
    async def prev_btn(self, interaction, button):
        self.index = (self.index - 1) % len(POKEMON_NAMES)
        self.active = POKEMON_NAMES[self.index]
        self.show_shiny = False
        entry = self._entry()
        self._update_variant_options()
        self._update_buttons()
        await interaction.response.edit_message(embed=build_embed(entry), view=self)

    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:male:1400956267979214971>"), style=discord.ButtonStyle.primary, row=1)
    async def male_btn(self, interaction, button):
        variants = get_variants(self._base_id())
        male = next((v for v in variants if not v["name"].lower().startswith("female")), None)
        self.active = male["name"]
        self.show_shiny = False
        self._update_buttons()
        await interaction.response.edit_message(embed=build_embed(male), view=self)

    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<a:spark:1407360333043208244>"), style=discord.ButtonStyle.success, row=1)
    async def shiny_btn(self, interaction, button):
        self.show_shiny = not self.show_shiny
        entry = self._entry()
        await interaction.response.edit_message(embed=build_embed(entry, self.show_shiny), view=self)

    @discord.ui.button(emoji=discord.PartialEmoji.from_str("<:female:1400956073573224520>"), style=discord.ButtonStyle.danger, row=1)
    async def female_btn(self, interaction, button):
        variants = get_variants(self._base_id())
        female = next((v for v in variants if v["name"].lower().startswith("female")), None)
        self.active = female["name"]
        self.show_shiny = False
        self._update_buttons()
        await interaction.response.edit_message(embed=build_embed(female), view=self)

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_btn(self, interaction, button):
        self.index = (self.index + 1) % len(POKEMON_NAMES)
        self.active = POKEMON_NAMES[self.index]
        self.show_shiny = False
        entry = self._entry()
        self._update_variant_options()
        self._update_buttons()
        await interaction.response.edit_message(embed=build_embed(entry), view=self)

    @discord.ui.select(placeholder="View a variant...", row=0, min_values=1, max_values=1, options=[discord.SelectOption(label="Loading...", value="loading")])
    async def variant_select(self, interaction, select):
        chosen = select.values[0]
        entry = next((p for p in pokemons if p["name"] == chosen), None)
        self.active = chosen
        self.show_shiny = False
        self._update_variant_options()
        self._update_buttons()
        await interaction.response.edit_message(embed=build_embed(entry), view=self)

    def _update_variant_options(self):
        variants = get_variants(self._base_id())
        self.variant_select.options = [
            discord.SelectOption(label=v["name"], value=v["name"], default=(v["name"] == self.active))
            for v in variants[:25]
        ]


# ── Cog ─────────────────────────────────────────────────

class PokedexSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="pokédex", invoke_without_command=True)
    async def pokedex(self, ctx):
        await ctx.send("Usage: `@Pokékiro pokédex info <pokemon name>`")

    @pokedex.command(name="info")
    async def pokedex_info(self, ctx, *, pokemon_name: str = None):
        if not pokemon_name:
            return await ctx.send("Usage: `@Pokékiro pokédex info <pokemon name>`")

        entry = next((p for p in pokemons if p["name"].lower() == pokemon_name.lower()), None)
        if not entry:
            entry = next((p for p in pokemons if pokemon_name.lower() in p["name"].lower()), None)
        if not entry:
            return await ctx.send(f"Pokémon **{pokemon_name}** not found in Pokédex.")

        index = POKEMON_NAMES.index(entry["name"]) if entry["name"] in POKEMON_NAMES else 0

        await ctx.send(embed=build_embed(entry), view=PokedexView(index, entry["name"]))


async def setup(bot):
    await bot.add_cog(PokedexSystem(bot))