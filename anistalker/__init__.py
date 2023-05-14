from .anistalker import AniStalker

async def setup(bot):
    await bot.add_cog(AniStalker(bot))
