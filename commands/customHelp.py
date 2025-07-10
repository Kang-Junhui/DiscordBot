import discord
from discord.ext import commands
import asyncio

class myHelp(commands.HelpCommand):
    def get_command_signature(self, command):
        return f"++{command.qualified_name}{' '+command.signature if command.signature and command.signature != '[command]' else ''}\n - {command.help}"

    async def send_bot_help(self, mapping):
        ctx = self.context
        embed = discord.Embed(title="📖 전체 명령어", color=discord.Color.green())
        for cog, command_list in mapping.items():
            name = cog.qualified_name if cog else "기타"
            filtered = await self.filter_commands(command_list, sort=True)
            if filtered:
                command_names = [f"`{self.get_command_signature(c)}`" for c in filtered]
                embed.add_field(name=name, value="\n".join(command_names), inline=False)

        await ctx.send(embed=embed)
        return

async def setup(bot):
    pass