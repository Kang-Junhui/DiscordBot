import discord
from discord.ext import commands
import os
import asyncio
from commands import load_all_commands
from commands.customHelp import myHelp

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix='++', 
    intents=intents,
    help_command=myHelp(command_attrs={"help": "모든 명령어를 보여줍니다."}),
    activity=discord.Game(name='++help로 명령어 확인')
)

@bot.event
async def on_ready():
    print(f'{bot.user} 준비 완료료!')

async def main():
    await load_all_commands(bot)
    token = os.getenv("DISCORD_TOKEN")
    if token is None:
        print("Error: TOKEN env is not set.")
        return
    await bot.start(token)

asyncio.run(main())