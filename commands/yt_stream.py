import discord
from discord.ext import commands
import yt_dlp
import asyncio
import subprocess

class MsgBox:
    @staticmethod
    def msgBox(query: str, rgb: int=0):
        rgb = max(0, min(rgb, 2))
        preset = (discord.Color.red(), discord.Color.green(), discord.Color.blue())
        embed = discord.Embed(
            description=query,
            color=preset[rgb]
        )
        return embed

class YTDLHelper:
    @staticmethod
    async def get_info_and_url(query: str):
        url = query
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        url2 = YTDLHelper.extract_audio_url(info)
        
        if not url2:
            raise discord.ClientException(MsgBox.msgBox("🎵 오디오 스트리밍 URL을 찾을 수 없습니다."))
        
        return info, url2

    @staticmethod
    async def get_search_info(query: str, limit: int=5):
        key = f"ytsearch{limit}:{query}"
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'quiet': True,
            'noplaylist': True
        }

        results = []

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(key, download=False)
        
        if 'entries' in info:
            for entry in info['entries']:
                if entry and entry['url']:
                    results.append(entry)
        if not results:
            raise discord.ClientException("검색 결과가 없습니다.")
        
        return results

    @staticmethod
    def extract_audio_url(info):
        for f in info['formats']:
            if f.get('vcodec') == 'none' and f.get('acodec') != 'none' and f.get('url'):
                if 'm3u8' in f['url']:
                    return f['url']
        # fallback
        for f in info['formats']:
            if f.get('vcodec') == 'none' and f.get('acodec') != 'none' and f.get('url'):
                return f['url']
        return None

class GuildState:
    def __init__(self):
        self.voice_client = None
        self.queue = []
        self.original_queue = []
        self.current = None
        self.loop_queue = False

    def cleanup_current(self):
        if self.current:
            try:
                self.current.cleanup()
            except Exception:
                pass
            self.current = None
        return 

class YTstream(commands.Cog, name='음악 재생'):
    def __init__(self, bot):
        self.bot = bot
        self.guild_states = {}  # {guild_id: GuildState}

    def get_state(self, guild_id):
        if guild_id not in self.guild_states:
            self.guild_states[guild_id] = GuildState()
        return self.guild_states[guild_id]

    async def play_next(self, ctx):
        state = self.get_state(ctx.guild.id)
        
        if not state.queue and state.loop_queue and state.original_queue:
            state.queue = state.original_queue.copy()
            
        state.cleanup_current()

        if state.queue:
            info, url = state.queue.pop(0)

            ffmpeg_audio = discord.FFmpegPCMAudio(
                executable='/usr/bin/ffmpeg',
                source=url,
                before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                options='-vn'
            )
            source = discord.PCMVolumeTransformer(ffmpeg_audio, volume=0.3)
            state.current = (source, info, url)
            await ctx.send(embed=MsgBox.msgBox(f"▶ 다음 곡: '{info.get('title')}'을/를 재생합니다!", 2))
            state.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))
        else:
            await ctx.send(embed=MsgBox.msgBox("🛑 대기열이 비어 있어 재생을 종료합니다."))
            state.current = None
            state.loop_queue = False
            state.original_queue.clear()
            state.queue.clear()
            await state.voice_client.disconnect()
            state.voice_client = None
        return

    @commands.command(help='봇을 음성채널에 입장시킵니다.')
    async def join(self, ctx):
        state = self.get_state(ctx.guild.id)
        if not ctx.author.voice:
            return await ctx.send(embed=MsgBox.msgBox("사용자가 음성 채널에 접속하지 않았습니다."))
        
        state.current = None
        state.loop_queue = False
        state.original_queue.clear()
        state.queue.clear()

        if not state.voice_client:
            state.voice_client = await ctx.author.voice.channel.connect()
        
        channel = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            state.voice_client = await channel.connect()
        return

    @commands.command(help='유튜브 링크 또는 검색어를 입력어를 입력해 재생 대기열에 추가합니다.')
    async def play(self, ctx, *, query: str):
        try:
            if not ctx.author.voice:
                return await ctx.send(embed=MsgBox.msgBox("음성 채널에 연결되어 있지 않습니다."))

            def time_format(sec):
                if sec is None:
                    return 'Unknown'
                min, sec = divmod(sec, 60)
                return f"{int(min)}:{str(int(sec)).zfill(2)}"
            
            state = self.get_state(ctx.guild.id)

            if not state.voice_client:
                return await ctx.send(embed=MsgBox.msgBox("음성 채널에 연결되어 있지 않습니다."))

            if not query.startswith('http'):
                message = await ctx.send("🕝검색 중...")
                results = await YTDLHelper.get_search_info(query)
                if not results:
                    return await ctx.send(embed=MsgBox.msgBox("검색 결과가 없습니다."))
                
                description = ''
                for idx, entry in enumerate(results, 1):
                    description += f"{idx}. {entry.get('title', 'Untitled')} ({time_format(entry.get('duration'))})\n"
                await message.delete()
                embed = discord.Embed(
                    title="🎶 다음 중 재생할 곡을 선택하세요",
                    description=description,
                    color=discord.Color.green()
                )
                message = await ctx.send(embed=embed)

                for i in range(len(results)):
                    await message.add_reaction(f"{i+1}\u20e3")
                
                def check(reaction, user):
                    return (
                        user == ctx.author and
                        reaction.message.id == message.id and
                        reaction.emoji in [f"{i+1}\u20e3" for i in range(len(results))]
                    )

                try:
                    reaction, _ = await self.bot.wait_for('reaction_add', timeout=20.0, check=check)
                    choice = int(reaction.emoji[0]) - 1
                except asyncio.TimeoutError:
                    await message.delete()
                    return await ctx.send(embed=MsgBox.msgBox("⏰ 선택 시간이 초과되었습니다."))
                except Exception as e:
                    await message.delete()
                    return await ctx.send(embed=MsgBox.msgBox(f"❌ 오류 발생: {e}"))
                await message.delete()
                
                embed = discord.Embed(
                    description=f"{results[choice].get('title')} ({time_format(results[choice].get('duration'))})",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                query = results[choice]['url']
            
            info, url = await YTDLHelper.get_info_and_url(query)
            
            if state.loop_queue:
                    state.original_queue.append((info, url))
            
            if not state.voice_client.is_playing() and not state.voice_client.is_paused():
                prep_msg = await ctx.send("🎧 재생 준비 중...")

                ffmpeg_audio = discord.FFmpegPCMAudio(
                    executable='/usr/bin/ffmpeg',
                    source=url,
                    before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                    options='-vn'
                )
                source = discord.PCMVolumeTransformer(ffmpeg_audio, volume=0.3)
                state.current = (source, info, url)
                await prep_msg.delete()
                await ctx.send(embed=MsgBox.msgBox(f"✅ '{info.get('title')} ({time_format(info.get('duration'))})'을/를 재생합니다!", 2))
                state.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))
            else:
                state.queue.append((info, url))
                await ctx.send(embed=MsgBox.msgBox(f"📥 '{info.get('title')} ({time_format(info.get('duration'))})'을/를 대기열에 추가했습니다.", 2))
            return
        except Exception as e:
            return await ctx.send(embed=MsgBox.msgBox(f"❌ 오류 발생: {e}"))

    @commands.command(help='음악을 일시정지합니다.')
    async def pause(self, ctx):
        vc = ctx.voice_client
        if vc and vc.is_playing():
            vc.pause()
            return await ctx.send("⏸ 일시정지했습니다.")
        return await ctx.send(embed=MsgBox.msgBox("재생 중인 노래가 없습니다."))

    @commands.command(help='일시정지를 해제합니다.')
    async def resume(self, ctx):
        vc = ctx.voice_client
        if vc and vc.is_paused():
            vc.resume()
            return await ctx.send("▶ 다시 재생합니다.")
        return await ctx.send(embed=MsgBox.msgBox("일시정지된 노래가 없습니다."))

    @commands.command(help='재생을 중지하고 대기열을 초기화합니다.')
    async def stop(self, ctx):
        state = self.get_state(ctx.guild.id)
        vc = ctx.voice_client
        if vc:
            vc.stop()
            state.cleanup_current()
            state.queue.clear()
            return await ctx.send(embed=MsgBox.msgBox("⏹ 재생을 중지하고 대기열을 초기화했습니다."))
        return await ctx.send(embed=MsgBox.msgBox("음성 채널에 연결되어 있지 않습니다."))

    @commands.command(help='노래를 건너뜁니다.')
    async def skip(self, ctx):
        vc = ctx.voice_client
        state = self.get_state(ctx.guild.id)
        if vc and state.queue:
            vc.stop()  # play_next가 호출됨
        else:
            await ctx.send(embed=MsgBox.msgBox("다음 곡이 없어 종료합니다."))
            state.cleanup_current()
            state.current = None
            state.loop_queue = False
            state.original_queue.clear()
            state.queue.clear()
            await vc.disconnect()
            state.voice_client = None
        return 

    @commands.command(help='음성채널에서 떠납니다.')
    async def leave(self, ctx):
        state = self.get_state(ctx.guild.id)
        vc = ctx.voice_client
        if vc:
            state.cleanup_current()
            state.current = None
            state.loop_queue = False
            state.original_queue.clear()
            state.queue.clear()
            await vc.disconnect()
            state.voice_client = None
            return await ctx.send(embed=MsgBox.msgBox("👋 연결을 종료합니다.", 2))
        return await ctx.send(embed=MsgBox.msgBox("현재 음성 채널에 연결되어 있지 않습니다."))

    @commands.command(help='현재 재생 목록을 간략하게 보여줍니다.')
    async def pli(self, ctx):
        def time_format(sec):
            if sec is None:
                return 'Unknown'
            min, sec = divmod(sec, 60)
            return f"{int(min)}:{str(int(sec)).zfill(2)}"
        
        state = self.get_state(ctx.guild.id)

        if state.voice_client or (not state.queue and state.current):
            return await ctx.send(embed=MsgBox.msgBox('음성 채널에 연결되어 있지 않거나 노래 재생 중이 아닙니다.'))

        _, c_info, _ = state.current
        c_title, c_duration = c_info.get('title', 'Untitled'), time_format(c_info.get('duration'))
        description = f"🎶 현재 재생 중: {c_title} ({c_duration})\n"
        
        if state.queue:
            n_info, _ = state.queue[0]
            n_title, n_duration = n_info.get('title', 'Untitled'), time_format(n_info.get('duration'))
            description += f"⏭ 다음 곡: {n_title} ({n_duration})\n📜 대기열 길이: {len(state.queue)}\n"
        else:
            description += "마지막 곡입니다."
        
        if state.loop_queue:
            description += "🔁 반복재생이 활성화 중입니다."

        embed = discord.Embed(
            title="📻 재생 정보",
            description=description,
            color=discord.Color.default(),
        )
        return await ctx.send(embed=embed)

    @commands.command(help='현재 재생목록을 반복 재생합니다.')
    async def loop(self, ctx):
        state = self.get_state(ctx.guild.id)
        if state.voice_client is None:
            return await ctx.send(embed=MsgBox.msgBox("음성 채널에 연결되어 있지 않습니다."))
        
        state.loop_queue = not getattr(state, 'loop_queue', False)
        
        if state.loop_queue:
            state.original_queue = state.queue.copy()
            if state.current:
                state.original_queue.append(state.current[1:])
        else:
            state.original_queue.clear()
        
        embed = MsgBox.msgBox(f"🔁 반복 재생이 {'활성화' if state.loop_queue else '비활성화'}되었습니다.", 1-int(not state.loop_queue))
        return await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(YTstream(bot))