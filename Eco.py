from asyncio import sleep
from datetime import datetime, time, timedelta
from random import randint
from typing import Optional

from discord import Embed
from discord.ext.commands import Cog, command
from pytz import timezone

from Converters import Bool, Id, IsMyNick, Product, Quality
import utils


class Eco(Cog):
    """Eco Commands"""

    def __init__(self, bot):
        self.bot = bot

    @command()
    async def contract(self, ctx, contract_id: Optional[Id] = 0, *, nick: IsMyNick):
        """Accept specific contract id.
        Write 0 as contract_id to get the list of contracts"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if contract_id == 0:
            tree = await self.bot.get_content(f"{URL}contracts.html", return_tree=True)
            text = [x.text_content().strip().replace("\n", " ").replace("\t", "") for x in tree.xpath('//*[@id="esim-layout"]//div[2]//ul//li')[:5]]
            links = tree.xpath('//*[@id="esim-layout"]//div[2]//ul//li//a/@href')[::2][:5]
            if links:
                embed = Embed(title=nick)
                embed.add_field(name="Contracts (first 5)", value="\n".join(f"[{t}]({URL+link})" for t, link in zip(text, links)))
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"**{nick}** no pending contracts")
        else:
            payload = {'action': "ACCEPT", "id": contract_id, "submit": "Accept"}
            url = await self.bot.get_content(f"https://{ctx.channel.name}.e-sim.org/contract.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def bid(self, ctx, auction: Id, price: float, delay: Optional[Bool] = False, *, nick: IsMyNick):
        """Bidding an auction few seconds before it's end"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(f"{URL}auction.html?id={auction}", return_tree=True)
        try:
            auction_time = str(tree.xpath(f'//*[@id="auctionClock{auction}"]')[0].text)
        except:
            return await ctx.send(f"**{nick}** ERROR: This auction has probably finished. if you think this is a mistake -"
                                  " you are welcome to run the function again, but this time write the delay yourself")
        if delay:
            h, m, s = auction_time.split(":")
            delay_in_seconds = int(h) * 3600 + int(m) * 60 + int(s) - 30
            await sleep(delay_in_seconds)
        payload = {'action': "BID", 'id': auction, 'price': f"{float(price):.2f}"}
        url = await self.bot.get_content(URL + "auctionAction.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def cc(self, ctx, country_id: int, max_price: float, amount: float, *, nick: IsMyNick):
        """Buying specific amount of coins, up to a pre-determined price.
        (It can help if there are many small offers, like NPC)"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        bought_amount = 0

        for Index in range(10):  # 10 pages
            tree = await self.bot.get_content(f"{URL}monetaryMarket.html?buyerCurrencyId={country_id}", return_tree=True)
            IDs = [ID.value for ID in tree.xpath("//td[4]//form[1]//input[@value][2]")]
            amounts = tree.xpath('//td[2]//b/text()')
            prices = tree.xpath("//td[3]//b/text()")
            for ID, offer_amount, price in zip(IDs, amounts, prices):
                try:
                    offer_amount, price = float(offer_amount), float(price)
                    if price > max_price:
                        await ctx.send(f"**{nick}** The price is too high ({price}).")
                        break
                    
                    payload = {'action': "buy", 'id': ID, 'ammount': min(offer_amount, amount - bought_amount),
                               'stockCompanyId': '', 'submit': 'Buy'}
                    url = await self.bot.get_content(f"{URL}monetaryMarket.html?buyerCurrencyId={country_id}", data=payload)
                    if "MM_POST_OK_BUY" not in str(url):
                        await ctx.send(f"ERROR: <{url}>")
                        break
                    await ctx.send(f"**{nick}** Bought {payload['ammount']} coins at {price} each.")
                    bought_amount += payload['ammount']
                    if bought_amount >= amount:
                        break
                    await sleep(randint(0, 2))
                    # sleeping for a random time between 0 and 2 seconds. feel free to change it
                    
                except Exception as error:
                    await ctx.send(f"**{nick}** {error}")
                    await sleep(5)
            if IDs and ID != IDs[-1]:
                break
        await ctx.send(f"**{nick}** bought total {round(bought_amount, 2)} coins.")

    @command()
    async def buy(self, ctx, amount: int, quality: Optional[Quality], product: Product, *, nick: IsMyNick):
        """Buy products at the LOCAL market (consider flying first)."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if not quality:
            quality = 5
        if not product:
            return await ctx.send(f"**{nick}** ERROR: Invalid input")
        tree = await self.bot.get_content(f"{URL}storage/money", return_tree=True)
        keys = [x.strip() for x in tree.xpath("//div//div/text()") if x]
        values = [float(x.strip()) for x in tree.xpath("//div//div/b/text()") if x]
        my_money = dict(zip([x for x in keys if x], values))
        products_bought = 0
        mm_bought = None
        while products_bought < amount:
            tree = await self.bot.get_content(f"{URL}productMarket.html?resource={product}&quality={quality}", return_tree=True)
            product_id = tree.xpath('//*[@id="command"]/input[1]')[0].value
            stock = int(tree.xpath(f"//tr[2]//td[3]/text()")[0])
            raw_cost = tree.xpath(f"//tr[2]//td[4]//text()")
            cost = float(raw_cost[2].strip())
            if mm_bought is None:
                mm_type = raw_cost[-1].strip()
                mm_bought = my_money.get(mm_type, 0)
            mm_needed = min(stock, amount - products_bought) * cost
            while mm_bought < mm_needed:
                tree1 = await self.bot.get_content(URL + "monetaryMarket.html", return_tree=True)
                try:
                    ID = tree1.xpath("//tr[2]//td[4]//form[1]//input[@value][2]")[0].value
                    cc_offer = float(tree1.xpath('//tr[2]//td[2]//b')[0].text)
                    price = float(tree1.xpath('//tr[2]//td[3]//b')[0].text)
                except:
                    await ctx.send(f"ERROR: there's no money in the monetary market")
                    break
                cc_quantity = min(cc_offer, (amount - products_bought) * cost)
                # TODO: No gold case
                payload = {'action': "buy", 'id': ID, 'ammount': cc_quantity}
                url = await self.bot.get_content(URL + "monetaryMarket.html", data=payload)
                if "MM_POST_OK_BUY" not in str(url):
                    await ctx.send(f"ERROR: <{url}>")
                    break
                await ctx.send(f"**{nick}** Bought {payload['ammount']} coins at {price} each.")
                mm_bought += cc_quantity

            quantity = min(stock, amount, mm_bought // cost - products_bought)
            payload = {'action': "buy", 'id': product_id, 'quantity': quantity, "submit": "Buy"}
            url = await self.bot.get_content(URL + "productMarket.html", data=payload)
            await ctx.send(f"**{nick}** Quantity: {quantity}. Price: {cost} {mm_type} each. <{url}>")
            if "POST_PRODUCT_NOT_ENOUGH_MONEY" in str(url):
                break
            products_bought += quantity

    @command()
    async def donate(self, ctx, type, data, receiver_id: Id, *, nick: IsMyNick):
        """
        Donating specific EQ ID(s) to a specific user.
        `type` can be eq or gold.
        if you want to donate eq, write its ids at `data`, separated by adjacent commas.
        if you want to donate gold, write the amount at `data`.
        if you want to donate product, send contract :)
        """
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        if type.lower() == "eq":
            results = []
            ids = [int(x.strip()) for x in data.split(",") if x.strip()]
            for Index, ID in enumerate(ids):
                payload = {"equipmentId": ID, "id": receiver_id, "reason": " ", "submit": "Donate"}
                url = await self.bot.get_content(URL + "donateEquipment.html", data=payload)
                results.append(f"ID {ID} - <{url}>")
            await ctx.send(f"**{nick}**\n" + "\n".join(results))
        elif type.lower() == "gold":
            if not data.replace('.', '', 1).isdigit():
                await ctx.send(f"**{nick}** ERROR: you must provide the sum to donate")
            else:
                payload = {"currencyId": 0, "sum": data, "reason": "", "submit": "Donate"}
                url = await self.bot.get_content(f"{URL}donateMoney.html?id={receiver_id}", data=payload)
                await ctx.send(f"**{nick}** <{url}>")
        else:
            await ctx.send(f"**{nick}** ERROR: you can donate eq or gold only, not {type}")

    @command()
    async def job(self, ctx, company_id: Optional[int] = 0, *, nick: IsMyNick):
        """Leaving current job and applying to the given company_id or to the best offer at the local market."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"

        try:
            await self.bot.get_content(URL + "work.html", data={'action': "leave", "submit": "Leave job"})
        except:
            pass
        if company_id != 0:
            tree = await self.bot.get_content(f"{URL}company.html?id={company_id}", return_tree=True)
            try:
                job_id = tree.xpath('//tr[2]//td[4]//input[1]')[0].value
            except:
                return await ctx.send(f"**{nick}** ERROR: There are no job offers in this company.")
        else:
            tree = await self.bot.get_content(URL + "jobMarket.html", return_tree=True)
            job_id = tree.xpath("//tr[2]//td[6]//input[1]")[0].value
        url = await self.bot.get_content(URL + "jobMarket.html", data={"id": job_id, "submit": "Apply"})
        await ctx.send(f"**{nick}** <{url}>")
        await ctx.invoke(self.bot.get_command("work"), nick=nick)

    @command(aliases=["split"])
    async def merge(self, ctx, ids_or_quality, *, nick: IsMyNick):
        """
        Merges a specific EQ IDs / all EQs up to specific Q (included).

        Examples:
        .merge 36191,34271,33877 My Nick  ->   Merges eqs id 36191, 34271 and 33877
        .merge 5 My Nick                  ->   Merges all Q1-6 eqs in your storage.
        .split 36191 My Nick              ->   Splits eq id 36191
        IMPORTANT NOTE: No spaces in `ids_or_quality`! only commas.
        """

        URL = f"https://{ctx.channel.name}.e-sim.org/"
        if ctx.invoked_with.lower() == "split":
            payload = {'action': "SPLIT", "itemId": int(ids_or_quality.strip())}
            url = await self.bot.get_content(URL + "equipmentAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")
        elif "," in ids_or_quality:
            EQ1, EQ2, EQ3 = [eq.strip() for eq in ids_or_quality.split(",")]
            payload = {'action': "MERGE", f'itemId[{EQ1}]': EQ1, f'itemId[{EQ2}]': EQ2, f'itemId[{EQ3}]': EQ3}
            url = await self.bot.get_content(URL + "equipmentAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")

        else:
            max_q_to_merge = int(ids_or_quality.lower().replace("q", ""))  # max_q_to_merge - including
            results = list()
            for Index in range(5):
                tree = await self.bot.get_content(f'{URL}storage.html?storageType=EQUIPMENT', return_tree=True)
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
                            url = await self.bot.get_content(URL + "equipmentAction.html", data=payload)
                            results.append(f"<{url}>")
                            await sleep(1)
                            if url == "http://www.google.com/":
                                # e-sim error
                                await sleep(5)

                            elif "?actionStatus=CONVERT_ITEM_OK" not in url:
                                # no money etc
                                break
                    if results:
                        await ctx.send(f"**{nick}**\n" + "\n".join(results))
                        results.clear()
            if results:
                await ctx.send(f"**{nick}**\n" + "\n".join(results))
        await ctx.invoke(self.bot.get_command("eqs"), nick=nick)

    @command()
    async def mm(self, ctx, *, nick: IsMyNick):
        """Sells all currencies in your account in the appropriate markets & edit current offers if needed."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        api = await self.bot.get_content(URL + "apiCountries.html")
        storage_tree = await self.bot.get_content(URL + "storage.html?storageType=MONEY", return_tree=True)
        for i in range(2, 20):
            try:
                CC = storage_tree.xpath(f'//*[@id="storageConteiner"]//div//div//div//div[{i}]/text()')[-1].strip()
                cc = [i["id"] for i in api if i["currencyName"] == CC][0]
                value = storage_tree.xpath(f'//*[@id="storageConteiner"]//div//div//div//div[{i}]/b/text()')[0]
                tree = await self.bot.get_content(f'{URL}monetaryMarket.html?buyerCurrencyId={cc}&sellerCurrencyId=0', return_tree=True)
                try:
                    MM = str(tree.xpath("//tr[2]//td[3]/b")[0].text).strip()
                except:
                    MM = 0.1
                payload = {"offeredMoneyId": cc, "buyedMoneyId": 0, "value": value,
                           "exchangeRatio": round(float(MM) - 0.0001, 4), "submit": "Post new offer"}
                await self.bot.get_content(URL + "monetaryMarket.html?action=post", data=payload)
                await ctx.send(f"**{nick}** posted {value} {CC} for {payload['exchangeRatio']}")
            except:
                break

        tree = await self.bot.get_content(URL + "monetaryMarket.html", return_tree=True)
        IDs = tree.xpath('//*[@id="command"]//input[1]')
        for i in range(2, 20):
            try:
                CC = tree.xpath(f'//*[@id="esim-layout"]//table[2]//tr[{i}]//td[1]/text()')[-1].strip()
                cc = [i["id"] for i in api if i["currencyName"] == CC][0]
                tree = await self.bot.get_content(f'{URL}monetaryMarket.html?buyerCurrencyId={cc}&sellerCurrencyId=0', return_tree=True)
                seller = tree.xpath("//tr[2]//td[1]/a/text()")[0].strip()
                if seller != nick:
                    try:
                        MM = tree.xpath("//tr[2]//td[3]/b")[0].text
                    except:
                        MM = 0.1
                    payload = {"id": IDs[i - 2].value, "rate": round(float(MM) - 0.0001, 4), "submit": "Edit"}
                    url = await self.bot.get_content(URL + "monetaryMarket.html?action=change", data=payload)
                    await ctx.send(f"**{nick}** <{url}>")
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
            url = await self.bot.get_content(URL + "auctionAction.html", data=payload)
            if "CREATE_AUCTION_ITEM_EQUIPED" in url:
                ctx.invoked_with = "unwear"
                await ctx.invoke(self.bot.get_command("wear"), ids, nick=nick)
                url = await self.bot.get_content(URL + "auctionAction.html", data=payload)
            results.append(f"ID {ID} - <{url}>")
        await ctx.send(f"**{nick}**\n" + "\n".join(results))
    
    @command(aliases=["w", "work+"])
    async def work(self, ctx, *, nick: IsMyNick):
        """`work+` -> for premium users"""

        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        if ctx.invoked_with.lower() == "work+":
            payload1 = {'task': "WORK", "action": "put", "submit": "Add plan"}
            payload2 = {'task': "TRAIN", "action": "put", "submit": "Add plan"}
            await self.bot.get_content(URL + "taskQueue.html", data=payload1)
            await self.bot.get_content(URL + "taskQueue.html", data=payload2)

        tree = await self.bot.get_content(URL + "work.html", return_tree=True)
        if tree.xpath('//*[@id="taskButtonWork"]//@href'):
            try:
                region = tree.xpath(
                    '//div[1]//div[2]//div[5]//div[1]//div//div[1]//div//div[4]//a/@href')[0].split("=")[1]
                payload = {'countryId': int(region) // 6 + 1, 'regionId': region, 'ticketQuality': 5}
                await self.bot.get_content(URL + "travel.html", data=payload)
            except:
                return await ctx.send(f"**{nick}** ERROR: I couldn't find in which region your work is. If you don't have a job, see `.help job`")

            await self.bot.get_content(URL + "train/ajax", data={"action": "train"})
            await ctx.send(f"**{nick}** Trained successfully")
            Tree = await self.bot.get_content(URL + "work/ajax", data={"action": "work"}, return_tree=True)
            if not Tree.xpath('//*[@id="taskButtonWork"]//@href'):
                data = await utils.find_one(server, "info", nick)
                data["Worked at"] = datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%Y-%m-%d %H:%M:%S")
                await utils.replace_one(server, "info", nick, data)
                await ctx.send(f"**{nick}** Worked successfully")
            else:
                await ctx.send(f"**{nick}** ERROR: Couldn't work")
        else:
            await ctx.send(f"**{nick}** Already worked")
        await ctx.invoke(self.bot.get_command("read"), nick=nick)

    @command()
    async def auto_work(self, ctx, work_sessions: Optional[int] = 1, *, nick: IsMyNick):
        """work at random times throughout the day"""
        sec_between_works = (24*60*60) // work_sessions
        while True:  # for every day:
            tz = timezone('Europe/Berlin')
            now = datetime.now(tz)
            midnight = tz.localize(datetime.combine(now+timedelta(days=1), time(0, 0, 0, 0)))
            sec_til_midnight = (midnight - now).seconds
            x = randint(0, min(sec_til_midnight, sec_between_works - 2000))
            await sleep(x)
            await ctx.invoke(self.bot.get_command("work"), nick=nick)
            i = work_sessions - 2

            while x + sec_between_works < sec_til_midnight:
                x = randint(x + sec_between_works + 20, sec_til_midnight - i*sec_between_works - i*60)
                await sleep(x)
                await ctx.invoke(self.bot.get_command("work"), nick=nick)
                i -= 1

            # sleep till midnight
            tz = timezone('Europe/Berlin')
            now = datetime.now(tz)
            midnight = tz.localize(datetime.combine(now+timedelta(days=1), time(0, 0, 0, 0)))
            await sleep((midnight-now).seconds+20)

    async def _received(self, URL, blacklist, contract_name):
        tree = await self.bot.get_content(f'{URL}contracts.html', return_tree=True)
        li = 0
        while True:
            try:
                li += 1
                line = tree.xpath(f'//*[@id="esim-layout"]//div[2]//ul//li[{li}]/a/text()')
                if contract_name.lower() in line[0].strip().lower() and "offered to" in tree.xpath(f'//*[@id="esim-layout"]//div[2]//ul//li[{li}]/text()')[1]:
                    blacklist.add(line[1].strip())
            except:
                break
        return blacklist

    async def _remove_rejected(self, URL, blacklist):
        tree = await self.bot.get_content(URL+'notifications.html?filter=CONTRACTS', return_tree=True)
        last_page = tree.xpath("//ul[@id='pagination-digg']//li[last()-1]//@href") or ['page=1']
        last_page = int(last_page[0].split('page=')[1])
        for page in range(1, int(last_page)+1):
            if page != 1:
                tree = await self.bot.get_content(f'{URL}notifications.html?filter=CONTRACTS&page={page}', return_tree=True)
            for tr in range(2, 22):
                if "   has rejected your  " in tree.xpath(f"//tr[{tr}]//td[2]/text()"):
                    blacklist.add(str(tree.xpath(f"//tr[{tr}]//td[2]//a[1]")[0].text).strip())
        return blacklist

    async def _friends_list(self, nick, server):
        URL = f"https://{server}.e-sim.org/"
        apiCitizen = await self.bot.get_content(f'{URL}apiCitizenByName.html?name={nick.lower()}')

        for page in range(1, 100):
            tree = await self.bot.get_content(f'{URL}profileFriendsList.html?id={apiCitizen["id"]}&page={page}', return_tree=True)
            for div in range(1, 13):
                friend = tree.xpath(f'//div//div[1]//div[{div}]/a/text()')
                if not friend:
                    return
                yield friend[0].strip()

    async def staff_list(self, URL, blacklist):
        tree = await self.bot.get_content(f"{URL}staff.html", return_tree=True)
        nicks = tree.xpath('//*[@id="esim-layout"]//a/text()')
        for nick in nicks:
            blacklist.add(nick.strip())
        return blacklist

    @command()
    async def send_contracts(self, ctx, contract_id: Id, contract_name, *, nick: IsMyNick):
        """
        Sending specific contract to all your friends,
        unless you have already sent them that contract, they have rejected your previous one or they are staff members"""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        blacklist = set()
        blacklist = await self.staff_list(URL, blacklist)
        blacklist = await self._received(URL, blacklist, contract_name)
        blacklist = await self._remove_rejected(URL, blacklist)
        async for friend in self._friends_list(nick, server):
            if friend not in blacklist:
                payload = {'id': contract_id, 'action': "PROPOSE", 'citizenProposedTo': friend, 'submit': 'Propose'}
                for _ in range(10):
                    try:
                        url = await self.bot.get_content(URL + "contract.html", data=payload)
                        await ctx.send(f"**{friend}:** <{url}>")
                        break  # sent
                    except Exception as error:
                        await ctx.send(f"**{nick}** {error} while sending to {friend}")
        await ctx.send(f"**{nick}** done.")


def setup(bot):
    bot.add_cog(Eco(bot))
