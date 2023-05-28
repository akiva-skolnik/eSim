"""Converters.py"""
from asyncio import sleep
from random import uniform

from aiohttp import ClientSession
from discord.ext.commands import BadArgument, Converter, errors

import utils

session = ClientSession()


class IsMyNick(Converter):
    """IsMyNick Converter"""
    async def convert(self, ctx, nick: str) -> str:
        server = ctx.channel.name
        my_nick = utils.my_nick(server)
        nicks = [x.strip().lower() for x in nick.replace('"', "").replace("'", "").replace("\n", ",").split(",")]
        if nick.lower() == "all":
            nicks.append(my_nick.lower())
            await sleep(uniform(1, 20))
        elif len(nicks) > 1:
            await sleep(uniform(0, len(nicks) * 2))
        if my_nick.lower() in nicks:
            return my_nick
        raise errors.CheckFailure


class Side(Converter):
    """Side Converter"""
    async def convert(self, ctx, side: str) -> str:
        if "d" in side.lower():
            return "defender"
        if "a" in side.lower():
            return "attacker"
        raise BadArgument(f'ERROR: "side" must be "defender" or "attacker" (not {side})')


class Quality(Converter):
    """Quality Converter"""
    async def convert(self, ctx, q: str) -> int:
        quality = "".join([x for x in str(q) if x.isdigit()])
        if quality.isdigit():
            return int(quality)
        raise BadArgument(f"""Wrong quality format (`{q}`).

            **Valid formats:**
            - `Q5`
            - `q5`
            - `5`""")


class Id(Converter):
    """Id Converter"""
    async def convert(self, ctx, id_or_link: str) -> int:
        id_or_link = id_or_link.split("id=")[-1].split("&")[0]
        if id_or_link.isdigit():
            return int(id_or_link)
        raise BadArgument(f"Wrong link / id {id_or_link}")


class Product(Converter):
    """Product Converter"""
    async def convert(self, ctx, product: str) -> str:
        product = product.upper()
        if product in ("DS", "DEFENSE SYSTEM"):
            product = "DEFENSE_SYSTEM"
        if product.endswith("S"):
            product = product[:-1]
        if product in ("DIAMOND", "DIAM"):
            product = "DIAMONDS"
        elif product in ("WEP", "WEAP"):
            product = "WEAPON"

        products = ["iron", "grain", "oil", "stone", "wood", "diamonds",
                    "weapon", "house", "gift", "food", "ticket", "defense_system", "hospital", "estate"]
        if product.lower() in products:
            return product
        raise BadArgument(f"""Wrong product (`{product}`).

            **Product list:**
            {", ".join(products).title()}""")


class Country(Converter):
    """Country Converter"""
    async def convert(self, ctx, country: str) -> int:
        if not country.isdigit():
            api = await session.get(f"https://{ctx.channel.name}.e-sim.org/apiCountries.html", ssl=True)
            country = next(x['id'] for x in await api.json(
                content_type=None) if x["name"].lower() == country.strip().lower())
        return country


class Dmg(Converter):
    """Dmg Converter"""
    async def convert(self, ctx, dmg: str) -> int:
        res = float(dmg.replace('k', '000'))
        if "." in dmg:
            res *= 1000 ** dmg.count("k")
        return int(res)
