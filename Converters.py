from os import environ

from discord.ext.commands import Converter


class IsMyNick(Converter):
    async def convert(self, ctx, nick):
        if nick.lower() == environ.get(ctx.channel.name, environ['nick']).lower():
            return nick
        else:
            raise
