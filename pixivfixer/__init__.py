from .pixivfixer import PixivFixer

async def setup(bot):
    await bot.add_cog(PixivFixer(bot))
