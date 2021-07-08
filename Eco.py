from asyncio import sleep
from random import randint
from typing import Optional

from discord import Embed
from discord.ext.commands import Cog, command

from Converters import IsMyNick


class Eco(Cog):
    """Eco Commands"""

    def __init__(self, bot):
        self.bot = bot

    @command()
    async def contract(self, ctx, contract_id, *, nick: IsMyNick):
        """Accept specific contract id."""
        payload = {'action': "ACCEPT", "id": contract_id, "submit": "Accept"}
        url = await self.bot.get_content(f"https://{ctx.channel.name}.e-sim.org/contract.html", data=payload,
                                         login_first=True)
        await ctx.send(url)

    @command()
    async def bid(self, ctx, auction_id_or_link, price, delay, *, nick: IsMyNick):
        """Bidding an auction few seconds before it's end"""
        if delay.lower() not in ("yes", "no"):
            return await ctx.send(f"delay parameter must to be 'yes' or 'no' (not {delay})")
        else:
            delay = True if delay.lower() == "yes" else False
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if ".e-sim.org/auction.html?id=" in auction_id_or_link:
            auction_id_or_link = auction_id_or_link.split("=")[1]
        tree = await self.bot.get_content(f"{URL}auction.html?id={auction_id_or_link}", login_first=True)
        try:
            auction_time = str(tree.xpath(f'//*[@id="auctionClock{auction_id_or_link}"]')[0].text)
        except:
            await ctx.send("This auction has probably finished. if you think this is mistake -"
                           " you are welcome to run the function again, but this time write the delay yourself")
            return
        h, m, s = auction_time.split(":")
        if delay:
            delay_in_seconds = int(h) * 3600 + int(m) * 60 + int(s) - 30
            await sleep(delay_in_seconds)
        payload = {'action': "BID", 'id': auction_id_or_link, 'price': f"{float(price):.2f}"}
        url = await self.bot.get_content(URL + "auctionAction.html", data=payload)
        await ctx.send(url)

    @command()
    async def cc(self, ctx, country_id, max_price, buy_amount, *, nick: IsMyNick):
        """
        Buying specific amount of coins, up to a pre-determined price.
        (It can help if there are many small offers, like NPC)"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        max_price, buy_amount = float(max_price), float(buy_amount)
        bought_amount = 0

        for Index in range(10):  # 10 pages
            tree = await self.bot.get_content(f"{URL}monetaryMarket.html?buyerCurrencyId={country_id}",
                                              login_first=not Index)
            IDs = tree.xpath("//td[4]//form[1]//input[@value][2]")
            IDs = [ID.value for ID in IDs]
            amounts = tree.xpath('//td[2]//b/text()')
            prices = tree.xpath("//td[3]//b/text()")
            for ID, amount, price in zip(IDs, amounts, prices):
                try:
                    amount, price = float(amount), float(price)
                    if price <= max_price and bought_amount <= buy_amount:
                        payload = {'action': "buy", 'id': ID,
                                   'ammount': amount if amount <= buy_amount - bought_amount else buy_amount - bought_amount}
                        url = await self.bot.get_content(f"{URL}monetaryMarket.html?buyerCurrencyId={country_id}",
                                                         data=payload)
                        await ctx.send(url)
                        if "MM_POST_OK_BUY" not in str(url):
                            return
                        else:
                            bought_amount += amount
                        await sleep(randint(0, 2))
                        # sleeping for a random time between 0 and 2 seconds. feel free to change it
                    else:
                        return
                except Exception as error:
                    await ctx.send(error)
                    await sleep(5)

    @command()
    async def products(self, ctx, amount: int, quality: Optional[int] = 5, product="wep", *, nick: IsMyNick):
        """Buy products at the LOCAL market (consider flying first)."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if not quality:
            quality = 5
        if not product:
            return await ctx.send("Invalid input")
        amount = int(amount)
        MMBought = 0
        tree = await self.bot.get_content(f"{URL}storage/money", login_first=True)
        keys = [x.strip() for x in tree.xpath("//div//div/text()") if x]
        values = [float(x.strip()) for x in tree.xpath("//div//div/b/text()") if x]
        my_money = dict(zip([x for x in keys if x], values))
        productsBought = 0
        for loop_count in range(5):
            tree = await self.bot.get_content(f"{URL}productMarket.html?resource={product}&quality={quality}")
            productId = tree.xpath('//*[@id="command"]/input[1]')[0].value
            stock = int(tree.xpath(f"//tr[2]//td[3]/text()")[0])
            raw_cost = tree.xpath(f"//tr[2]//td[4]//text()")
            cost = float(raw_cost[2].strip())
            if not loop_count:
                mm_type = raw_cost[-1].strip()
                if mm_type in my_money:
                    MMBought = my_money[mm_type]
            MM_needed = (amount - productsBought) * cost if (amount - productsBought) <= stock else stock * cost
            for _ in range(5):
                if MMBought >= MM_needed:
                    break
                tree1 = await self.bot.get_content(URL + "monetaryMarket.html")
                ID = tree1.xpath("//tr[2]//td[4]//form[1]//input[@value][2]")[0].value
                CC_offer = float(tree1.xpath('//tr[2]//td[2]//b')[0].text)
                cc_quantity = CC_offer if CC_offer < (amount - productsBought) * cost else (
                                                                                                   amount - productsBought) * cost
                # Todo: No gold case
                payload = {'action': "buy", 'id': ID, 'ammount': cc_quantity}
                url = await self.bot.get_content(URL + "monetaryMarket.html", data=payload)
                await ctx.send(url)
                MMBought += cc_quantity

            quantity = int(MMBought / cost) - productsBought
            if quantity > stock:
                quantity = stock
            if quantity > amount:
                quantity = amount
            payload = {'action': "buy", 'id': productId, 'quantity': quantity, "submit": "Buy"}
            url = await self.bot.get_content(URL + "productMarket.html", data=payload)
            if "POST_PRODUCT_NOT_ENOUGH_MONEY" in str(url):
                break
            await ctx.send(url)
            productsBought += quantity
            if productsBought >= amount:
                break

    @command()
    async def donate(self, ctx, ids, receiver_id: int, *, nick: IsMyNick):
        """
        Donating specific EQ ID(s) to specific user.
        If you need anything else (gold, products) use contract (see contract function)
        """
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        results = []
        ids = [x.strip() for x in ids.split(",") if x.strip()]
        for Index, ID in enumerate(ids):
            payload = {"equipmentId": ID.strip(), "id": receiver_id, "reason": " ", "submit": "Donate"}
            url = await self.bot.get_content(URL + "donateEquipment.html", data=payload, login_first=not Index)
            results.append(f"ID {ID} - {url}")
        await ctx.send("\n".join(results))

    async def eqs(self, ctx, *, nick: IsMyNick):
        """Shows list of EQs in storage."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(URL + 'storage.html?storageType=EQUIPMENT', login_first=True)
        original_IDs = tree.xpath(f'//*[starts-with(@id, "cell")]/a/text()')
        IDs = [f"[{ID}]({URL}showEquipment.html?id={ID.replace('#', '')})" for ID in original_IDs]
        if sum([len(x) for x in IDs]) > 1000:
            IDs = [ID for ID in original_IDs]
            # Eq id instead of link
        items = tree.xpath(f'//*[starts-with(@id, "cell")]/b/text()')
        results = []
        for ID, Item in zip(IDs, items):
            results.append(f"{ID}: {Item}")
        await ctx.send("\n".join(results))

    @command(aliases=["inventory"])
    async def inv(self, ctx, *, nick: IsMyNick):
        """
        shows all of your in-game inventory.
        """
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(f"{URL}storage.html?storageType=PRODUCT", login_first=True)
        tree2 = await self.bot.get_content(f"{URL}storage.html?storageType=SPECIAL_ITEM")
        container_1 = tree.xpath("//div[@class='storage']")
        special_items = tree2.xpath('//div[@class="specialItemInventory"]')
        gold = tree.xpath('//div[@class="sidebar-money"][1]/b/text()')[0]
        quantity = [gold]
        for item in special_items:
            if item.xpath('span/text()'):
                if item.xpath('b/text()')[0].lower() == "medkit":
                    quantity.append(item.xpath('span/text()')[0])
                elif "reshuffle" in item.xpath('b/text()')[0].lower():
                    quantity.append(item.xpath('span/text()')[0])
                elif "upgrade" in item.xpath('b/text()')[0].lower():
                    quantity.append(item.xpath('span/text()')[0])
        for item in container_1:
            quantity.append(item.xpath("div[1]/text()")[0].strip())
        products = [f"Gold"]
        for item in special_items:
            if item.xpath('span/text()'):
                if item.xpath('b/text()')[0].lower() == "medkit":
                    products.append(item.xpath('b/text()')[0])
                elif "reshuffle" in item.xpath('b/text()')[0].lower():
                    products.append("Reshuffles")
                elif "upgrade" in item.xpath('b/text()')[0].lower():
                    products.append("Upgrades")
        for item in container_1:
            name = item.xpath("div[2]/img/@src")[0].replace("//cdn.e-sim.org//img/productIcons/", "").replace(
                "Rewards/", "").replace(".png", "")
            if name.lower() in ["iron", "grain", "diamonds", "oil", "stone", "wood"]:
                quality = ""
            else:
                quality = item.xpath("div[2]/img/@src")[1].replace(
                    "//cdn.e-sim.org//img/productIcons/", "").replace(".png", "")
            products.append(f"{quality.title()} {name}" if quality else f"{name}")

        embed = Embed()
        for i in range(len(products) // 5 + 1):
            value = [f"**{a}**: {b}" for a, b in zip(products[i * 5:(i + 1) * 5], quantity[i * 5:(i + 1) * 5])]
            embed.add_field(name="**Products: **" if not i else u"\u200B",
                            value="\n".join(value) if value else u"\u200B")
        embed.set_footer(text="Inventory")
        await ctx.send(embed=embed)

    @command()
    async def job(self, ctx, *, nick: IsMyNick):
        """Leaving job and apply for the best offer at the local market."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        await self.bot.get_content(URL + "work.html", data={'action': "leave", "submit": "Submit"}, login_first=True)
        tree = await self.bot.get_content(URL + "jobMarket.html")
        jobId = tree.xpath("//tr[2]//td[6]//input[1]")[0].value
        url = await self.bot.get_content(URL + "jobMarket.html", data={"id": jobId, "submit": "Apply"})
        await ctx.send(url)
        await ctx.invoke(self.bot.get_command("work"), nick=nick)

    @command()
    async def merge(self, ctx, ids_or_quality, *, nick: IsMyNick):
        """
        Merges specific EQ IDs / all EQs up to specific Q (included).

        Examples:
        .merge 36191,34271,33877 My Nick  ->   Merges eqs id 36191, 34271 and 33877
        .merge 5 My Nick  ->   Merges all Q1-6 eqs in your storage.
        IMPORTANT NOTE: No spaces in `ids_or_quality`! only commas.
        """

        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if "," in ids_or_quality:
            EQ1, EQ2, EQ3 = [eq.strip() for eq in ids_or_quality.split(",")]
            payload = {'action': "MERGE", f'itemId[{EQ1}]': EQ1, f'itemId[{EQ2}]': EQ2, f'itemId[{EQ3}]': EQ3}
            merge_request = await self.bot.get_content(URL + "equipmentAction.html", data=payload, login_first=True)
            await ctx.send(merge_request)

        else:
            max_q_to_merge = int(ids_or_quality.lower().replace("q", ""))  # max_q_to_merge - including
            for Index in range(5):
                tree = await self.bot.get_content(f'{URL}storage.html?storageType=EQUIPMENT', login_first=not Index)
                IDs = tree.xpath(f'//*[starts-with(@id, "cell")]/a/text()')
                items = tree.xpath(f'//*[starts-with(@id, "cell")]/b/text()')
                DICT = {}
                for ID, item in zip(IDs, items):
                    Q = int(item.split()[0].replace("Q", ""))
                    if Q < max_q_to_merge + 1:
                        if Q not in DICT:
                            DICT[Q] = []
                        DICT[Q].append(int(ID.replace("#", "")))
                for i in range(1, max_q_to_merge + 1):
                    if i in DICT and len(DICT[i]) > 2:
                        for z in range(int(len(DICT[i]) / 3)):
                            EQ1, EQ2, EQ3 = DICT[i][z * 3:z * 3 + 3]
                            payload = {'action': "MERGE", f'itemId[{EQ1}]': EQ1, f'itemId[{EQ2}]': EQ2,
                                       f'itemId[{EQ3}]': EQ3}
                            merge_request = await self.bot.get_content(URL + "equipmentAction.html", data=payload)
                            await ctx.send(merge_request)
                            await sleep(1)
                            if merge_request == "http://www.google.com/":
                                # e-sim error
                                await sleep(5)

                            elif "?actionStatus=CONVERT_ITEM_OK" not in merge_request:
                                # no money etc
                                break

    @command()
    async def mm(self, ctx, *, nick: IsMyNick):
        """Sells all currencies in your account in the appropriate markets & edit current offers if needed."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        api = await self.bot.get_content(URL + "apiCountries.html")
        storage_tree = await self.bot.get_content(URL + "storage.html?storageType=MONEY", login_first=True)
        for i in range(2, 20):
            try:
                CC = storage_tree.xpath(f'//*[@id="storageConteiner"]//div//div//div//div[{i}]/text()')[-1].strip()
                cc = [i["id"] for i in api if i["currencyName"] == CC][0]
                value = storage_tree.xpath(f'//*[@id="storageConteiner"]//div//div//div//div[{i}]/b/text()')[0]
                tree = await self.bot.get_content(f'{URL}monetaryMarket.html?buyerCurrencyId={cc}&sellerCurrencyId=0')
                try:
                    MM = str(tree.xpath("//tr[2]//td[3]/b")[0].text).strip()
                except:
                    MM = 0.1
                payload = {"offeredMoneyId": cc, "buyedMoneyId": 0, "value": value,
                           "exchangeRatio": round(float(MM) - 0.0001, 4), "submit": "Post new offer"}
                send_monetary_market = await self.bot.get_content(URL + "monetaryMarket.html?action=post", data=payload)
                await ctx.send(send_monetary_market)
            except:
                break

        tree = await self.bot.get_content(URL + "monetaryMarket.html")
        IDs = tree.xpath('//*[@id="command"]//input[1]')
        for i in range(2, 20):
            try:
                CC = tree.xpath(f'//*[@id="esim-layout"]//table[2]//tr[{i}]//td[1]/text()')[-1].strip()
                cc = [i["id"] for i in api if i["currencyName"] == CC][0]
                tree = await self.bot.get_content(f'{URL}monetaryMarket.html?buyerCurrencyId={cc}&sellerCurrencyId=0')
                seller = tree.xpath("//tr[2]//td[1]/a/text()")[0].strip()
                if seller != nick:
                    try:
                        MM = tree.xpath("//tr[2]//td[3]/b")[0].text
                    except:
                        MM = 0.1
                    payload = {"id": IDs[i - 2].value, "rate": round(float(MM) - 0.0001, 4), "submit": "Edit"}
                    edit_offer = await self.bot.get_content(URL + "monetaryMarket.html?action=change", data=payload)
                    await ctx.send(edit_offer)
            except:
                break

    @command()
    async def sell(self, ctx, ids, price: float, hours: int, *, nick: IsMyNick):
        """Sell specific EQ ID(s) & reshuffle & upgrade  at auctions.
        `ids` MUST be separated by a comma, and without spaces (or with spaces, but within quotes)"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        results = []
        ids = [x.strip() for x in ids.split(",") if x.strip()]
        for Index, ID in enumerate(ids):
            ID = ID.replace(URL + "showEquipment.html?id=", "").strip()
            if ID == "reshuffle":
                item = "SPECIAL_ITEM 20"
            elif ID == "upgrade":
                item = "SPECIAL_ITEM 19"
            else:
                item = f"EQUIPMENT {ID}"
            payload = {'action': "CREATE_AUCTION", 'price': price, "id": item, "length": hours,
                       "submit": "Create auction"}
            url = await self.bot.get_content(URL + "auctionAction.html", data=payload, login_first=not Index)
            if "CREATE_AUCTION_ITEM_EQUIPED" in url:
                ctx.invoked_with = "unwear"
                await ctx.invoke(self.bot.get_command("wear"), ids, nick=nick)
                url = await self.bot.get_content(URL + "auctionAction.html", data=payload)
            results.append(f"ID {ID} - {url}\n")
        await ctx.send("".join(results))

    @command(aliases=["w", "work+"])
    async def work(self, ctx, *, nick: IsMyNick):
        """`work+` -> for premium users"""

        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if ctx.invoked_with.lower() == "work+":
            payload1 = {'task': "WORK", "action": "put", "submit": "Add plan"}
            payload2 = {'task': "TRAIN", "action": "put", "submit": "Add plan"}
            await self.bot.get_content(URL + "taskQueue.html", data=payload1, login_first=True)
            await self.bot.get_content(URL + "taskQueue.html", data=payload2)

        tree = await self.bot.get_content(URL + "work.html", login_first=ctx.invoked_with.lower() == "work")
        if tree.xpath('//*[@id="taskButtonWork"]//@href'):
            try:
                region = tree.xpath(
                    '//div[1]//div[2]//div[5]//div[1]//div//div[1]//div//div[4]//a/@href')[0].split("=")[1]
                payload = {'countryId': int(int(region) / 6) + (int(region) % 6 > 0), 'regionId': region,
                           'ticket_quality': 5}
                await self.bot.get_content(URL + "travel.html", data=payload)
            except:
                return await ctx.send("I couldn't find in which region your work is. Maybe you don't have a job")

            await self.bot.get_content(URL + "train/ajax", data={"action": "train"})
            await ctx.send("Trained successfully")
            Tree = await self.bot.get_content(URL + "work/ajax", data={"action": "work"}, return_url=True)
            if not Tree.xpath('//*[@id="taskButtonWork"]//@href'):
                await ctx.send("Worked successfully")
            else:
                await ctx.send("Couldn't work")
        else:
            await ctx.send("Already worked")


def setup(bot):
    bot.add_cog(Eco(bot))
