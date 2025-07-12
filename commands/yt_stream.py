import discord
from discord.ext import commands
import yt_dlp
import asyncio

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
    def get_info_and_url(url: str):
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/best',
            'quiet': True,
            'noplaylist': True,
            'no_warnings': True,
            'skip_download': True,
            # 'extractor_args': {'youtube':['player_client=android']},
            'cache_dir': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        url2 = YTDLHelper.extract_audio_url(info)
        
        if not url2:
            raise discord.ClientException(MsgBox.msgBox("🎵 오디오 스트리밍 URL을 찾을 수 없습니다."))
        
        return [(info, url2)]
    
    @staticmethod
    def get_pli_info_url(url: str):
        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'noplaylist': False,
            'no_warnings': True,
            'cache_dir': False,
            'skip_download': True,
        }
        ydl_opts2 = {
            'format': 'bestaudio[ext=m4a]/best',
            'quiet': True,
            'noplaylist': True,
            'no_warnings': True,
            'skip_download': True,
            # 'extractor_args': {'youtube':['player_client=android']},
            'cache_dir': False,
        }

        results = []

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        with yt_dlp.YoutubeDL(ydl_opts2) as ydl:
            entries = info.get('entries', [])
            for entry in entries:
                if entry and entry.get('url'):
                    try:
                        v_url = entry.get('url')
                        info2 = ydl.extract_info(v_url, download=False)
                        url2 = YTDLHelper.extract_audio_url(info2)
                        results.append((info2, url2))
                    except Exception as e:
                        print(f"[❌ 실패] {entry.get('title', 'Unknown')} - {e}")
        
        if not results:
            raise discord.ClientException("유효한 곡이 존재하지 않습니다.")
        
        return results

    @staticmethod
    def get_search_info(query: str, limit: int=5):
        key = f"ytsearch{limit}:{query}"
        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'noplaylist': True,
            'no_warnings': True,
            'cache_dir': False,
            'skip_download': True,
        }

        results = []

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(key, download=False)
        
        if 'entries' in info:
            entries = info.get('entries')
            for entry in entries:
                if entry and entry.get('url'):
                    results.append(entry)
        if not results:
            raise discord.ClientException("검색 결과가 없습니다.")
        
        return results

    @staticmethod
    def extract_audio_url(info):
        formats = info.get('formats', [])
        for f in formats:
            url = f.get('url')
            if f.get('vcodec') == 'none' and f.get('acodec') != 'none' and url:
                if 'm3u8' in url:
                    return url
        # fallback
        for f in formats:
            if f.get('vcodec') == 'none' and f.get('acodec') != 'none' and f.get('url'):
                return f.get('url')
        return None

class GuildState:
    def __init__(self):
        self.voice_client = None
        self.queue = []
        self.original_queue = []
        self.current = None
        self.loop_queue = False
        self.queue_lock = asyncio.Lock()

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

    def time_format(self, sec):
        if sec is None:
            return 'Unknown'
        min, sec = divmod(sec, 60)
        return f"{int(min)}:{str(int(sec)).zfill(2)}"

    async def _force_leave(self, ctx):
        state = self.get_state(ctx.guild.id)
        vc = state.voice_client
        if vc:
            state.cleanup_current()
            state.current = None
            state.loop_queue = False
            state.original_queue.clear()
            state.queue.clear()
            await vc.disconnect()
            state.voice_client = None
            await ctx.send(embed=MsgBox.msgBox("음성채팅에 아무도 없어 자동 종료합니다."))
        return
    
    async def play_next(self, ctx):
        state = self.get_state(ctx.guild.id)
        
        vch = state.voice_client.channel
        non_bot_memebers = [m for m in vch.members if not m.bot]
        if not non_bot_memebers:
            return await self._force_leave(ctx)
        
        state.cleanup_current()
        
        while state.queue_lock.locked() and not state.queue:
            await asyncio.sleep(0.5)

        if not state.queue and state.loop_queue and state.original_queue:
            state.queue = state.original_queue.copy()
        
        if state.queue:
            info, url = state.queue.pop(0)
            source = discord.FFmpegOpusAudio(
                executable='/usr/bin/ffmpeg',
                source=url,
                before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                options='-vn -ac 2 -ar 48000 -f opus'
            )
            # source = discord.PCMVolumeTransformer(ffmpeg_audio, volume=0.3)
            state.current = (source, info, url)
            await ctx.send(embed=MsgBox.msgBox(f"✅ '{info.get('title')} ({self.time_format(info.get('duration'))})'을/를 재생합니다!", 2))
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

    @commands.command(help='유튜브 링크 또는 검색어를 입력어를 입력해 재생 대기열에 추가합니다.')
    async def play(self, ctx, *, query: str):
        state = self.get_state(ctx.guild.id)
        if state.queue_lock.locked():
            return await ctx.send("⚠️ 재생목록을 추가하는 중입니다. 나중에 다시 시도해주세요.")
            
        try:
            async with state.queue_lock:
                if not ctx.author.voice:
                    return await ctx.send(embed=MsgBox.msgBox("사용자가 음성 채널에 연결되어 있지 않습니다."))

                if not state.voice_client:
                    state.current = None
                    state.loop_queue = False
                    state.original_queue.clear()
                    state.queue.clear()
                    state.voice_client = await ctx.author.voice.channel.connect()

                if not query.startswith('http'):
                    message = await ctx.send("🕝검색 중...")
                    results = YTDLHelper.get_search_info(query)
                    if not results:
                        return await ctx.send(embed=MsgBox.msgBox("검색 결과가 없습니다."))
                    
                    description = ''
                    for idx, entry in enumerate(results, 1):
                        description += f"{idx}. {entry.get('title', 'Untitled')} ({self.time_format(entry.get('duration'))})\n"
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
                        description=f"{results[choice].get('title')} ({self.time_format(results[choice].get('duration'))})",
                        color=discord.Color.green()
                    )
                    await ctx.send(embed=embed)
                    query = results[choice].get('url')
                
                prep_msg = await ctx.send("🎧 재생 준비 중...")

                if query.startswith('https://www.youtube.com/playlist'):
                    play_lists = YTDLHelper.get_pli_info_url(query)
                    state.queue.extend(play_lists)
                    if state.loop_queue:
                        state.original_queue.extend(play_lists)
                else:
                    music = YTDLHelper.get_info_and_url(query)
                    state.queue.extend(music)
                    if state.loop_queue:
                        state.original_queue.extend(music)
                await prep_msg.delete()
                
            if not state.voice_client.is_playing() and not state.voice_client.is_paused():
                await self.play_next(ctx)
            elif query.startswith('https://www.youtube.com/playlist'):
                await ctx.send(embed=MsgBox.msgBox(f"📥 '{play_lists[0][0].get('title')} ({self.time_format(play_lists[0][0].get('duration'))})' 외 {len(play_lists)-1}곡을 대기열에 추가했습니다.", 2))
            else:
                await ctx.send(embed=MsgBox.msgBox(f"📥 '{music[0][0].get('title')} ({self.time_format(music[0][0].get('duration'))})'을/를 대기열에 추가했습니다.", 2))
            return
        except Exception as e:
            return await ctx.send(embed=MsgBox.msgBox(f"❌ 오류 발생: {e}"))

    @commands.command(help='음악을 일시정지합니다.')
    async def pause(self, ctx):
        state = self.get_state(ctx.guild.id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            return await ctx.send("⏸ 일시정지했습니다.")
        return await ctx.send(embed=MsgBox.msgBox("재생 중인 노래가 없습니다."))

    @commands.command(help='일시정지를 해제합니다.')
    async def resume(self, ctx):
        state = self.get_state(ctx.guild.id)
        if state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            return await ctx.send("▶ 다시 재생합니다.")
        return await ctx.send(embed=MsgBox.msgBox("일시정지된 노래가 없습니다."))

    @commands.command(help='재생을 중지하고 대기열을 초기화합니다.')
    async def stop(self, ctx):
        state = self.get_state(ctx.guild.id)
        if state.queue_lock.locked():
            return await ctx.send("⚠️ 재생목록을 추가하는 중입니다. 나중에 다시 시도해주세요.")
        
        if state.voice_client:
            state.voice_client.stop()
            state.cleanup_current()
            state.queue.clear()
            return await ctx.send(embed=MsgBox.msgBox("⏹ 재생을 중지하고 대기열을 초기화했습니다."))
        return await ctx.send(embed=MsgBox.msgBox("음성 채널에 연결되어 있지 않습니다."))

    @commands.command(help='노래를 건너뜁니다.')
    async def skip(self, ctx):
        state = self.get_state(ctx.guild.id)
        if state.queue_lock.locked():
            return await ctx.send("⚠️ 재생목록을 추가하는 중입니다. 나중에 다시 시도해주세요.")
        
        if state.voice_client and state.queue:
            state.voice_client.stop()
        else:
            await ctx.send(embed=MsgBox.msgBox("다음 곡이 없어 종료합니다."))
            state.cleanup_current()
            state.current = None
            state.loop_queue = False
            state.original_queue.clear()
            state.queue.clear()
            await state.voice_client.disconnect()
            state.voice_client = None
        return 

    @commands.command(help='음성채널에서 떠납니다.')
    async def leave(self, ctx):
        state = self.get_state(ctx.guild.id)
        if state.queue_lock.locked():
            return await ctx.send("⚠️ 재생목록을 추가하는 중입니다. 나중에 다시 시도해주세요.")

        if state.voice_client:
            state.cleanup_current()
            state.current = None
            state.loop_queue = False
            state.original_queue.clear()
            state.queue.clear()
            await state.voice_client.disconnect()
            state.voice_client = None
            return await ctx.send(embed=MsgBox.msgBox("👋 연결을 종료합니다.", 2))
        return await ctx.send(embed=MsgBox.msgBox("현재 음성 채널에 연결되어 있지 않습니다."))

    @commands.command(help='현재 재생 목록을 간략하게 보여줍니다.')
    async def pli(self, ctx):        
        state = self.get_state(ctx.guild.id)
        if state.queue_lock.locked():
            return await ctx.send("⚠️ 재생목록을 추가하는 중입니다. 나중에 다시 시도해주세요.")
        
        if state.voice_client or (not state.queue and state.current):
            return await ctx.send(embed=MsgBox.msgBox('음성 채널에 연결되어 있지 않거나 노래 재생 중이 아닙니다.'))

        _, c_info, _ = state.current
        c_title, c_duration = c_info.get('title', 'Untitled'), self.time_format(c_info.get('duration'))
        description = f"🎶 현재 재생 중: {c_title} ({c_duration})\n"
        
        if state.queue:
            n_info, _ = state.queue[0]
            n_title, n_duration = n_info.get('title', 'Untitled'), self.time_format(n_info.get('duration'))
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
