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
from utils.constants import HUNTING_ITEMS_EMOJIS, CURRENCY_EXCHANGE_AND_BALANCE, XP_BOOSTERS_AND_CANDIES_EMOJIS, EVOLUTION_ITEMS_EMOJIS, FORM_CHANGING_ITEMS_EMOJIS, HELD_ITEMS_EMOJIS, BATTLE_ITEMS_EMOJIS, NATURE_MINTS_EMOJIS
from utils.registered_checker import check_registration

INVENTORY_FILE = "data/trainers_inventory_database.json"
PAGE_SIZE = 10

PAGE_TITLES = {
    1: "Page 1 - XP Boosters & Candies",
    2: "Page 2 - Evolution Items",
    3: "Page 3 - Form Changing Items",
    4: "Page 4 - Held Items",
    5: "Page 5 - Nature Mints",
    6: "Page 6 - Hunting Items",
    7: "Page 7 - Battle Items",
    8: "Page 8 - Exclusive Items"
}

SHOP_ITEMS = {
    1: [
        {
            "key": "xp_booster_1",
            "name": "XP Booster 1",
            "emoji_key": "xp_1",
            "emoji_dict": "XP_BOOSTERS_AND_CANDIES_EMOJIS",
            "price": 10,
            "currency": "pokecoins",
            "inventory_page": 1,
        },
        {
            "key": "xp_booster_2",
            "name": "XP Booster 2",
            "emoji_key": "xp_2",
            "emoji_dict": "XP_BOOSTERS_AND_CANDIES_EMOJIS",
            "price": 20,
            "currency": "pokecoins",
            "inventory_page": 1,
        },
        {
            "key": "xp_booster_3",
            "name": "XP Booster 3",
            "emoji_key": "xp_3",
            "emoji_dict": "XP_BOOSTERS_AND_CANDIES_EMOJIS",
            "price": 30,
            "currency": "pokecoins",
            "inventory_page": 1,
        },
        {
            "key": "rare_candy",
            "name": "Rare Candy",
            "emoji_key": "rare_candy",
            "emoji_dict": "XP_BOOSTERS_AND_CANDIES_EMOJIS",
            "price": 50,
            "currency": "pokecoins",
            "inventory_page": 1,
        },
    ],
    2: [
        {"key": "reaper_cloth",     "name": "Reaper Cloth",     "emoji_key": "reaper_cloth",     "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "razor_fang",       "name": "Razor Fang",       "emoji_key": "razor_fang",       "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "dawn_stone",       "name": "Dawn Stone",       "emoji_key": "dawn_stone",       "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "dusk_stone",       "name": "Dusk Stone",       "emoji_key": "dusk_stone",       "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "fire_stone",       "name": "Fire Stone",       "emoji_key": "fire_stone",       "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "ice_stone",        "name": "Ice Stone",        "emoji_key": "ice_stone",        "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "leaf_stone",       "name": "Leaf Stone",       "emoji_key": "leaf_stone",       "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "moon_stone",       "name": "Moon Stone",       "emoji_key": "moon_stone",       "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "oval_stone",       "name": "Oval Stone",       "emoji_key": "oval_stone",       "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "everstone",        "name": "Everstone",        "emoji_key": "everstone",        "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "shiny_stone",      "name": "Shiny Stone",      "emoji_key": "shiny_stone",      "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "sun_stone",        "name": "Sun Stone",        "emoji_key": "sun_stone",        "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "thunder_stone",    "name": "Thunder Stone",    "emoji_key": "thunder_stone",    "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "water_stone",      "name": "Water Stone",      "emoji_key": "water_stone",      "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "electirizer",      "name": "Electirizer",      "emoji_key": "electirizer",      "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "protector",        "name": "Protector",        "emoji_key": "protector",        "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "magmarizer",       "name": "Magmarizer",       "emoji_key": "magmarizer",       "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "linking_cord",     "name": "Linking Cord",     "emoji_key": "linking_cord",     "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "soothe_bell",      "name": "Soothe Bell",      "emoji_key": "soothe_bell",      "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "berry_sweet",      "name": "Berry Sweet",      "emoji_key": "berry_sweet",      "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "clover_sweet",     "name": "Clover Sweet",     "emoji_key": "clover_sweet",     "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "flower_sweet",     "name": "Flower Sweet",     "emoji_key": "flower_sweet",     "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "love_sweet",       "name": "Love Sweet",       "emoji_key": "love_sweet",       "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "ribbon_sweet",     "name": "Ribbon Sweet",     "emoji_key": "ribbon_sweet",     "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "star_sweet",       "name": "Star Sweet",       "emoji_key": "star_sweet",       "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "strawberry_sweet", "name": "Strawberry Sweet", "emoji_key": "strawberry_sweet", "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "chipped_pot",      "name": "Chipped Pot",      "emoji_key": "chipped_pot",      "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "cracked_pot",      "name": "Cracked Pot",      "emoji_key": "cracked_pot",      "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "deep_sea_scale",   "name": "Deep Sea Scale",   "emoji_key": "deep_sea_scale",   "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "deep_sea_tooth",   "name": "Deep Sea Tooth",   "emoji_key": "deep_sea_tooth",   "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
        {"key": "leaders_crest",    "name": "Leader's Crest",   "emoji_key": "leaders_crest",    "emoji_dict": "EVOLUTION_ITEMS_EMOJIS", "price": 100, "currency": "pokecoins", "inventory_page": 2},
    ],
    3: [
        {"key": "rusted_sword",      "name": "Rusted Sword",      "emoji_key": "rusted_sword",      "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "rusted_shield",     "name": "Rusted Shield",     "emoji_key": "rusted_shield",     "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "red_orb",           "name": "Red Orb",           "emoji_key": "red_orb",           "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "blue_orb",          "name": "Blue Orb",          "emoji_key": "blue_orb",          "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "zygarde_cube",      "name": "Zygarde Cube",      "emoji_key": "zygarde_cube",      "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "scroll_of_darkness","name": "Scroll of Darkness","emoji_key": "scroll_of_darkness","emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "scroll_of_waters",  "name": "Scroll of Waters",  "emoji_key": "scroll_of_waters",  "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "reveal_glass",      "name": "Reveal Glass",      "emoji_key": "reveal_glass",      "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "adamant_crystal",   "name": "Adamant Crystal",   "emoji_key": "adamant_crystal",   "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "dna_splicers",      "name": "DNA Splicers",      "emoji_key": "dna_splicers",      "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "griseous_core",     "name": "Griseous Core",     "emoji_key": "griseous_core",     "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "lustrous_globe",    "name": "Lustrous Globe",    "emoji_key": "lustrous_globe",    "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "prison_bottle",     "name": "Prison Bottle",     "emoji_key": "prison_bottle",     "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "gracidea",          "name": "Gracidea",          "emoji_key": "gracidea",          "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "n_solarizer",       "name": "N-Solarizer",       "emoji_key": "n_solarizer",       "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "n_lunarizer",       "name": "N-Lunarizer",       "emoji_key": "n_lunarizer",       "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
        {"key": "reins_of_unity",    "name": "Reins of Unity",    "emoji_key": "reins_of_unity",    "emoji_dict": "FORM_CHANGING_ITEMS_EMOJIS", "price": 150, "currency": "pokecoins", "inventory_page": 3},
    ],
    4: [
        {"key": "aloraichium_z", "name": "Aloraichium Z", "emoji_key": "aloraichium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "buginium_z", "name": "Buginium Z", "emoji_key": "buginium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "darkinium_z", "name": "Darkinium Z", "emoji_key": "darkinium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "decidium_z", "name": "Decidium Z", "emoji_key": "decidium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "dragonium_z", "name": "Dragonium Z", "emoji_key": "dragonium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "eevium_z", "name": "Eevium Z", "emoji_key": "eevium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "electrium_z", "name": "Electrium Z", "emoji_key": "electrium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "fairium_z", "name": "Fairium Z", "emoji_key": "fairium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "fightinium_z", "name": "Fightinium Z", "emoji_key": "fightinium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "firium_z", "name": "Firium Z", "emoji_key": "firium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "flyinium_z", "name": "Flyinium Z", "emoji_key": "flyinium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "ghostium_z", "name": "Ghostium Z", "emoji_key": "ghostium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "grassium_z", "name": "Grassium Z", "emoji_key": "grassium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "groundium_z", "name": "Groundium Z", "emoji_key": "groundium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "icium_z", "name": "Icium Z", "emoji_key": "icium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "incinium_z", "name": "Incinium Z", "emoji_key": "incinium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "kommonium_z", "name": "Kommonium Z", "emoji_key": "kommonium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "lunalium_z", "name": "Lunalium Z", "emoji_key": "lunalium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "lycanium_z", "name": "Lycanium Z", "emoji_key": "lycanium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "marshadium_z", "name": "Marshadium Z", "emoji_key": "marshadium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "mewnium_z", "name": "Mewnium Z", "emoji_key": "mewnium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "mimikium_z", "name": "Mimikium Z", "emoji_key": "mimikium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "normalium_z", "name": "Normalium Z", "emoji_key": "normalium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "pikanium_z", "name": "Pikanium Z", "emoji_key": "pikanium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "pikashunium_z", "name": "Pikashunium Z", "emoji_key": "pikashunium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "poisonium_z", "name": "Poisonium Z", "emoji_key": "poisonium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "primarium_z", "name": "Primarium Z", "emoji_key": "primarium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "psychium_z", "name": "Psychium Z", "emoji_key": "psychium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "rockium_z", "name": "Rockium Z", "emoji_key": "rockium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "snorlium_z", "name": "Snorlium Z", "emoji_key": "snorlium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "solganium_z", "name": "Solganium Z", "emoji_key": "solganium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "steelium_z", "name": "Steelium Z", "emoji_key": "steelium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "tapunium_z", "name": "Tapunium Z", "emoji_key": "tapunium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "waterium_z", "name": "Waterium Z", "emoji_key": "waterium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "ultranecrozium_z", "name": "Ultranecrozium Z", "emoji_key": "ultranecrozium_z", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "barbaracite", "name": "Barbaracite", "emoji_key": "barbaracite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "beedrillite", "name": "Beedrillite", "emoji_key": "beedrillite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "cameruptite", "name": "Cameruptite", "emoji_key": "cameruptite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "chandelurite", "name": "Chandelurite", "emoji_key": "chandelurite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "chesnaughtite", "name": "Chesnaughtite", "emoji_key": "chesnaughtite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "clefablite", "name": "Clefablite", "emoji_key": "clefablite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "delphoxite", "name": "Delphoxite", "emoji_key": "delphoxite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "dragalgite", "name": "Dragalgite", "emoji_key": "dragalgite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "dragoninite", "name": "Dragoninite", "emoji_key": "dragoninite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "drampanite", "name": "Drampanite", "emoji_key": "drampanite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "eelektrossite", "name": "Eelektrossite", "emoji_key": "eelektrossite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "emboarite", "name": "Emboarite", "emoji_key": "emboarite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "excadrite", "name": "Excadrite", "emoji_key": "excadrite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "feraligite", "name": "Feraligite", "emoji_key": "feraligite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "floettite", "name": "Floettite", "emoji_key": "floettite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "froslassite", "name": "Froslassite", "emoji_key": "froslassite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "greninjite", "name": "Greninjite", "emoji_key": "greninjite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "hawluchanite", "name": "Hawluchanite", "emoji_key": "hawluchanite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "lopunnite", "name": "Lopunnite", "emoji_key": "lopunnite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "malamarite", "name": "Malamarite", "emoji_key": "malamarite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "meganiumite", "name": "Meganiumite", "emoji_key": "meganiumite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "pyroarite", "name": "Pyroarite", "emoji_key": "pyroarite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "salamencite", "name": "Salamencite", "emoji_key": "salamencite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "scolipite", "name": "Scolipite", "emoji_key": "scolipite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "scraftinite", "name": "Scraftinite", "emoji_key": "scraftinite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "skarmorite", "name": "Skarmorite", "emoji_key": "skarmorite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "starminite", "name": "Starminite", "emoji_key": "starminite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "victreebelite", "name": "Victreebelite", "emoji_key": "victreebelite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "zygardite", "name": "Zygardite", "emoji_key": "zygardite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "blazikenite", "name": "Blazikenite", "emoji_key": "blazikenite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "falinksite", "name": "Falinksite", "emoji_key": "falinksite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "latiasite", "name": "Latiasite", "emoji_key": "latiasite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "latiosite", "name": "Latiosite", "emoji_key": "latiosite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "raichunite_x", "name": "Raichunite X", "emoji_key": "raichunite_x", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "raichunite_y", "name": "Raichunite Y", "emoji_key": "raichunite_y", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "sceptilite", "name": "Sceptilite", "emoji_key": "sceptilite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "swampertite", "name": "Swampertite", "emoji_key": "swampertite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "abomasite", "name": "Abomasite", "emoji_key": "abomasite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "absolite", "name": "Absolite", "emoji_key": "absolite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "aerodactylite", "name": "Aerodactylite", "emoji_key": "aerodactylite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "aggronite", "name": "Aggronite", "emoji_key": "aggronite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "alakazite", "name": "Alakazite", "emoji_key": "alakazite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "altarianite", "name": "Altarianite", "emoji_key": "altarianite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "ampharosite", "name": "Ampharosite", "emoji_key": "ampharosite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "audinite", "name": "Audinite", "emoji_key": "audinite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "banettite", "name": "Banettite", "emoji_key": "banettite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "blastoisinite", "name": "Blastoisinite", "emoji_key": "blastoisinite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "charizardite_x", "name": "Charizardite X", "emoji_key": "charizardite_x", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "charizardite_y", "name": "Charizardite Y", "emoji_key": "charizardite_y", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "diancite", "name": "Diancite", "emoji_key": "diancite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "galladite", "name": "Galladite", "emoji_key": "galladite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "gardevoirite", "name": "Gardevoirite", "emoji_key": "gardevoirite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "garchompite", "name": "Garchompite", "emoji_key": "garchompite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "gengarite", "name": "Gengarite", "emoji_key": "gengarite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "glalitie", "name": "Glalitie", "emoji_key": "glalitie", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "gyaradosite", "name": "Gyaradosite", "emoji_key": "gyaradosite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "heracronite", "name": "Heracronite", "emoji_key": "heracronite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "houndoomnite", "name": "Houndoomnite", "emoji_key": "houndoomnite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "kangaskhanite", "name": "Kangaskhanite", "emoji_key": "kangaskhanite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "lucarionite", "name": "Lucarionite", "emoji_key": "lucarionite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "manectite", "name": "Manectite", "emoji_key": "manectite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "mawilite", "name": "Mawilite", "emoji_key": "mawilite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "medichamnite", "name": "Medichamnite", "emoji_key": "medichamnite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "metagrossite", "name": "Metagrossite", "emoji_key": "metagrossite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "mewtwonite_x", "name": "Mewtwonite X", "emoji_key": "mewtwonite_x", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "mewtwonite_y", "name": "Mewtwonite Y", "emoji_key": "mewtwonite_y", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "pidgeotite", "name": "Pidgeotite", "emoji_key": "pidgeotite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "pinsirite", "name": "Pinsirite", "emoji_key": "pinsirite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "sablenite", "name": "Sablenite", "emoji_key": "sablenite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "scizorite", "name": "Scizorite", "emoji_key": "scizorite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "sharpedonite", "name": "Sharpedonite", "emoji_key": "sharpedonite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "slowbronite", "name": "Slowbronite", "emoji_key": "slowbronite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "steelixite", "name": "Steelixite", "emoji_key": "steelixite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "tyranitarite", "name": "Tyranitarite", "emoji_key": "tyranitarite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
        {"key": "venusaurite", "name": "Venusaurite", "emoji_key": "venusaurite", "emoji_dict": "HELD_ITEMS_EMOJIS", "price": 200, "currency": "pokecoins", "inventory_page": 4},
    ],
    7: [
        {"key": "dynamax_band", "name": "Dynamax Band", "emoji_key": "dynamax_band", "emoji_dict": "BATTLE_ITEMS_EMOJIS", "price": 250, "currency": "pokecoins", "inventory_page": 7},
        {"key": "mega_ring",    "name": "Mega Ring",    "emoji_key": "mega_ring",    "emoji_dict": "BATTLE_ITEMS_EMOJIS", "price": 250, "currency": "pokecoins", "inventory_page": 7},
        {"key": "zpower_ring",  "name": "Z-Power Ring", "emoji_key": "zpower_ring",  "emoji_dict": "BATTLE_ITEMS_EMOJIS", "price": 250, "currency": "pokecoins", "inventory_page": 7},
    ],
    5: [
        {"key": "adamant_mint", "name": "Adamant Mint", "emoji_key": "adamant_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "bold_mint", "name": "Bold Mint", "emoji_key": "bold_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "brave_mint", "name": "Brave Mint", "emoji_key": "brave_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "calm_mint", "name": "Calm Mint", "emoji_key": "calm_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "careful_mint", "name": "Careful Mint", "emoji_key": "careful_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "gentle_mint", "name": "Gentle Mint", "emoji_key": "gentle_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "impish_mint", "name": "Impish Mint", "emoji_key": "impish_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "lax_mint", "name": "Lax Mint", "emoji_key": "lax_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "lonely_mint", "name": "Lonely Mint", "emoji_key": "lonely_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "mild_mint", "name": "Mild Mint", "emoji_key": "mild_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "modest_mint", "name": "Modest Mint", "emoji_key": "modest_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "naughty_mint", "name": "Naughty Mint", "emoji_key": "naughty_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "quiet_mint", "name": "Quiet Mint", "emoji_key": "quiet_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "rash_mint", "name": "Rash Mint", "emoji_key": "rash_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "relaxed_mint", "name": "Relaxed Mint", "emoji_key": "relaxed_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "sassy_mint", "name": "Sassy Mint", "emoji_key": "sassy_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "serious_mint", "name": "Serious Mint", "emoji_key": "serious_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "docile_mint", "name": "Docile Mint", "emoji_key": "docile_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "jolly_mint", "name": "Jolly Mint", "emoji_key": "jolly_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "naive_mint", "name": "Naive Mint", "emoji_key": "naive_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
        {"key": "timid_mint", "name": "Timid Mint", "emoji_key": "timid_mint", "emoji_dict": "NATURE_MINTS_EMOJIS", "price": 50, "currency": "pokecoins", "inventory_page": 5},
    ],
    6: [
        {"key": "incense", "name": "Incense (default, customizable)", "emoji_key": "incense", "emoji_dict": "HUNTING_ITEMS_EMOJIS", "price": 50, "currency": "shards", "inventory_page": 6},
        {"key": "shiny_charm",     "name": "Shiny Charm",     "emoji_key": "shiny_charm",     "emoji_dict": "HUNTING_ITEMS_EMOJIS", "price": 100, "currency": "shards", "inventory_page": 6},
        {"key": "oval_charm",      "name": "Oval Charm",      "emoji_key": "oval_charm",      "emoji_dict": "HUNTING_ITEMS_EMOJIS", "price": 70,  "currency": "shards", "inventory_page": 6},
        {"key": "summoning_stone", "name": "Summoning Stone", "emoji_key": "summoning_stone", "emoji_dict": "HUNTING_ITEMS_EMOJIS", "price": 100, "currency": "shards", "inventory_page": 6},
    ],
    8: [
        {"key": "shards", "name": "Shards", "emoji_key": "shard", "emoji_dict": "CURRENCY_EXCHANGE_AND_BALANCE", "price": 200, "currency": "pokecoins", "inventory_page": 8},
    ],
}

CURRENCY_LABEL = {
    "shards": "Shards",
    "pokecoins": "Pokécoins",
}

def get_emoji(item: dict) -> str:
    from utils import constants as _c
    d = getattr(_c, item["emoji_dict"])
    return d.get(item["emoji_key"], "")

def make_embed(title: str, user) -> discord.Embed:
    embed = discord.Embed(title=title, color=discord.Color.gold())
    embed.set_author(name=user.name, icon_url=user.display_avatar.url)
    return embed

def build_shop_item_pages(page: int, user) -> list:
    items = SHOP_ITEMS.get(page, [])
    total_items = len(items)

    if total_items == 0:
        embed = make_embed(PAGE_TITLES[page], user)
        embed.description = f"Total items: **{total_items}**"
        return [embed]

    pages = []
    for i in range(0, total_items, PAGE_SIZE):
        embed = make_embed(PAGE_TITLES[page], user)
        lines = []
        for idx, item in enumerate(items[i:i + PAGE_SIZE], start=i + 1):
            emoji = get_emoji(item)
            currency_label = CURRENCY_LABEL.get(item["currency"], item["currency"])
            lines.append(f"`{idx}`    {emoji} **{item['name']}**\n\u200b    {item['price']} {currency_label} each")
        embed.description = f"Total items: **{total_items}**\n\n" + "\n\n".join(lines)
        embed.set_footer(text=f"Showing {i+1}-{min(i+PAGE_SIZE, total_items)} of {total_items}")
        pages.append(embed)

    return pages

def find_item(name: str):
    for page_items in SHOP_ITEMS.values():
        for item in page_items:
            if item["name"].lower() == name.lower():
                return item
    return None

class PurchaseConfirmView(discord.ui.View):
    def __init__(self, ctx, item: dict, amount: int, reply_msg):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.item = item
        self.amount = amount
        self.reply_msg = reply_msg
        self.btn_msg = None
        self.done = False

    async def on_timeout(self):
        if not self.done:
            self.done = True
            try:
                await self.reply_msg.edit(content="Aborted.")
                await self.btn_msg.delete()
            except Exception:
                pass

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your purchase!", ephemeral=True)

        self.done = True
        self.stop()

        item = self.item
        amount = self.amount
        total_cost = item["price"] * amount
        currency = item["currency"]
        emoji = get_emoji(item)
        currency_label = CURRENCY_LABEL.get(currency, currency)

        with open(INVENTORY_FILE, "r") as f:
            inv_data = json.load(f)

        user_inv = inv_data.get(str(interaction.user.id), {})
        current_balance = user_inv.get(currency, 0)

        if current_balance < total_cost:
            await self.reply_msg.edit(content=f"You don't have enough **{currency_label}** for that!", view=None)
            await self.btn_msg.delete()
            await interaction.response.defer()
            return

        user_inv[currency] = current_balance - total_cost

        items_dict = user_inv.setdefault("items", {})
        items_dict[item["name"]] = items_dict.get(item["name"], 0) + amount

        inv_data[str(interaction.user.id)] = user_inv
        with open(INVENTORY_FILE, "w") as f:
            json.dump(inv_data, f, indent=4)

        await self.reply_msg.edit(content=f"You purchased {amount} {item['name']} {emoji}!")
        await self.btn_msg.delete()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your purchase!", ephemeral=True)

        self.done = True
        self.stop()
        await self.reply_msg.edit(content="Purchasing cancelled.")
        await self.btn_msg.delete()
        await interaction.response.defer()

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user_inv(self, user_id):
        if not os.path.exists(INVENTORY_FILE):
            return None
        with open(INVENTORY_FILE, "r") as f:
            data = json.load(f)
        return data.get(str(user_id))

    @commands.command()
    async def shop(self, ctx, page: int = None):
        if not await check_registration(ctx):
            return

        if page in range(1, 9):
            return await self.show_page(ctx, page)

        embed = make_embed("Pokékiro Shop", ctx.author)
        embed.description = (
            "Use `@Pokékiro#4959 shop <page>` to view different pages.\n\n"
            "Page 1\nXP Boosters & Candies\n\n"
            "Page 2\nEvolution Items\n\n"
            "Page 3\nForm Changing Items\n\n"
            "Page 4\nHeld Items\n\n"
            "Page 5\nNature Mints\n\n"
            "Page 6\nHunting Items\n\n"
            "Page 7\nBattle Items\n\n"
            "Page 8\nExclusive Items"
        )
        await ctx.send(embed=embed, view=ShopPageSelect(ctx, None))

    async def show_page(self, ctx, page):
        pages = build_shop_item_pages(page, ctx.author)
        view = ShopPageSelect(ctx, page)
        if len(pages) > 1:
            msg = await ctx.send(embed=pages[0], view=view)
            await msg.edit(view=Paginator(ctx, pages))
        else:
            await ctx.send(embed=pages[0], view=view)

    async def show_currency_exchange(self, ctx):
        embed = make_embed(PAGE_TITLES[8], ctx.author)
        embed.description = ""
        await ctx.send(embed=embed, view=ShopPageSelect(ctx, 8))

    @commands.command()
    async def buy(self, ctx, *, args: str = None):
        if not await check_registration(ctx):
            return

        if not args:
            return await ctx.reply("Usage: `@Pokékiro#4959 buy <item name> <amount>`")

        parts = args.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdigit():
            item_name = parts[0].strip()
            amount = int(parts[1])
        else:
            item_name = args.strip()
            amount = 1

        if amount < 1:
            return await ctx.reply("Amount must be at least 1.")

        item = find_item(item_name)
        if not item:
            return await ctx.reply(f"Item **{item_name}** not found in the shop.")

        if item["key"] == "incense":
            from cogs.spawn_system import IncenseSettingsView, calc_incense
            user_inv = self.get_user_inv(ctx.author.id) or {}
            shards = user_inv.get("shards", 0)
            default_price = calc_incense("1h", "20s")[1]
            if shards < default_price:
                return await ctx.reply(
                    f"You don't have enough Shards! Default incense costs **{default_price}** Shards but you only have **{shards}**. Nikal gareeb 🤡"
                )
            view = IncenseSettingsView(ctx, timeout=60)
            msg = await ctx.reply(view._get_content(), view=view)
            view.msg = msg
            return

        confirm_items = {"shards", "summoning_stone", "oval_charm", "shiny_charm", "incense"}
        if item["key"] not in confirm_items:
            user_inv = self.get_user_inv(ctx.author.id) or {}
            currency = item["currency"]
            currency_label = CURRENCY_LABEL.get(currency, currency)
            total_cost = item["price"] * amount

            if user_inv.get(currency, 0) < total_cost:
                return await ctx.reply(f"You don't have enough **{currency_label}** for that!")

            user_inv[currency] = user_inv.get(currency, 0) - total_cost
            if item["key"] == "shards":
                user_inv["shards"] = user_inv.get("shards", 0) + amount
            else:
                items_dict = user_inv.setdefault("items", {})
                items_dict[item["name"]] = items_dict.get(item["name"], 0) + amount

            with open(INVENTORY_FILE, "r") as f:
                inv_data = json.load(f)
            inv_data[str(ctx.author.id)] = user_inv
            with open(INVENTORY_FILE, "w") as f:
                json.dump(inv_data, f, indent=4)

            emoji = get_emoji(item)
            return await ctx.reply(f"You purchased {amount} {item['name']} {emoji}!")

        user_inv = self.get_user_inv(ctx.author.id) or {}
        currency = item["currency"]
        currency_label = CURRENCY_LABEL.get(currency, currency)
        total_cost = item["price"] * amount

        if user_inv.get(currency, 0) < total_cost:
            return await ctx.reply(f"You don't have enough **{currency_label}** for that!")

        emoji = get_emoji(item)
        confirm_text = f"Are you sure? You want to purchase {emoji} **{item['name']}** **{amount}**"

        reply_msg = await ctx.reply(confirm_text)
        view = PurchaseConfirmView(ctx, item, amount, reply_msg)
        btn_msg = await ctx.send(view=view)
        view.btn_msg = btn_msg

class ShopPageSelect(discord.ui.View):
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
                8: "Exclusive Items"
            }.items()
        ]
        select = discord.ui.Select(placeholder="Open a page", options=options)
        select.callback = self.callback
        self.add_item(select)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your shop!", ephemeral=True)

        page = int(interaction.data['values'][0]) if interaction.data and 'values' in interaction.data else 1

        if page in range(1, 9):
            pages = build_shop_item_pages(page, interaction.user)
            view = ShopPageSelect(self.ctx, page)
            if len(pages) > 1:
                await interaction.response.send_message(embed=pages[0], view=view)
                msg = await interaction.original_response()
                await msg.edit(view=Paginator(self.ctx, pages))
            else:
                await interaction.response.send_message(embed=pages[0], view=view)

async def setup(bot):
    await bot.add_cog(Shop(bot))
