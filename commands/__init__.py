import os
import asyncio

async def load_all_commands(bot):
    for filename in os.listdir(os.path.dirname(__file__)):
        if filename.endswith(".py") and filename != "__init__.py" and filename != "customHelp.py":
            await bot.load_extension(f"commands.{filename[:-3]}")