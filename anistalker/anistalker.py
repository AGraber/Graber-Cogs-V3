import discord
import aiohttp
import json
import random
import time
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import humanize_list
import aiohttp
from discord.ext import tasks

anilist_api_url = 'https://graphql.anilist.co'

# GraphQL queries

user_id_query = '''
query ($username: String) {
    User (name: $username) {
        id
    }
}
'''

activity_query = '''
query ($id: Int, $created: Int) {
    Page {
        activities (userId: $id, createdAt_greater: $created, sort: ID, type: MEDIA_LIST) {
            ... on ListActivity {
                type
                status
                siteUrl
                user {
                    name
                    siteUrl
                    avatar {
                        large
                    }
                }
                progress
                media {
                    title {
                        romaji
                    }
                    coverImage {
                        extraLarge,
                        color,
                    }
                }
            }
        }
    }
}
'''

class AniStalker(commands.Cog, name="AniStalker"):
    def __init__(self, bot: discord.Client):
        self.fetch_activities.start()

        default_global = {}
        default_guild = {
            "anilist_users": {},
            "channel": None
        }

        self.bot = bot
        self.config = Config.get_conf(self, identifier=181020010)
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    def cog_unload(self):
        self.fetch_activities.cancel()

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def anistalkerchannel(self, ctx: commands.Context, target: discord.TextChannel):
        """Set the channel where AniStalker will send updates"""
        await self.config.guild(ctx.guild).channel.set(target.id)
        await ctx.send(f'{target.name} will now receive updates from AniStalker!')

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def anistalkeruser(self, ctx: commands.Context, target: str):
        """Add a user for AniStalker to stalk"""
        
        # get the id
        variables = {'username': target}

        data = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(anilist_api_url, json={'query': user_id_query, 'variables': variables}) as res:
                    data = await res.json()
        except aiohttp.ClientError:
            await ctx.send('Failed to fetch data from Anilist GraphQL API. The website is likely experiencing high load and/or is down.')
            return
        
        if 'errors' in data:
            await ctx.send(f'An error occured while trying to fetch data from Anilist GraphQL API: {data["errors"][0]["message"]}')
            return

        user_id = data['data']['User']['id']

        async with self.config.guild(ctx.guild).anilist_users() as anilist_users:
            if str(user_id) in anilist_users:
                del anilist_users[str(user_id)]
                await ctx.send(f'Removing {target} (ID: {user_id}) from AniStalker!')
            else:
                anilist_users[user_id] = int(time.time())
                await ctx.send(f'Adding {target} (ID: {user_id}) to AniStalker!')

    @tasks.loop(seconds=30.0)
    async def fetch_activities(self):
        for guild in self.bot.guilds:
            channel = await self.config.guild(guild).channel()
            if channel == None:
                continue

            async with self.config.guild(guild).anilist_users() as anilist_users:

                for user_id, timestamp in anilist_users.items():
                    variables = {'id': user_id, 'created': timestamp}
                    data = None

                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(anilist_api_url, json={'query': activity_query, 'variables': variables}) as res:
                                if res.status != 200 or len(await res.read()) == 0:
                                    continue
                                data = await res.json()
                    except aiohttp.ClientError as the_exception:
                        #await self.bot.get_channel(channel).send('Failed to fetch data from Anilist GraphQL API. The website is likely experiencing high load and/or is down.')
                        print(the_exception)
                        return

                    if data == None:
                        continue

                    if 'errors' in data:
                        await self.bot.get_channel(channel).send(f'An error occured while trying to fetch data from Anilist GraphQL API for user {user_id}: {data["errors"][0]["message"]}')
                        return

                    activities = data['data']['Page']['activities']
                    for activity in activities:
                        title = None
                        description = ''
                        url = ''
                        
                        status = activity['status']
                        if status == "watched episode":
                            title = f"Watched {activity['media']['title']['romaji']}"
                            url = activity['siteUrl']
                            if '-' in activity['progress']:
                                description = f'Episodes {activity["progress"]}'
                            else:
                                description = f'Episode {activity["progress"]}'
                        elif status == "rewatched episode":
                            title = f"Rewatched {activity['media']['title']['romaji']}"
                            url = activity['siteUrl']
                            if '-' in activity['progress']:
                                description = f'Episodes {activity["progress"]}'
                            else:
                                description = f'Episode {activity["progress"]}'
                        elif status == "read chapter":
                            title = f"Read {activity['media']['title']['romaji']}"
                            url = activity['siteUrl']
                            if '-' in activity['progress']:
                                description = f'Chapters {activity["progress"]}'
                            else:
                                description = f'Chapter {activity["progress"]}'
                        elif status == "completed":
                            title = f"Completed {activity['media']['title']['romaji']}"
                            url = activity['siteUrl']
                        elif status == "rewatched":
                            title = f"Completed rewatching {activity['media']['title']['romaji']}"
                            url = activity['siteUrl']

                        if title == None:
                            continue # unsupported activity

                        color = activity['media']['coverImage']['color']
                        if color == None:
                            color = 0x3db4f2
                        else:
                            color = int(color.lstrip("#"), 16)
                            
                            

                        embed = discord.Embed(title=title, url=url, description=description, color=color)
                        embed.set_author(name=activity['user']['name'], url=activity['user']['siteUrl'], icon_url=activity['user']['avatar']['large'])
                        embed.set_thumbnail(url=activity['media']['coverImage']['extraLarge'])
                        await self.bot.get_channel(channel).send(embed=embed)

                    anilist_users[user_id] = int(time.time())
