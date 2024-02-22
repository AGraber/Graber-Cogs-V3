import discord
import re
import aiohttp
import json
import io
import os
from ffmpy import FFmpeg
from datetime import datetime
from redbot.core import commands
from redbot.core.bot import Red


class PixivFixer(commands.Cog, name='PixivFixer'):
    def __init__(self, bot: Red):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return

        if message.author.bot is True:
            return

        if message.author.guild_permissions.embed_links is False:
            return

        content = message.content
        match = re.search(r'https?://(?:www\.)?pixiv\.com/(?:.*/)(?:artworks/|member_illust\.php\?illust_id=)([0-9]*)/?([0-9]*)?', content)
        if match is None:
            return

        artwork_id = match.group(0)
        image_index = int(match.group(1))

        request_string = f'https://phixiv.net/api/info?id={artwork_id}&language=en'
        async with aiohttp.ClientSession() as session:
            async with session.get(request_string) as response:
                if response.ok is True:
                    final_text = await response.text()
                    artwork = json.loads(final_text)

                    embed = discord.Embed(title=artwork['title'], url=artwork['url'], description=f"{artwork['description']}\n{', '.join(artwork['tags'])}")
                    embed.set_author(name=artwork['author_name'], url=f"https://www.pixiv.net/users/{artwork['author_id']}")
                    embed.color = 0x26a7de

                    if image_index < 0 or image_index >= len(artwork['images']):
                        image_index = 0
                    
                    artwork_media_url = artwork['image_proxy_urls'][image_index]

                    # check if artwork url ends with .mp4
                    if artwork_media_url.endswith('.mp4'):
                        await message.channel.send(embed=embed)

                        if os.path.exists('original_video.mp4'):
                            os.remove('original_video.mp4')

                        if os.path.exists('gif.gif'):
                            os.remove('gif.gif')

                        async with aiohttp.ClientSession() as session:
                            async with session.get(artwork_media_url) as response:
                                with open('original_video.mp4', 'wb') as file:
                                    temp = await response.read()
                                    data = io.BytesIO(temp)
                                    file.write(data.getbuffer())

                                ff = FFmpeg(
                                    inputs={'original_video.mp4': None},
                                    outputs={'gif.gif': '-filter_complex "[0:v] split [a][b];[a] palettegen [p];[b][p] paletteuse"'}
                                )
                                ff.run()
                                discord_attachment = discord.File('gif.gif')
                                await message.channel.send(file=discord_attachment)
                                os.remove('original_video.mp4')
                                os.remove('gif.gif')
                    else:
                        embed.set_image(url=artwork_media_url)
                        await message.channel.send(embed=embed)

                    # edit the original message to suppress any embed from twitter proper
                    await message.edit(suppress=True)
