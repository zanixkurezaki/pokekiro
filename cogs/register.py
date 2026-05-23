import discord
from discord.ext import commands

class Register(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def register(self, ctx):
        embed = discord.Embed(
            title="Welcome to the world of Pokémon!",
            description=(
                "To begin your journey in **Pokékiro**, choose one of the starter Pokémon using:\n"
                "`@Pokékiro#4959 pick <Pokémon>`"
            ),
            color=discord.Color.gold()
        )

        embed.add_field(
            name="Generation I (Kanto)",
            value="Bulbasaur    ·    Charmander    ·    Squirtle",
            inline=False
        )
        embed.add_field(
            name="Generation II (Johto)",
            value="Chikorita    ·    Cyndaquil    ·    Totodile",
            inline=False
        )
        embed.add_field(
            name="Generation III (Hoenn)",
            value="Treecko    ·    Torchic    ·    Mudkip",
            inline=False
        )
        embed.add_field(
            name="Generation IV (Sinnoh)",
            value="Turtwig    ·    Chimchar    ·    Piplup",
            inline=False
        )
        embed.add_field(
            name="Generation V (Unova)",
            value="Snivy    ·    Tepig    ·    Oshawott",
            inline=False
        )
        embed.add_field(
            name="Generation VI (Kalos)",
            value="Chespin    ·    Fennekin    ·    Froakie",
            inline=False
        )
        embed.add_field(
            name="Generation VII (Alola)",
            value="Rowlet    ·    Litten    ·    Popplio",
            inline=False
        )
        embed.add_field(
            name="Generation VIII (Galar)",
            value="Grookey    ·    Scorbunny    ·    Sobble",
            inline=False
        )
        embed.add_field(
            name="Generation IX (Paldea)",
            value="Sprigatito    ·    Fuecoco    ·    Quaxly",
            inline=False
        )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Register(bot))
