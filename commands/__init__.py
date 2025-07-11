import os
import asyncio

async def load_all_commands(bot):
    # white list 파일을 참조 후 command로 쓸 .py 파일을 load_extension 
    white_list = os.path.join(os.path.dirname(__file__), "WhiteList.txt")
    with open(white_list, 'r', encoding='utf-8') as f:
        module = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    for mod in module:
        try:
            await bot.load_extension(f"commands.{mod[:-3]}")
        except Exception as e:
            print(f"Failed to load {mod}: {e}")
