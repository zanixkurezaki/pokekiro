import json
import discord
from discord.ext import commands

from database.movesets_database import pokemon_movesets
from utils.registered_checker import check_registration

DATA_FILE = "data/trainers_collection_database.json"

def get_available_moves(pokemon_name: str, level: int) -> list[str]:
    """Return moves a pokemon can learn at or below given level (level-up only, not Breeding)."""
    entry = next((p for p in pokemon_movesets if p["name"].lower() == pokemon_name.lower()), None)
    if not entry:
        return []
    result = []
    for m in entry["moves"]:
        method = m["method"]
        if method == "Breeding":
            continue
        try:
            if int(method) <= level:
                result.append(m["move"])
        except ValueError:
            continue
    return result

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class ChangeMoveSelect(discord.ui.Select):
    def __init__(self, current_moves: list, new_move: str, poke_index: int, user_id: str):
        self.new_move = new_move
        self.poke_index = poke_index
        self.user_id = user_id

        options = [
            discord.SelectOption(label=move if move else "None", value=str(i))
            for i, move in enumerate(current_moves)
        ]
        super().__init__(
            placeholder="Select a move to replace...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn't your selection!", ephemeral=True)

        slot_index = int(self.values[0])

        data = load_data()
        poke = data[self.user_id]["pokemon"][self.poke_index]

        current_moves = poke.get("current_moves", [None, None, None, None])
        current_moves[slot_index] = self.new_move
        poke["current_moves"] = current_moves

        available = poke.get("available_moves", [])
        if self.new_move not in available:
            available.append(self.new_move)
            poke["available_moves"] = available

        data[self.user_id]["pokemon"][self.poke_index] = poke
        save_data(data)

        await interaction.message.edit(view=None)
        await interaction.response.send_message(f"Your pokémon has learned **{self.new_move}**!")

class ChangeMoveView(discord.ui.View):
    def __init__(self, current_moves: list, new_move: str, poke_index: int, user_id: str):
        super().__init__(timeout=60)
        self.add_item(ChangeMoveSelect(current_moves, new_move, poke_index, user_id))

class Moves(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="moves")
    async def moves(self, ctx, order_number: int = None):
        if not await check_registration(ctx):
            return

        user_id = str(ctx.author.id)
        data = load_data()

        if user_id not in data or not data[user_id].get("pokemon"):
            return await ctx.send("You have no Pokémon.")

        pokes = data[user_id]["pokemon"]

        if order_number is None:
            order_number = data[user_id].get("selected_pokemon")
            if not order_number:
                return await ctx.send("You have no Pokémon selected. Provide an order number or select one first.")

        if order_number < 1 or order_number > len(pokes):
            return await ctx.send("Invalid Pokémon order number.")

        poke = pokes[order_number - 1]
        name = poke["name"]
        level = poke["level"]

        computed_available = get_available_moves(name, level)

        if "available_moves" not in poke:
            poke["available_moves"] = computed_available
            pokes[order_number - 1] = poke
            data[user_id]["pokemon"] = pokes
            save_data(data)

        available_moves = poke.get("available_moves", computed_available)

        current_moves = poke.get("current_moves", [None, None, None, None])
        while len(current_moves) < 4:
            current_moves.append(None)

        embed = discord.Embed(
            title=f"Level {level} {name}",
            description=(
                f"Here are the moves your pokémon can learn right now. "
                f"View all moves and how to get them using `@Pokékiro moves`!"
            ),
            color=discord.Color.gold()
        )

        available_value = "\n".join(available_moves) if available_moves else "None"
        embed.add_field(name="Available Moves", value=available_value, inline=False)

        current_value = "\n".join(
            move if move else "None"
            for move in current_moves
        )
        embed.add_field(name="Current Moves", value=current_value, inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="learn")
    async def learn(self, ctx, *, move_name: str = None):
        if not await check_registration(ctx):
            return

        if not move_name:
            return await ctx.reply("Usage: `@Pokékiro learn <move name>`")

        user_id = str(ctx.author.id)
        data = load_data()

        if user_id not in data or not data[user_id].get("pokemon"):
            return await ctx.send("You have no Pokémon.")

        pokes = data[user_id]["pokemon"]
        selected_no = data[user_id].get("selected_pokemon")

        if not selected_no or not (1 <= selected_no <= len(pokes)):
            return await ctx.send("You have no Pokémon selected.")

        poke = pokes[selected_no - 1]
        poke_index = selected_no - 1
        name = poke["name"]
        level = poke["level"]

        computed_available = get_available_moves(name, level)
        if "available_moves" not in poke:
            poke["available_moves"] = computed_available

        available_moves = poke.get("available_moves", computed_available)

        move_name_clean = move_name.strip().title()
        if move_name_clean not in available_moves:
            return await ctx.reply(f"**{move_name_clean}** is not an available move for your {name} right now.")

        current_moves = poke.get("current_moves", [None, None, None, None])
        while len(current_moves) < 4:
            current_moves.append(None)

        if move_name_clean in current_moves:
            return await ctx.reply(f"Your {name} already knows **{move_name_clean}**!")

        if None in current_moves:
            slot = current_moves.index(None)
            current_moves[slot] = move_name_clean
            poke["current_moves"] = current_moves
            pokes[poke_index] = poke
            data[user_id]["pokemon"] = pokes
            save_data(data)
            return await ctx.reply(f"Your pokémon has learned **{move_name_clean}**!")

        embed = discord.Embed(
            description="Your pokémon already knows the max number of moves! Please select a move to replace.",
            color=discord.Color.gold()
        )
        embed.set_author(name="Change Move")

        view = ChangeMoveView(current_moves, move_name_clean, poke_index, user_id)
        await ctx.reply(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Moves(bot))
