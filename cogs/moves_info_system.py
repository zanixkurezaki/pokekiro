import discord
from discord.ext import commands

from database.moves_database import POKEMON_MOVES
from utils.constants import TYPE_EMOJIS, MOVE_CLASS_EMOJIS

def get_type_emoji(type_name: str) -> str:
    key = f"{type_name.lower()}_type"
    return TYPE_EMOJIS.get(key, "")

def get_class_emoji(class_name: str) -> str:
    return MOVE_CLASS_EMOJIS.get(class_name.lower(), "")

class MoveInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="move", invoke_without_command=False)
    async def move(self, ctx):
        pass

    @move.command(name="info")
    async def move_info(self, ctx, *, move_name: str = None):
        if not move_name:
            return await ctx.reply("Usage: `@Pokekiro move info <move name>`")

        key = move_name.strip().lower().replace(" ", "-")
        move = POKEMON_MOVES.get(key)

        if not move:
            for m in POKEMON_MOVES.values():
                if m["name"].lower() == move_name.strip().lower():
                    move = m
                    break

        if not move:
            return await ctx.reply(f"Move **{move_name}** not found.")

        name        = move["name"]
        description = move["description"]
        move_type   = move["type"]
        move_class  = move["class"]
        power       = move["power"]
        pp          = move["pp"]
        priority    = move["priority"]
        accuracy    = move["accuracy"]
        target      = move["target"]

        type_emoji  = get_type_emoji(move_type)
        class_emoji = get_class_emoji(move_class)

        embed = discord.Embed(
            title=name,
            description=description,
            color=discord.Color.gold()
        )

        embed.add_field(name="Type",     value=f"{type_emoji} {move_type}", inline=False)
        embed.add_field(name="Class",    value=f"{class_emoji} {move_class}", inline=False)
        embed.add_field(name="Power",    value=str(power), inline=False)
        embed.add_field(name="Accuracy", value=str(accuracy), inline=False)
        embed.add_field(name="PP",       value=str(pp), inline=False)
        embed.add_field(name="Priority", value=str(priority), inline=False)
        embed.add_field(name="Target",   value=target, inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MoveInfo(bot))
