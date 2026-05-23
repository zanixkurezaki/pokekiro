import json
import os
import discord
import aiohttp
from datetime import datetime
from discord.ext import commands
from timezonefinder import TimezoneFinder
import pytz

SETTINGS_FILE = "data/user_timezone_database.json"

def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {}

def save_settings(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def geocode_country(country_name: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": country_name, "format": "json", "limit": 1}
    headers = {"User-Agent": "Pokekiro-Discord-Bot/1.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        item = data[0]
                        display = item.get("display_name", country_name).split(",")[0].strip()
                        return display, float(item["lat"]), float(item["lon"])
    except Exception:
        pass
    return None

def get_time_period(lat: float, lon: float) -> tuple:
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    local_hour = datetime.now(pytz.timezone(tz_name)).hour

    if 5 <= local_hour < 8:
        return "morning", "🌅", "It is currently morning time."
    elif 8 <= local_hour < 18:
        return "day", "☀️", "It is currently day time."
    elif 18 <= local_hour < 21:
        return "evening", "🌆", "It is currently evening time."
    else:
        return "night", "🌙", "It is currently night time."

def get_user_location(user_id: str) -> dict | None:
    settings = load_settings()
    return settings.get(user_id, {}).get("location")

class TimezoneSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="timezone")
    async def timezone_cmd(self, ctx, *, country: str = None):
        user_id  = str(ctx.author.id)
        settings = load_settings()

        if country is None:
            loc = settings.get(user_id, {}).get("location")
            if not loc:
                return await ctx.reply(
                    "No location set.\n"
                    "Use `@Pokékiro timezone <country>` to set one."
                )
            return await ctx.reply(
                f"Your current location is **Set** ({loc['lat']}, {loc['lon']})."
            )

        result = await geocode_country(country)
        if not result:
            return await ctx.reply(f"Could not find **{country}**. Please try a more specific name.")

        name, lat, lon = result
        if user_id not in settings:
            settings[user_id] = {}
        settings[user_id]["location"] = {"name": name, "lat": lat, "lon": lon}
        save_settings(settings)

        await ctx.reply(f"Set your location to **{name}** ({lat}, {lon}).")

    @commands.command(name="time")
    async def time_cmd(self, ctx):
        user_id  = str(ctx.author.id)
        settings = load_settings()

        loc = settings.get(user_id, {}).get("location")
        if not loc:
            return await ctx.reply(
                "No location set.\n"
                "Use `@Pokékiro timezone <country>` to set one first."
            )

        period, emoji, description = get_time_period(loc["lat"], loc["lon"])

        embed = discord.Embed(color=discord.Color.gold())
        embed.add_field(name=f"Time: {period.capitalize()} {emoji}", value=description, inline=False)
        embed.add_field(name="Your Location", value=f"{loc['name']}\n{loc['lat']}, {loc['lon']}", inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TimezoneSystem(bot))