from os import environ

from discord.ext.commands import Converter, BadArgument


class IsMyNick(Converter):
    async def convert(self, ctx, nick):
        if nick.lower() == environ.get(ctx.channel.name, environ['nick']).lower():
            return nick
        else:
            raise


class Side(Converter):
    async def convert(self, ctx, side):
        if side.lower() not in ("defender", "attacker"):
            raise BadArgument(f'ERROR: "side" must be "defender" or "attacker" (not {side})')
        else:
            return side.lower()


def Quality(q):
    try:
        return int("".join([x for x in q if x.isdigit()]))
    except ValueError:
        raise BadArgument(f"""Wrong quality format (`{q}`).

        **Valid formats:**
        - `Q5`
        - `q5`
        - `5`""")


class Product(Converter):
    async def convert(self, ctx, product):
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
