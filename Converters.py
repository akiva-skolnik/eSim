from os import environ

from discord.ext.commands import Converter, BadArgument


class IsMyNick(Converter):
    async def convert(self, ctx, nick: str) -> str:
        if nick.lower() == environ.get(ctx.channel.name, environ['nick']).lower():
            return nick
        else:
            raise


class Side(Converter):
    async def convert(self, ctx, side: str) -> str:
        if "d" in side.lower():
            return "defender"
        elif "a" in side.lower():
            return "attacker"
        else:
            raise BadArgument(f'ERROR: "side" must be "defender" or "attacker" (not {side})')


class Bool(Converter):
    async def convert(self, ctx, answer: str) -> bool:
        answer = answer.lower()
        if "y" in answer or "t" in answer:
            return True
        elif "n" in answer or "f" in answer:
            return False
        else:
            raise BadArgument(f'ERROR: please choose yes/no or true/false (not {answer})')


class Quality(Converter):
    async def convert(self, ctx, q: str) -> int:
        quality = "".join([x for x in str(q) if x.isdigit()])
        if quality.isdigit():
            return int(quality)
        else:
            raise BadArgument(f"""Wrong quality format (`{q}`).

            **Valid formats:**
            - `Q5`
            - `q5`
            - `5`""")


class Id(Converter):
    async def convert(self, ctx, id_or_link: str) -> int:
        id = id_or_link.split("id=")[-1].split("&")[0]
        if id.isdigit():
            return int(id)
        else:
            raise BadArgument(f"Wrong link / id {id_or_link}")


class Product(Converter):
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
        else:
            raise BadArgument(f"""Wrong product (`{product}`).

            **Product list:**
            {", ".join(products).title()}""")


class Dmg(Converter):
    async def convert(self, ctx, dmg: str) -> int:
        res = float(dmg.replace('k', '000'))
        if "." in dmg:
            res *= 1000 ** dmg.count("k")
        return int(res)
