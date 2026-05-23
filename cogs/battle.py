import discord
from discord.ui import Button, View, Select
from discord.ext import commands
import asyncio
from typing import Dict
import random
import json
import os
from datetime import datetime

from database.moves_database import POKEMON_MOVES
from utils.registered_checker import check_registration
from utils.constants import GENDER_EMOJIS, TYPE_EMOJIS
from database.pokemons_database import pokemons
from cogs.friendship_system import load_collection, save_collection, ensure_friendship_points, add_friendship_points
from utils.artwork_handler import get_artwork_url, get_pokemon_artwork

DATA_FILE      = "data/trainers_collection_database.json"
INVENTORY_FILE = "data/trainers_inventory_database.json"
BATTLE_DB_FILE = "data/battling_database.json"

battles: Dict[int, dict]           = {}
pending_challenges: Dict[int, dict] = {}


# ── File I/O ──────────────────────────────────────────────────────────────────

def load_collection() -> dict:
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_collection(data: dict):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving collection: {e}")

def load_battle_db() -> dict:
    try:
        if os.path.exists(BATTLE_DB_FILE):
            with open(BATTLE_DB_FILE, "r") as f:
                return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"battles": []}

def save_battle_db(data: dict) -> bool:
    os.makedirs("data", exist_ok=True)
    try:
        with open(BATTLE_DB_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving battles: {e}")
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_registered(user_id) -> bool:
    return str(user_id) in load_collection()

def get_trainer_data(user_id) -> dict | None:
    return load_collection().get(str(user_id))

def get_pokemon_by_order(trainer_data: dict, order_number: int) -> dict | None:
    pokemon_list = trainer_data.get("pokemon", [])
    if 1 <= order_number <= len(pokemon_list):
        return pokemon_list[order_number - 1]
    return None

def format_gender(gender) -> str:
    g = str(gender).lower().strip()
    if g in ("male", "♂", "m"):   return GENDER_EMOJIS.get("male", "♂")
    if g in ("female", "♀", "f"): return GENDER_EMOJIS.get("female", "♀")
    return GENDER_EMOJIS.get("unknown", "")

def get_type_emoji(move_type: str) -> str:
    key = f"{move_type.lower()}_type"
    return TYPE_EMOJIS.get(key) or TYPE_EMOJIS.get("normal_type", "")


def _get_friendship_reward_embed(user, pokemon: dict, gained: int, order_number: int) -> discord.Embed:
    ensure_friendship_points(pokemon)
    name = pokemon.get("name", "Pokémon")
    level = pokemon.get("level", 1)
    stats = pokemon.get("stats", {})
    total_iv = float(stats.get("total_iv_percent", 0))
    gender = format_gender(pokemon.get("gender", "unknown"))

    db_p = next((p for p in pokemons if p["name"].lower() == str(name).lower()), None)
    artwork_file, _ = get_pokemon_artwork(db_p, pokemon.get("gender", ""), bool(pokemon.get("shiny", False))) if db_p else (None, False)
    artwork_url = get_artwork_url(artwork_file, shiny=bool(pokemon.get("shiny", False))) if artwork_file else None

    embed = discord.Embed(color=discord.Color.gold())
    embed.description = (
        f"Your **Level {level} {name}** {gender} **({total_iv:.2f}%) No. {order_number}** "
        f"gained **{gained} Friendship Points**."
    )
    if artwork_url:
        embed.set_author(name=f"{user.display_name}'s Pokémon", icon_url=artwork_url)
        embed.set_thumbnail(url=artwork_url)
    return embed

def get_pokemon_iv(poke: dict) -> float:
    return poke.get("stats", {}).get("total_iv_percent", 0)

def get_calculated_stats(poke: dict) -> dict:
    stats = poke.get("stats", {})
    return {
        "hp":         int(stats.get("hp", 50)),
        "attack":     int(stats.get("attack", 50)),
        "defense":    int(stats.get("defense", 50)),
        "sp_attack":  int(stats.get("special_attack", 50)),
        "sp_defense": int(stats.get("special_defense", 50)),
        "speed":      int(stats.get("speed", 50)),
    }


# ── Battle DB ─────────────────────────────────────────────────────────────────

def record_battle(challenger, opponent, challenger_party, opponent_party,
                  winner_id=None, loser_id=None, battle_format="1v1", status="active"):
    db = load_battle_db()

    def fmt_party(party):
        return [
            f"Lvl. {p['level']} {p.get('iv', 0)}% {p['name']} {format_gender(p.get('gender','unknown'))} "
            f"• {p.get('hp', 0)}/{p.get('max_hp', 0)} HP"
            for p in party
        ]

    c_id = str(challenger.id)
    o_id = str(opponent.id)

    entry = {
        "trainers":           [c_id, o_id],
        f"{c_id}_pokemons":   fmt_party(challenger_party),
        f"{o_id}_pokemons":   fmt_party(opponent_party),
        "winner_id":          winner_id,
        "loser_id":           loser_id,
        "format":             battle_format,
        "status":             status,
        "date":               datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    db["battles"].append(entry)
    save_battle_db(db)

def update_battle_result(challenger_id: str, opponent_id: str,
                         winner_id: str, loser_id: str):
    db = load_battle_db()
    for battle in reversed(db.get("battles", [])):
        if (battle.get("status") == "active" and
                set(battle.get("trainers", [])) == {challenger_id, opponent_id}):
            battle["status"]    = "inactive"
            battle["winner_id"] = winner_id
            battle["loser_id"]  = loser_id
            break
    save_battle_db(db)


# ── Type Effectiveness ────────────────────────────────────────────────────────

TYPE_EFFECTIVENESS = {
    "Normal":   {"Rock": 0.5, "Steel": 0.5, "Ghost": 0},
    "Fire":     {"Grass": 2.0, "Ice": 2.0, "Bug": 2.0, "Steel": 2.0,
                 "Water": 0.5, "Rock": 0.5, "Fire": 0.5, "Dragon": 0.5},
    "Water":    {"Fire": 2.0, "Ground": 2.0, "Rock": 2.0,
                 "Grass": 0.5, "Water": 0.5, "Dragon": 0.5},
    "Electric": {"Water": 2.0, "Flying": 2.0,
                 "Electric": 0.5, "Grass": 0.5, "Dragon": 0.5, "Ground": 0},
    "Grass":    {"Water": 2.0, "Ground": 2.0, "Rock": 2.0,
                 "Fire": 0.5, "Grass": 0.5, "Poison": 0.5, "Flying": 0.5,
                 "Bug": 0.5, "Dragon": 0.5, "Steel": 0.5},
    "Ice":      {"Grass": 2.0, "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0,
                 "Fire": 0.5, "Water": 0.5, "Ice": 0.5, "Steel": 0.5},
    "Fighting": {"Normal": 2.0, "Ice": 2.0, "Rock": 2.0, "Dark": 2.0, "Steel": 2.0,
                 "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5,
                 "Fairy": 0.5, "Ghost": 0},
    "Poison":   {"Grass": 2.0, "Fairy": 2.0,
                 "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0},
    "Ground":   {"Fire": 2.0, "Electric": 2.0, "Poison": 2.0, "Rock": 2.0, "Steel": 2.0,
                 "Grass": 0.5, "Bug": 0.5, "Flying": 0},
    "Flying":   {"Grass": 2.0, "Fighting": 2.0, "Bug": 2.0,
                 "Electric": 0.5, "Rock": 0.5, "Steel": 0.5},
    "Psychic":  {"Fighting": 2.0, "Poison": 2.0,
                 "Psychic": 0.5, "Steel": 0.5, "Dark": 0},
    "Bug":      {"Grass": 2.0, "Psychic": 2.0, "Dark": 2.0,
                 "Fire": 0.5, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5,
                 "Ghost": 0.5, "Steel": 0.5, "Fairy": 0.5},
    "Rock":     {"Fire": 2.0, "Ice": 2.0, "Flying": 2.0, "Bug": 2.0,
                 "Fighting": 0.5, "Ground": 0.5, "Steel": 0.5},
    "Ghost":    {"Psychic": 2.0, "Ghost": 2.0,
                 "Dark": 0.5, "Normal": 0},
    "Dragon":   {"Dragon": 2.0, "Steel": 0.5, "Fairy": 0},
    "Dark":     {"Psychic": 2.0, "Ghost": 2.0,
                 "Fighting": 0.5, "Dark": 0.5, "Fairy": 0.5},
    "Steel":    {"Ice": 2.0, "Rock": 2.0, "Fairy": 2.0,
                 "Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Steel": 0.5},
    "Fairy":    {"Fighting": 2.0, "Dragon": 2.0, "Dark": 2.0,
                 "Fire": 0.5, "Poison": 0.5, "Steel": 0.5},
}


# ── Damage Calculation ────────────────────────────────────────────────────────

def calculate_damage(attacker: dict, defender: dict, move_name: str) -> int:
    try:
        from utils.abilities_natures import apply_ability_effect
    except ImportError:
        def apply_ability_effect(ability, effect_type, **kwargs):
            return kwargs.get("default_value", 1.0)

    move_data = POKEMON_MOVES.get(move_name.lower().replace(" ", "-"), {})
    if not move_data or move_data.get("power") in ("—", None, 0):
        return 0

    try:
        power = int(move_data.get("power", 50))
    except (ValueError, TypeError):
        return 0

    move_type  = move_data.get("type", "Normal")
    move_class = move_data.get("class", "Physical")

    attacker_stats   = attacker.get("calculated_stats", {})
    defender_stats   = defender.get("calculated_stats", {})
    level            = attacker.get("level", 1)
    attacker_ability = attacker.get("full_data", {}).get("ability", "")
    defender_ability = defender.get("full_data", {}).get("ability", "")

    if move_class == "Physical":
        attack  = attacker_stats.get("attack", 50)
        defense = defender_stats.get("defense", 50)
        attack  = attack * apply_ability_effect(attacker_ability, "stat_modifier",
                                                stat="attack", default_value=1.0)
        defense = defense * apply_ability_effect(defender_ability, "stat_modifier",
                                                 stat="defense", default_value=1.0)
    else:
        attack  = attacker_stats.get("sp_attack", 50)
        defense = defender_stats.get("sp_defense", 50)

    defense = max(defense, 1)
    damage  = ((((2 * level / 5) + 2) * power * (attack / defense)) / 50) + 2

    # STAB
    if move_type in attacker.get("type", []):
        damage *= 1.5

    # Type effectiveness
    defender_types  = defender.get("type", ["Normal"])
    effectiveness   = 1.0
    if move_type in TYPE_EFFECTIVENESS:
        for def_type in defender_types:
            effectiveness *= TYPE_EFFECTIVENESS[move_type].get(def_type, 1.0)

    is_super_effective = effectiveness > 1.0

    # Ability immunities
    if defender_ability == "Levitate" and move_type == "Ground":
        return 0
    if defender_ability == "Wonder Guard" and effectiveness <= 1.0:
        return 0

    damage *= effectiveness

    damage = apply_ability_effect(
        attacker_ability, "damage_modifier",
        attacker=attacker, defender=defender,
        move_data=move_data, damage=damage, default_value=damage
    )

    defender_hp     = defender.get("hp", 0)
    defender_max_hp = defender.get("max_hp", 1)
    damage_reduction = apply_ability_effect(
        defender_ability, "damage_taken_modifier",
        move_type=move_type, is_super_effective=is_super_effective,
        defender_hp=defender_hp, defender_max_hp=defender_max_hp,
        default_value=1.0
    )
    damage *= damage_reduction

    # Sturdy
    if defender_ability == "Sturdy" and defender_hp == defender_max_hp and damage >= defender_hp:
        damage = defender_hp - 1

    # Critical hit (1/24 chance, 1.5x)
    if random.randint(1, 24) == 1:
        damage *= 1.5

    damage = max(1, int(damage * random.uniform(0.85, 1.0)))
    return damage


# ── Ability Triggers ──────────────────────────────────────────────────────────

async def trigger_switch_abilities(battle: dict):
    try:
        from utils.abilities_natures import ABILITY_EFFECTS
    except ImportError:
        ABILITY_EFFECTS = {}

    messages = []
    c = battle["challenger_party"][battle["challenger_current_idx"]]
    o = battle["opponent_party"][battle["opponent_current_idx"]]

    for attacker, defender in [(c, o), (o, c)]:
        ability = attacker.get("full_data", {}).get("ability", "")
        if ability not in ABILITY_EFFECTS:
            continue
        ability_data = ABILITY_EFFECTS[ability]
        if ability_data.get("type") != "on_switch_in":
            continue
        effect = ability_data.get("effect")

        for poke in (attacker, defender):
            poke.setdefault("stat_changes", {})

        if effect == "lower_opponent_attack":
            messages.append(f"**{attacker['name']}'s Intimidate lowered {defender['name']}'s Attack!**")
            defender["stat_changes"]["attack"] = defender["stat_changes"].get("attack", 0) - 1
        elif effect == "raise_defense":
            messages.append(f"**{attacker['name']}'s Dauntless Shield raised its Defense!**")
            attacker["stat_changes"]["defense"] = attacker["stat_changes"].get("defense", 0) + 1
        elif effect == "raise_attack":
            messages.append(f"**{attacker['name']}'s Intrepid Sword raised its Attack!**")
            attacker["stat_changes"]["attack"] = attacker["stat_changes"].get("attack", 0) + 1
        elif effect == "download":
            opp_def   = defender.get("calculated_stats", {}).get("defense", 50)
            opp_spdef = defender.get("calculated_stats", {}).get("sp_defense", 50)
            if opp_def < opp_spdef:
                messages.append(f"**{attacker['name']}'s Download raised its Attack!**")
                attacker["stat_changes"]["attack"] = attacker["stat_changes"].get("attack", 0) + 1
            else:
                messages.append(f"**{attacker['name']}'s Download raised its Sp. Atk!**")
                attacker["stat_changes"]["sp_attack"] = attacker["stat_changes"].get("sp_attack", 0) + 1

        weather_map = {
            "Drizzle": "rain", "Drought": "harsh sunlight",
            "Sand Stream": "sandstorm", "Snow Warning": "snow",
            "Electric Surge": "Electric Terrain", "Grassy Surge": "Grassy Terrain",
            "Misty Surge": "Misty Terrain", "Psychic Surge": "Psychic Terrain",
        }
        if ability in weather_map:
            weather = weather_map[ability]
            battle["weather"] = weather
            messages.append(f"**{attacker['name']}'s {ability} created {weather}!**")

    if messages:
        await battle["channel"].send("\n".join(messages))


async def trigger_contact_abilities(attacker: dict, defender: dict,
                                    move_data: dict, battle: dict) -> list:
    messages = []
    if not move_data.get("contact", True):
        return messages

    defender_ability = defender.get("full_data", {}).get("ability", "")

    if defender_ability == "Static" and random.random() < 0.3:
        if not attacker.get("status"):
            attacker["status"] = "paralyzed"
            messages.append(f"**{attacker['name']} was paralyzed by {defender['name']}'s Static!**")
    elif defender_ability == "Flame Body" and random.random() < 0.3:
        if not attacker.get("status"):
            attacker["status"] = "burned"
            messages.append(f"**{attacker['name']} was burned by {defender['name']}'s Flame Body!**")
    elif defender_ability == "Poison Point" and random.random() < 0.3:
        if not attacker.get("status"):
            attacker["status"] = "poisoned"
            messages.append(f"**{attacker['name']} was poisoned by {defender['name']}'s Poison Point!**")
    elif defender_ability in ("Rough Skin", "Iron Barbs"):
        recoil = max(1, int(attacker.get("max_hp", 100) * 0.125))
        attacker["hp"] = max(0, attacker.get("hp", 0) - recoil)
        messages.append(
            f"**{attacker['name']} was hurt by {defender['name']}'s {defender_ability}!** ({recoil} damage)"
        )

    return messages


# ── Battle Action View ────────────────────────────────────────────────────────

class BattleActionView(View):
    def __init__(self, battle: dict, user, pokemon_data: dict, timeout=20):
        super().__init__(timeout=timeout)
        self.battle       = battle
        self.user         = user
        self.pokemon_data = pokemon_data
        self.selected_action = None

        full = pokemon_data.get("full_data", pokemon_data)
        learned_moves = (
            full.get("current_moves") or full.get("learned_moves") or
            pokemon_data.get("current_moves") or pokemon_data.get("learned_moves") or []
        )

        move_options = []
        for move_name in learned_moves[:4]:
            move_data = POKEMON_MOVES.get(move_name.lower().replace(" ", "-"), {})
            move_type = move_data.get("type", "Normal")
            power     = move_data.get("power", "—")
            move_options.append(discord.SelectOption(
                label=move_data.get("name", move_name),
                value=move_name,
                description=f"{move_type} | Power: {power}",
                emoji=get_type_emoji(move_type) or None
            ))

        if not move_options:
            move_options.append(discord.SelectOption(
                label="Struggle", value="Struggle",
                description="No moves — uses Struggle", emoji=None
            ))

        move_select = Select(
            placeholder="Use a Move",
            options=move_options,
            custom_id="move_select",
            disabled=(len(learned_moves) == 0)
        )
        move_select.callback = self.move_callback
        self.add_item(move_select)

        user_party   = self._get_party()
        current_idx  = self._get_current_idx()
        available    = [
            (i, p) for i, p in enumerate(user_party)
            if i != current_idx and p.get("hp", 0) > 0
        ]

        switch_options = [
            discord.SelectOption(
                label=f"{p['name']} (Lvl. {p['level']})",
                value=str(i),
                description=f"HP: {p['hp']}/{p['max_hp']} | IV: {p.get('iv',0)}%"
            )
            for i, p in available
        ] or [discord.SelectOption(
            label="No Pokémon available", value="none",
            description="No other Pokémon can battle"
        )]

        switch_select = Select(
            placeholder="Switch Pokémon",
            options=switch_options,
            custom_id="switch_select",
            disabled=(len(available) == 0)
        )
        switch_select.callback = self.switch_callback
        self.add_item(switch_select)

        flee_btn = Button(label="Flee", style=discord.ButtonStyle.danger, custom_id="flee")
        flee_btn.callback = self.flee_callback
        self.add_item(flee_btn)

        pass_btn = Button(label="Pass", style=discord.ButtonStyle.secondary, custom_id="pass")
        pass_btn.callback = self.pass_callback
        self.add_item(pass_btn)

    def _get_party(self):
        if self.user.id == self.battle["challenger"].id:
            return self.battle["challenger_party"]
        return self.battle["opponent_party"]
 
    def _get_current_idx(self):
        if self.user.id == self.battle["challenger"].id:
            return self.battle.get("challenger_current_idx", 0)
        return self.battle.get("opponent_current_idx", 0)

    def _set_action(self, action: dict):
        self.selected_action = action
        if self.user.id == self.battle["challenger"].id:
            self.battle["challenger_action"] = action
        else:
            self.battle["opponent_action"] = action

    async def on_timeout(self):
        if self.selected_action is None:
            self._set_action({"type": "auto_pass"})

    async def move_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("This is not your battle!", ephemeral=True)
        if self.selected_action:
            return await interaction.response.send_message("You already selected an action!", ephemeral=True)
        move_name = interaction.data["values"][0]
        if move_name == "none":
            return await interaction.response.send_message("No moves available!", ephemeral=True)
        self._set_action({"type": "move", "move": move_name})
        await interaction.response.send_message(f"You selected **{move_name}**!", ephemeral=True)
        self.stop()

    async def switch_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("This is not your battle!", ephemeral=True)
        if self.selected_action:
            return await interaction.response.send_message("You already selected an action!", ephemeral=True)
        value = interaction.data["values"][0]
        if value == "none":
            return await interaction.response.send_message("No Pokémon available to switch!", ephemeral=True)
        idx = int(value)
        self._set_action({"type": "switch", "index": idx})
        pokemon_name = self._get_party()[idx]["name"]
        await interaction.response.send_message(f"You selected to switch to **{pokemon_name}**!", ephemeral=True)
        self.stop()

    async def flee_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("This is not your battle!", ephemeral=True)
        if self.selected_action:
            return await interaction.response.send_message("You already selected an action!", ephemeral=True)
        self._set_action({"type": "flee"})
        await interaction.response.send_message("You fled from the battle!", ephemeral=True)
        self.stop()

    async def pass_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("This is not your battle!", ephemeral=True)
        if self.selected_action:
            return await interaction.response.send_message("You already selected an action!", ephemeral=True)
        self._set_action({"type": "pass"})
        await interaction.response.send_message("You passed your turn!", ephemeral=True)
        self.stop()

    # ── Battle Embeds ─────────────────────────────────────────────────────────────

def build_party_text(party: list) -> str:
    if not party:
        return "None"
    return "\n".join(
        f"Lvl. {p['level']} {p['name']}{format_gender(p.get('gender','unknown'))} (#{p['order_number']})"
        for p in party
    )

def _build_action_embed(current_poke: dict, party: list, current_idx: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"What should {current_poke['name']} do?",
        color=discord.Color.gold()
    )
    full  = current_poke.get("full_data", current_poke)
    moves = (
        full.get("current_moves") or full.get("learned_moves") or
        current_poke.get("current_moves") or current_poke.get("learned_moves") or []
    )
    moves_text = "\n".join(
        f"{get_type_emoji(POKEMON_MOVES.get(m.lower().replace(' ', '-'), {}).get('type', 'Normal'))} {m}"
        for m in moves[:4]
    ) or "None"
    embed.add_field(name="Available Moves", value=moves_text, inline=False)

    bench = [
        f"Lvl. {p['level']} {p.get('iv',0)}% {p['name']}{format_gender(p.get('gender','unknown'))} (#{p['order_number']})"
        for i, p in enumerate(party)
        if i != current_idx and p.get("hp", 0) > 0
    ]
    embed.add_field(name="Available Pokémon", value="\n".join(bench) or "None", inline=False)
    return embed

async def _update_battle_embed(battle: dict, c: dict, o: dict):
    embed = discord.Embed(
        title=f"⚔️ {battle['challenger'].display_name} vs {battle['opponent'].display_name}",
        description="Choose your moves in DMs.",
        color=discord.Color.gold()
    )
    embed.add_field(
        name=battle["challenger"].display_name,
        value=f"Lvl. {c['level']} {c.get('iv',0)}% {c['name']}{format_gender(c.get('gender','unknown'))} "
              f"• {c['hp']}/{c['max_hp']} HP",
        inline=False
    )
    embed.add_field(
        name=battle["opponent"].display_name,
        value=f"Lvl. {o['level']} {o.get('iv',0)}% {o['name']}{format_gender(o.get('gender','unknown'))} "
              f"• {o['hp']}/{o['max_hp']} HP",
        inline=False
    )
    if os.path.exists("assets/battle_field.png"):
        file  = discord.File("assets/battle_field.png", filename="battle_field.png")
        embed.set_image(url="attachment://battle_field.png")
        await battle["message"].edit(embed=embed, attachments=[file])
    else:
        await battle["message"].edit(embed=embed)

async def update_party_embed(battle: dict, client):
    embed = discord.Embed(
        title="Choose your party",
        description=(
            f"Choose **{battle['team_size']}** pokémon to fight in the battle. "
            "The battle will begin once both trainers have chosen their party."
        ),
        color=discord.Color.gold()
    )
    embed.add_field(name=f"{battle['challenger'].display_name}'s Party",
                    value=build_party_text(battle["challenger_party"]), inline=False)
    embed.add_field(name=f"{battle['opponent'].display_name}'s Party",
                    value=build_party_text(battle["opponent_party"]), inline=False)
    bot_name = client.user.name if client.user else "Pokékiro"
    embed.set_footer(text=f"Use `@{bot_name} battle add <pokémon>` to add a pokémon to the party!")
    await battle["message"].edit(embed=embed)


# ── Battle Flow ───────────────────────────────────────────────────────────────

async def start_battle(battle: dict):
    record_battle(
        battle["challenger"], battle["opponent"],
        battle["challenger_party"], battle["opponent_party"],
        battle_format=battle["format"], status="active"
    )

    embed = discord.Embed(
        title="💥 Ready to battle!",
        description="The battle will begin in 5 seconds.",
        color=discord.Color.gold()
    )
    for side, key in [("challenger", "challenger_party"), ("opponent", "opponent_party")]:
        user = battle[side]
        text = "\n".join(
            f"Lvl. {p['level']} {p.get('iv',0)}% {p['name']}{format_gender(p.get('gender','unknown'))}"
            for p in battle[key]
        )
        embed.add_field(name=user.display_name, value=text, inline=False)

    await battle["message"].edit(embed=embed)
    await asyncio.sleep(5)
    await trigger_switch_abilities(battle)

    for p in battle["challenger_party"] + battle["opponent_party"]:
        max_hp = p.get("calculated_stats", {}).get("hp", p.get("max_hp", 50))
        p["max_hp"] = max_hp
        if "hp" not in p or p["hp"] > max_hp:
            p["hp"] = max_hp

    battle["battle_started"] = True
    await begin_battle_loop(battle)


async def begin_battle_loop(battle: dict):
    battle.setdefault("turn_counter", 0)
    battle.setdefault("weather", None)

    while battle["battle_started"]:
        battle["turn_counter"] += 1

        c = battle["challenger_party"][battle["challenger_current_idx"]]
        o = battle["opponent_party"][battle["opponent_current_idx"]]

        battle["challenger_action"] = None
        battle["opponent_action"]   = None

        # Truant check
        for side, poke in (("challenger", c), ("opponent", o)):
            ability = poke.get("full_data", {}).get("ability", "")
            if ability == "Truant":
                last = battle.get(f"{side}_last_moved_turn", 0)
                if battle["turn_counter"] - last == 1:
                    battle[f"{side}_action"] = {"type": "truant_skip"}

        # Send DM action views — fallback to channel if DMs disabled
        for side, poke in (("challenger", c), ("opponent", o)):
            if battle[f"{side}_action"] is not None:
                continue
            user  = battle[side]
            embed = _build_action_embed(poke, battle[f"{side}_party"], battle[f"{side}_current_idx"])
            view  = BattleActionView(battle, user, poke, timeout=20)
            try:
                await user.send(embed=embed, view=view)
            except discord.Forbidden:
                try:
                    await battle["channel"].send(
                        f"{user.mention} — your DMs are disabled! "
                        "Please enable DMs to participate in battles.",
                        embed=embed, view=view
                    )
                except Exception:
                    battle[f"{side}_action"] = {"type": "auto_pass"}

        # Wait for both actions (max 22 s)
        deadline = asyncio.get_event_loop().time() + 22
        while True:
            if battle["challenger_action"] is not None and battle["opponent_action"] is not None:
                break
            if asyncio.get_event_loop().time() > deadline:
                for side in ("challenger", "opponent"):
                    if battle[f"{side}_action"] is None:
                        battle[f"{side}_action"] = {"type": "auto_pass"}
                break
            await asyncio.sleep(0.5)

        if not battle["battle_started"]:
            break

        turn_messages = await resolve_turn(battle, c, o)

        embed = discord.Embed(
            title=f"⚔️ {battle['challenger'].display_name} vs {battle['opponent'].display_name}",
            description="\n".join(turn_messages) or "Nothing happened.",
            color=0xFFD700
        )

        if not battle["battle_started"]:
            embed.set_footer(text="Battle ended!")
            await battle["channel"].send(embed=embed)
            await _end_battle(battle, turn_messages)
            break
        else:
            embed.set_footer(text="Next round in 5 seconds.")
            await battle["channel"].send(embed=embed)
            c = battle["challenger_party"][battle["challenger_current_idx"]]
            o = battle["opponent_party"][battle["opponent_current_idx"]]
            await _update_battle_embed(battle, c, o)
            await asyncio.sleep(5)


async def resolve_turn(battle: dict, c: dict, o: dict) -> list:
    messages = []
    c_action = battle["challenger_action"]
    o_action = battle["opponent_action"]
    c_user   = battle["challenger"]
    o_user   = battle["opponent"]

    # Flee check first
    for action, user in ((c_action, c_user), (o_action, o_user)):
        if action["type"] == "flee":
            messages.append(f"**{user.display_name}** fled from the battle!")
            battle["battle_started"] = False
            return messages

    # Switches
    for side, action, user, party_key, idx_key in (
        ("challenger", c_action, c_user, "challenger_party", "challenger_current_idx"),
        ("opponent",   o_action, o_user, "opponent_party",   "opponent_current_idx"),
    ):
        if action["type"] == "switch":
            idx      = action["index"]
            party    = battle[party_key]
            old_name = party[battle[idx_key]]["name"]
            battle[idx_key] = idx
            messages.append(
                f"**{user.display_name}** withdrew **{old_name}** and sent out **{party[idx]['name']}**!"
            )

    if c_action["type"] == "switch" or o_action["type"] == "switch":
        await trigger_switch_abilities(battle)
        c = battle["challenger_party"][battle["challenger_current_idx"]]
        o = battle["opponent_party"][battle["opponent_current_idx"]]

    # Speed order
    c_speed = c.get("calculated_stats", {}).get("speed", 0)
    o_speed = o.get("calculated_stats", {}).get("speed", 0)
    c_goes_first = c_speed >= o_speed if c_speed != o_speed else random.random() < 0.5

    ordered = [
        ("challenger", c_action, c_user, c, o, o_user, "challenger_last_moved_turn"),
        ("opponent",   o_action, o_user, o, c, c_user, "opponent_last_moved_turn"),
    ]
    if not c_goes_first:
        ordered.reverse()

    for side, action, user, attacker, defender, def_user, last_moved_key in ordered:
        if not battle["battle_started"]:
            break

        atype = action["type"]

        if atype in ("pass", "auto_pass"):
            label = "passed their turn" if atype == "pass" else "did nothing (time ran out)"
            messages.append(f"**{user.display_name}** {label}.")

        elif atype == "truant_skip":
            messages.append(f"**{attacker['name']}** is loafing around! (Truant)")

        elif atype == "move":
            move_name = action["move"]
            move_data = POKEMON_MOVES.get(move_name.lower().replace(" ", "-"), {})
            damage    = calculate_damage(attacker, defender, move_name)
            defender["hp"] = max(0, defender.get("hp", 0) - damage)
            battle[last_moved_key] = battle["turn_counter"]

            type_emoji = get_type_emoji(move_data.get("type", "Normal"))

            # Super effective / not very effective text
            move_type     = move_data.get("type", "Normal")
            defender_types = defender.get("type", ["Normal"])
            effectiveness = 1.0
            if move_type in TYPE_EFFECTIVENESS:
                for dt in defender_types:
                    effectiveness *= TYPE_EFFECTIVENESS[move_type].get(dt, 1.0)
            if effectiveness > 1.0:
                eff_text = " **It's super effective!**"
            elif effectiveness < 1.0 and effectiveness > 0:
                eff_text = " *It's not very effective...*"
            elif effectiveness == 0:
                eff_text = " *It had no effect.*"
            else:
                eff_text = ""

            messages.append(
                f"**{user.display_name}'s {attacker['name']}** used {type_emoji} **{move_name}**! "
                f"Dealt **{damage}** damage!{eff_text} "
                f"({defender['hp']}/{defender['max_hp']} HP remaining)"
            )

            contact_msgs = await trigger_contact_abilities(attacker, defender, move_data, battle)
            messages.extend(contact_msgs)

            if defender["hp"] <= 0:
                messages.append(f"**{def_user.display_name}'s {defender['name']}** fainted! 💀")

                def_side    = "opponent" if side == "challenger" else "challenger"
                def_party   = battle[f"{def_side}_party"]
                def_idx_key = f"{def_side}_current_idx"
                next_alive  = next(
                    (i for i, p in enumerate(def_party) if p.get("hp", 0) > 0), None
                )
                if next_alive is not None:
                    battle[def_idx_key] = next_alive
                    messages.append(
                        f"**{def_user.display_name}** sent out **{def_party[next_alive]['name']}**!"
                    )
                    await trigger_switch_abilities(battle)
                else:
                    battle["battle_started"] = False

    return messages


async def _end_battle(battle: dict, turn_messages: list):
    c_alive = any(p.get("hp", 0) > 0 for p in battle["challenger_party"])
    o_alive = any(p.get("hp", 0) > 0 for p in battle["opponent_party"])

    c_id = str(battle["challenger"].id)
    o_id = str(battle["opponent"].id)

    if c_alive and not o_alive:
        winner_id, loser_id = c_id, o_id
        winner_display = battle["challenger"].display_name
    elif o_alive and not c_alive:
        winner_id, loser_id = o_id, c_id
        winner_display = battle["opponent"].display_name
    else:
        last = (turn_messages[-1] if turn_messages else "").lower()
        if battle["challenger"].display_name.lower() in last and "fled" in last:
            winner_id, loser_id = o_id, c_id
            winner_display = battle["opponent"].display_name
        elif battle["opponent"].display_name.lower() in last and "fled" in last:
            winner_id, loser_id = c_id, o_id
            winner_display = battle["challenger"].display_name
        else:
            winner_id = loser_id = winner_display = None

    battles.pop(battle["challenger"].id, None)
    battles.pop(battle["opponent"].id, None)

    if winner_id and loser_id:
        update_battle_result(c_id, o_id, winner_id, loser_id)
        await battle["channel"].send(f"🏆 **{winner_display}** wins the battle!")
    else:
        await battle["channel"].send("The battle ended in a draw!")

    data = load_collection()
    rewards = []
    for user in (battle["challenger"], battle["opponent"]):
        udata = data.get(str(user.id))
        if not udata:
            continue
        selected = udata.get("selected_pokemon")
        pokes = udata.get("pokemon", [])
        if not isinstance(selected, int) or not (1 <= selected <= len(pokes)):
            continue
        pokemon = pokes[selected - 1]
        if not isinstance(pokemon, dict):
            continue
        add_friendship_points(pokemon, 5)
        rewards.append((user, selected, pokemon))
        pokes[selected - 1] = pokemon
        udata["pokemon"] = pokes
        data[str(user.id)] = udata
    save_collection(data)

    for user, selected, pokemon in rewards:
        embed = _get_friendship_reward_embed(user, pokemon, 5, selected)
        await battle["channel"].send(embed=embed)

# ── Challenge View ────────────────────────────────────────────────────────────

class ChallengeView(View):
    def __init__(self, opponent, challenger, team_size: int, channel, guild, timeout=60):
        super().__init__(timeout=timeout)
        self.opponent   = opponent
        self.challenger = challenger
        self.team_size  = team_size
        self.channel    = channel
        self.guild      = guild
        self.responded  = False
        self.msg        = None

    async def on_timeout(self):
        pending_challenges.pop(self.opponent.id, None)
        if self.msg and not self.responded:
            try:
                await self.msg.edit(content="The request to battle has timed out.", embed=None, view=None)
            except Exception:
                pass

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("This challenge is not for you!", ephemeral=True)
        if self.responded:
            return await interaction.response.send_message("Already responded.", ephemeral=True)
        self.responded = True
        pending_challenges.pop(self.opponent.id, None)

        battle = {
            "challenger":             self.challenger,
            "opponent":               self.opponent,
            "team_size":              self.team_size,
            "channel":                self.channel,
            "guild":                  self.guild,
            "challenger_party":       [],
            "opponent_party":         [],
            "challenger_current_idx": 0,
            "opponent_current_idx":   0,
            "challenger_ready":       False,
            "opponent_ready":         False,
            "battle_started":         False,
            "challenger_action":      None,
            "opponent_action":        None,
            "turn_counter":           0,
            "weather":                None,
            "format":                 f"{self.team_size}v{self.team_size}",
            "message":                None,
        }
        battles[self.challenger.id] = battle
        battles[self.opponent.id]   = battle

        await interaction.response.edit_message(view=None)

        bot_name = interaction.client.user.name if interaction.client.user else "Pokékiro"
        party_embed = discord.Embed(
            title="Choose your party",
            description=(
                f"Choose **{self.team_size}** pokémon to fight in the battle. "
                "The battle will begin once both trainers have chosen their party."
            ),
            color=discord.Color.gold()
        )
        party_embed.add_field(name=f"{self.challenger.display_name}'s Party", value="None", inline=False)
        party_embed.add_field(name=f"{self.opponent.display_name}'s Party",   value="None", inline=False)
        party_embed.set_footer(text=f"Use `@{bot_name} battle add <order_number>` to add a pokémon!")

        msg = await self.channel.send(embed=party_embed)
        battle["message"] = msg
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("This challenge is not for you!", ephemeral=True)
        if self.responded:
            return await interaction.response.send_message("Already responded.", ephemeral=True)
        self.responded = True
        pending_challenges.pop(self.opponent.id, None)
        await interaction.response.edit_message(content="Battle request cancelled.", embed=None, view=None)
        self.stop()

# ── Cog ───────────────────────────────────────────────────────────────────────

class Battle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="challenge")
    async def challenge(self, ctx, *args):
        if not await check_registration(ctx):
            return

        opponent  = None
        team_size = 1

        for arg in args:
            if arg.startswith("<@") and arg.endswith(">"):
                uid = arg.strip("<@!>")
                try:
                    opponent = await ctx.guild.fetch_member(int(uid))
                except Exception:
                    pass
            elif arg.isdigit():
                team_size = max(1, min(6, int(arg)))

        if opponent is None and ctx.message.mentions:
            opponent = ctx.message.mentions[0]

        if opponent is None:
            return await ctx.reply("Please mention a user to challenge! e.g. `challenge @user`")
        if opponent.id == ctx.author.id:
            return await ctx.reply("You can't challenge yourself!")
        if opponent.bot:
            return await ctx.reply("You can't challenge a bot!")
        if not is_registered(opponent.id):
            return await ctx.reply(f"**{opponent.display_name}** is not registered!")

        if ctx.author.id in battles or opponent.id in battles:
            return await ctx.reply("One of you is already in a battle!")
        if ctx.author.id in pending_challenges:
            return await ctx.reply("You already have a pending challenge!")
        if opponent.id in pending_challenges:
            return await ctx.reply(f"**{opponent.display_name}** already has a pending challenge!")

        view = ChallengeView(
            opponent=opponent, challenger=ctx.author,
            team_size=team_size, channel=ctx.channel,
            guild=ctx.guild, timeout=60
        )
        msg = await ctx.send(
            f"Challenging {opponent.mention} to a battle. Click the accept button to accept!",
            view=view
        )
        view.msg = msg
        pending_challenges[opponent.id] = {
            "challenger": ctx.author, "opponent": opponent,
            "team_size": team_size, "channel": ctx.channel,
            "message": msg, "guild": ctx.guild,
        }

    @commands.group(name="battle", invoke_without_command=True)
    async def battle_root(self, ctx):
        await ctx.reply(
            "**Battle Commands:**\n"
            "`challenge @user [team_size]` — Challenge someone\n"
            "`battle add <order_number>` — Add a Pokémon to your party\n"
            "`battle remove <order_number>` — Remove a Pokémon from your party"
        )

    @battle_root.command(name="add")
    async def battle_add(self, ctx, order_number: int = None):
        if not await check_registration(ctx):
            return

        battle = battles.get(ctx.author.id)
        if battle is None:
            return await ctx.reply("You're not in a battle setup right now!")
        if battle["battle_started"]:
            return await ctx.reply("The battle has already started!")
        if order_number is None:
            return await ctx.reply("Usage: `battle add <order_number>`")

        trainer_data = get_trainer_data(ctx.author.id)
        if trainer_data is None:
            return await ctx.reply("Could not load your trainer data!")

        poke = get_pokemon_by_order(trainer_data, order_number)
        if poke is None:
            return await ctx.reply(f"No Pokémon found at position **#{order_number}**!")

        is_challenger = ctx.author.id == battle["challenger"].id
        party_key     = "challenger_party" if is_challenger else "opponent_party"
        ready_key     = "challenger_ready" if is_challenger else "opponent_ready"
        party         = battle[party_key]
        team_size     = battle["team_size"]

        if len(party) >= team_size:
            return await ctx.reply(f"Your party is already full! ({team_size}/{team_size})")
        if any(p.get("order_number") == order_number for p in party):
            return await ctx.reply(f"**{poke.get('name')}** is already in your party!")

        calc_stats  = get_calculated_stats(poke)
        gender_text = str(poke.get("gender", "unknown")).lower().strip()
        if gender_text not in ("male", "female"):
            gender_text = "unknown"

        battle_poke = {
            "name":             poke.get("name", "Unknown"),
            "level":            poke.get("level", 1),
            "iv":               get_pokemon_iv(poke),
            "type":             poke.get("type", ["Normal"]),
            "order_number":     order_number,
            "gender":           gender_text,
            "calculated_stats": calc_stats,
            "max_hp":           calc_stats["hp"],
            "hp":               calc_stats["hp"],
            "status":           None,
            "stat_changes":     {},
            "full_data":        poke,
        }
        party.append(battle_poke)

        await ctx.reply(
            f"Added **{battle_poke['name']}** (Lvl. {battle_poke['level']}, "
            f"{battle_poke['iv']}% IV) to your party! ({len(party)}/{team_size})"
        )

        if len(party) == team_size:
            battle[ready_key] = True
            await ctx.send(f"✅ **{ctx.author.display_name}**'s party is ready!")

        await update_party_embed(battle, self.bot)

        if battle["challenger_ready"] and battle["opponent_ready"]:
            await ctx.send("🔥 Both parties are ready! Starting battle...")
            await start_battle(battle)

    @battle_root.command(name="remove")
    async def battle_remove(self, ctx, order_number: int = None):
        battle = battles.get(ctx.author.id)
        if battle is None:
            return await ctx.reply("You're not in a battle setup right now!")
        if battle["battle_started"]:
            return await ctx.reply("Can't remove Pokémon after battle has started!")
        if order_number is None:
            return await ctx.reply("Usage: `battle remove <order_number>`")

        is_challenger = ctx.author.id == battle["challenger"].id
        party_key     = "challenger_party" if is_challenger else "opponent_party"
        ready_key     = "challenger_ready" if is_challenger else "opponent_ready"
        party         = battle[party_key]

        before = len(party)
        battle[party_key] = [p for p in party if p.get("order_number") != order_number]

        if len(battle[party_key]) == before:
            return await ctx.reply(f"No Pokémon with order #{order_number} found in your party!")

        battle[ready_key] = False
        removed_name = next((p["name"] for p in party if p["order_number"] == order_number), "Pokémon")
        await ctx.reply(f"Removed **{removed_name}** from your party.")
        await update_party_embed(battle, self.bot)


async def setup(bot):
    await bot.add_cog(Battle(bot))
