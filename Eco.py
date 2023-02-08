"""Eco.py"""
import os
from asyncio import sleep
from datetime import datetime, time, timedelta
from random import randint, uniform
from typing import Optional

from discord import Embed
from discord.ext.commands import Cog, command
from pytz import timezone

import utils
from Converters import Bool, Country, Id, IsMyNick, Product, Quality


class Eco(Cog):
    """Eco Commands"""

    def __init__(self, bot):
        self.bot = bot

    @command()
    async def contract(self, ctx, contract_id: Optional[Id] = 0, *, nick: IsMyNick):
        """Accept specific contract id.
        Write 0 as contract_id to get the list of contracts"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        if contract_id == 0:
            tree = await self.bot.get_content(f"{base_url}contracts.html", return_tree=True)
            text = [x.text_content().strip().replace("\n", " ").replace("\t", "") for x in tree.xpath('//*[@id="esim-layout"]//div[2]//ul//li')[:5]]
            links = utils.get_ids_from_path(tree, '//*[@id="esim-layout"]//div[2]//ul//li//a')[::2][:5]
            if links:
                embed = Embed(title=nick)
                embed.add_field(name="Contracts (first 5)", value="\n".join(f"[{t}]({base_url}profile.html?id={link})" for t, link in zip(text, links)))
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"**{nick}** no pending contracts")
        else:
            payload = {'action': "ACCEPT", "id": contract_id, "submit": "Accept"}
            url = await self.bot.get_content(f"https://{ctx.channel.name}.e-sim.org/contract.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def bid(self, ctx, auction: Id, price: float, delay: Optional[Bool] = False, *, nick: IsMyNick):
        """Bidding an auction few seconds before its end"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(f"{base_url}auction.html?id={auction}", return_tree=True)

        if delay:
            try:
                auction_time = str(tree.xpath(f'//*[@id="auctionClock{auction}"]')[0].text)
            except Exception:
                return await ctx.send(f"**{nick}** ERROR: This auction has probably finished. if you think this"
                                      f" is a mistake - set delay to False")
            h, m, s = auction_time.split(":")
            t = randint(15, 60)
            delay_in_seconds = int(h) * 3600 + int(m) * 60 + int(s) - t
            await ctx.send(f"**{nick}** Ok, I will bid ~{t} seconds before the auction ends")
            await sleep(delay_in_seconds)
        if not delay or not self.bot.should_break(ctx):
            payload = {'action': "BID", 'id': auction, 'price': f"{float(price):.2f}"}
            url = await self.bot.get_content(base_url + "auctionAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def cc(self, ctx, countries, max_price: float, amount: float, *, nick: IsMyNick):
        """Buying specific amount of coins, up to a pre-determined price.
        (It can help if there are many small offers, like NPC)"""
        countries = [await Country().convert(ctx, country.strip()) for country in countries.split(",")]
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        for country in countries:
            bought_amount = 0
            for _ in range(10):  # 10 pages
                tree = await self.bot.get_content(f"{base_url}monetaryMarket.html?buyerCurrencyId={country}", return_tree=True)
                prices = tree.xpath("//td[3]//b/text()")
                ids = [ID.value for ID in tree.xpath("//td[4]//form[1]//input[@value][2]")][:len(prices)]
                amounts = tree.xpath('//td[2]//b/text()')[:len(prices)]
                offer_id = None
                for offer_id, offer_amount, price in zip(ids, amounts, prices):
                    if self.bot.should_break(ctx):
                        return
                    try:
                        offer_amount, price = float(offer_amount), float(price)
                        if price > max_price:
                            await ctx.send(f"**{nick}** The price is too high ({price}).")
                            break

                        payload = {'action': "buy", 'id': offer_id, 'ammount': round(min(offer_amount, amount - bought_amount), 2),
                                   'stockCompanyId': '', 'submit': 'Buy'}
                        url = await self.bot.get_content(f"{base_url}monetaryMarket.html?buyerCurrencyId={country}", data=payload)
                        if "MM_POST_OK_BUY" not in str(url):
                            await ctx.send(f"ERROR: <{url}>")
                            break
                        await ctx.send(f"**{nick}** Bought {payload['ammount']} coins at {price} each.")
                        bought_amount += payload['ammount']
                        if bought_amount >= amount:
                            break
                        await sleep(uniform(0, 2))
                        # sleeping for a random time between 0 and 2 seconds. feel free to change it

                    except Exception as error:
                        await ctx.send(f"**{nick}** ERROR {error}")
                        await sleep(5)
                if offer_id and offer_id != ids[-1]:
                    break
            await ctx.send(f"**{nick}** bought total {round(bought_amount, 2)} coins.")
            await sleep(uniform(0, 4))

    @command()
    async def buy(self, ctx, market: Country, amount: int, quality: Optional[Quality], product: Product, *, nick: IsMyNick):
        """Buy products at the given market (auto fly with Q5 ticket)."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        if not quality:
            quality = 5
        if not product:
            return await ctx.send(f"**{nick}** ERROR: Invalid input")

        products_bought = 0
        while products_bought < amount and not self.bot.should_break(ctx):
            tree = await self.bot.get_content(f"{base_url}productMarket.html?resource={product}&quality={quality}&countryId={market}", return_tree=True)
            try:
                product_id = tree.xpath('//*[@id="command"]/input[1]')[0].value
            except IndexError:
                await ctx.send(f"**{nick}** ERROR: there are no Q{quality} {product} in the market.")
                break
            stock = int(tree.xpath("//tr[2]//td[3]/text()")[0])
            cost = float([x.strip() for x in tree.xpath("//tr[2]//td[4]//text()") if x.strip()][0])
            quantity = min(stock, amount)
            payload = {'action': "buy", 'id': product_id, 'quantity': quantity, "submit": "Buy"}
            url = await self.bot.get_content(base_url + "productMarket.html", data=payload)
            await ctx.send(f"**{nick}** Quantity: {quantity}. Price: {cost} each. <{url}>")
            if "POST_PRODUCT_BUY_OK" not in url:
                break
            products_bought += quantity

    @command()
    async def donate(self, ctx, donation_type, data, receiver_id: Id, *, nick: IsMyNick):
        """
        Donating specific EQ ID(s) to a specific user.
        `donation_type` can be eq or gold.
        if you want to donate eq, write its ids at `data`, separated by adjacent commas.
        if you want to donate gold, write the amount at `data`.
        if you want to donate product, send contract :)
        """
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        if "eq" in donation_type.lower():
            results = []
            ids = [int(x.strip()) for x in data.split(",") if x.strip()]
            for index, eq_id in enumerate(ids):
                payload = {"equipmentId": eq_id, "id": receiver_id, "reason": " ", "submit": "Donate"}
                url = await self.bot.get_content(base_url + "donateEquipment.html", data=payload)
                results.append(f"ID {eq_id} - <{url}>")
            await ctx.send(f"**{nick}**\n" + "\n".join(results))
        elif donation_type.lower() == "gold":
            if not data.replace('.', '', 1).isdigit():
                await ctx.send(f"**{nick}** ERROR: you must provide the sum to donate")
            else:
                payload = {"currencyId": 0, "sum": data, "reason": "", "submit": "Donate"}
                url = await self.bot.get_content(f"{base_url}donateMoney.html?id={receiver_id}", data=payload)
                await ctx.send(f"**{nick}** <{url}>")
        else:
            await ctx.send(f"**{nick}** ERROR: you can donate eq or gold only, not {donation_type}")

    @command()
    async def job(self, ctx, company_id: Optional[int] = 0, ticket_quality: Optional[Quality] = 5,  *, nick: IsMyNick):
        """Leaving current job and applying to the given company_id or to the best offer at the local market."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        if company_id != 0:
            api_citizen = await self.bot.get_content(f"{base_url}apiCitizenByName.html?name={nick.lower()}")
            tree = await self.bot.get_content(f"{base_url}company.html?id={company_id}", return_tree=True)
            region = utils.get_ids_from_path(tree, '//div[1]//div[2]//div[5]//div[1]//div//div[1]//div//div[4]//a')[0]
            await ctx.invoke(self.bot.get_command("fly"), region, ticket_quality, nick=nick)
            job_ids = tree.xpath('//td[4]//input[1]')
            skills = [int(x) for x in tree.xpath('//td[1]/text()') if x.isdigit()]
            job_id = None
            for job_id, skill in zip(job_ids, skills):
                if api_citizen["economySkill"] >= skill:
                    break
            if job_id is not None:
                job_id = job_id.value
            else:
                return await ctx.send(f"**{nick}** ERROR: There are no job offers in <{base_url}company.html?id={company_id}> for your skill.")
        else:
            tree = await self.bot.get_content(base_url + "jobMarket.html", return_tree=True)
            job_id = tree.xpath("//tr[2]//td[6]//input[1]")[0].value

        url = await self.bot.get_content(base_url + "jobMarket.html", data={"id": job_id, "submit": "Apply"})
        if "APPLY_FOR_JOB_ALREADY_HAVE_JOB" in url:
            await self.bot.get_content(base_url + "work.html", data={'action': "leave", "submit": "Leave job"})
            url = await self.bot.get_content(base_url + "jobMarket.html", data={"id": job_id, "submit": "Apply"})
            if "APPLY_FOR_JOB_ALREADY_HAVE_JOB" in url:
                return await ctx.send(f"**{nick}** ERROR: Couldn't apply for a new job. Perhaps you should wait 6 hours.")
        await ctx.send(f"**{nick}** <{url}>")
        await ctx.invoke(self.bot.get_command("work"), nicks=nick)

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

        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        if ctx.invoked_with.lower() == "split":
            payload = {'action': "SPLIT", "itemId": int(ids_or_quality.strip())}
            url = await self.bot.get_content(base_url + "equipmentAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")
        elif "," in ids_or_quality:
            eq1, eq2, eq3 = [eq.strip() for eq in ids_or_quality.split(",")]
            payload = {'action': "MERGE", f'itemId[{eq1}]': eq1, f'itemId[{eq2}]': eq2, f'itemId[{eq3}]': eq3}
            url = await self.bot.get_content(base_url + "equipmentAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")

        else:
            await ctx.send(f"**{nick}** On it!")
            max_q_to_merge = int(ids_or_quality.lower().replace("q", ""))  # max_q_to_merge - including
            results = []
            error = False
            for _ in range(5):
                tree = await self.bot.get_content(f'{base_url}storage.html?storageType=EQUIPMENT', return_tree=True)
                ids = tree.xpath('//*[starts-with(@id, "cell")]/a/text()')
                items = tree.xpath('//*[starts-with(@id, "cell")]/b/text()')
                eqs_dict = {}
                for eq_id, item in zip(ids, items):
                    quality = int(item.split()[0].replace("Q", ""))
                    if quality < max_q_to_merge + 1:
                        if quality not in eqs_dict:
                            eqs_dict[quality] = []
                        eqs_dict[quality].append(int(eq_id.replace("#", "")))
                for i in range(1, max_q_to_merge + 1):
                    for z in range(len(eqs_dict.get(i, [])) // 3):
                        if self.bot.should_break(ctx):
                            error = True
                            break
                        eq1, eq2, eq3 = eqs_dict[i][z * 3:z * 3 + 3]
                        payload = {'action': "MERGE", f'itemId[{eq1}]': eq1, f'itemId[{eq2}]': eq2, f'itemId[{eq3}]': eq3}
                        url = await self.bot.get_content(base_url + "equipmentAction.html", data=payload)
                        results.append(f"<{url}>")
                        await sleep(uniform(0, 2))
                        if url == "http://www.google.com/":
                            # e-sim error
                            await sleep(5)

                        elif "?actionStatus=CONVERT_ITEM_OK" not in url:
                            # no money etc
                            error = True
                            break
                    if results:
                        await ctx.send(f"**{nick}**\n" + "\n".join(results)[:1950])
                        results.clear()
                    if error:
                        break
                if error:
                    break
            await ctx.send(f"**{nick}**\n" + "\n".join(results)[:1950])

        await ctx.invoke(self.bot.get_command("eqs"), nick=nick)

    @command()
    async def mm(self, ctx, *, nicks):
        """Sells all currencies in your account in the appropriate markets & edit current offers if needed."""
        async for nick in utils.get_nicks(ctx.channel.name, nicks):
            base_url = f"https://{ctx.channel.name}.e-sim.org/"
            api = await self.bot.get_content(base_url + "apiCountries.html")
            storage_tree = await self.bot.get_content(base_url + "storage.html?storageType=MONEY", return_tree=True)
            for i in range(2, 30):
                if self.bot.should_break(ctx):
                    return
                try:
                    currency = storage_tree.xpath(f'//*[@id="storageConteiner"]//div//div//div//div[{i}]/text()')[-1].strip()
                    cc = [i["id"] for i in api if i["currencyName"] == currency][0]
                    value = storage_tree.xpath(f'//*[@id="storageConteiner"]//div//div//div//div[{i}]/b/text()')[0]
                    tree = await self.bot.get_content(f'{base_url}monetaryMarket.html?buyerCurrencyId={cc}&sellerCurrencyId=0', return_tree=True)
                    try:
                        ratio = float(str(tree.xpath("//tr[2]//td[3]/b")[0].text).strip())
                    except Exception:
                        ratio = 0.1
                    payload = {"offeredMoneyId": cc, "buyedMoneyId": 0, "value": value,
                               "exchangeRatio": round(ratio - 0.0001, 4), "submit": "Post new offer"}
                    await self.bot.get_content(base_url + "monetaryMarket.html?action=post", data=payload)
                    await ctx.send(f"**{nick}** posted {value} {currency} for {payload['exchangeRatio']}")
                except Exception:
                    break
            tree = await self.bot.get_content(base_url + "monetaryMarket.html", return_tree=True)
            ids = tree.xpath('//*[@id="command"]//input[1]')
            for i in range(2, 30):
                if self.bot.should_break(ctx):
                    return
                try:
                    currency = tree.xpath(f'//*[@id="esim-layout"]//table[2]//tr[{i}]//td[1]/text()')[-1].strip()
                    cc = [i["id"] for i in api if i["currencyName"] == currency][0]
                    tree = await self.bot.get_content(f'{base_url}monetaryMarket.html?buyerCurrencyId={cc}&sellerCurrencyId=0', return_tree=True)
                    seller = tree.xpath("//tr[2]//td[1]/a/text()")[0].strip()
                    if seller.lower() != nick.lower():
                        try:
                            ratio = float(str(tree.xpath("//tr[2]//td[3]/b")[0].text))
                        except Exception:
                            ratio = 0.1
                        payload = {"id": ids[i - 2].value, "rate": round(ratio - 0.0001, 4), "submit": "Edit"}
                        await self.bot.get_content(base_url + "monetaryMarket.html?action=change", data=payload)
                        await ctx.send(f"**{nick}** edited {currency} for {payload['rate']}")
                except Exception:
                    break

    @command()
    async def sell(self, ctx, quantity: int, quality: Optional[Quality], product: Product, price: float, country: Country, *, nick: IsMyNick):
        """Sell products at market."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        payload = {'storageType': 'PRODUCT', 'action': 'POST_OFFER', 'product': f'{quality or 5}-{product}',
                   'countryId': country, 'quantity': quantity, 'price': price}
        url = await self.bot.get_content(base_url + "storage.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def auction(self, ctx, ids, price: float, hours: int, *, nick: IsMyNick):
        """Sell specific EQ ID(s) & reshuffle & upgrade at auctions.
        `ids` MUST be separated by a comma, and without spaces (or with spaces, but within quotes)
        set `ids=ALL` if you want to sell all your eqs."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        results = []
        if ids.lower() == "all":
            tree = await self.bot.get_content(base_url + 'storage.html?storageType=EQUIPMENT', return_tree=True)
            ids = tree.xpath('//*[starts-with(@id, "cell")]/a/text()')
        else:
            ids = [x.strip() for x in ids.split(",") if x.strip()]
        for eq_id in ids:
            if self.bot.should_break(ctx):
                return
            eq_id = eq_id.replace(base_url + "showEquipment.html?id=", "").replace("#", "").strip()
            if eq_id == "reshuffle":
                item = "SPECIAL_ITEM 20"
            elif eq_id == "upgrade":
                item = "SPECIAL_ITEM 19"
            else:
                item = f"EQUIPMENT {eq_id}"
            payload = {'action': "CREATE_AUCTION", 'price': price, "id": item, "length": hours,
                       "submit": "Create auction"}
            url = await self.bot.get_content(base_url + "auctionAction.html", data=payload)
            if "CREATE_AUCTION_ITEM_EQUIPED" in url:
                ctx.invoked_with = "unwear"
                await ctx.invoke(self.bot.get_command("wear"), ids, nick=nick)
                url = await self.bot.get_content(base_url + "auctionAction.html", data=payload)
            results.append(f"ID {eq_id} - <{url}>")
        await ctx.send(f"**{nick}**\n" + "\n".join(results))

    @command(aliases=["w", "work+"])
    async def work(self, ctx, *, nicks):
        """`work+` -> for premium users"""

        server = ctx.channel.name
        async for nick in utils.get_nicks(server, nicks):
            base_url = f"https://{server}.e-sim.org/"
            if ctx.invoked_with.lower() == "work+":
                payload1 = {'task': "WORK", "action": "put", "submit": "Add plan"}
                payload2 = {'task': "TRAIN", "action": "put", "submit": "Add plan"}
                await self.bot.get_content(base_url + "taskQueue.html", data=payload1)
                await sleep(uniform(1, 2))
                await self.bot.get_content(base_url + "taskQueue.html", data=payload2)

            tree = await self.bot.get_content(base_url + "work.html", return_tree=True)
            await sleep(uniform(3, 20))

            train_first = randint(1, 2) == 1
            if train_first and tree.xpath('//*[@id="taskButtonTrain"]//@href'):
                await self.bot.get_content(base_url + "train/ajax", data={"action": "train"})
                await ctx.send(f"**{nick}** Trained successfully")
                await sleep(uniform(3, 30))

            if tree.xpath('//*[@id="taskButtonWork"]//@href'):
                if tree.xpath('//*[@id="workButton"]'):
                    await self.bot.get_content(base_url + "work/ajax", data={"action": "work"}, return_tree=True)
                else:
                    try:
                        region = utils.get_ids_from_path(
                            tree, '//div[1]//div[2]//div[5]//div[1]//div//div[1]//div//div[4]//a')[0]
                    except Exception:
                        return await ctx.send(f"**{nick}** ERROR: I couldn't find in which region your work is. If you don't have a job, see `.help job`")
                    await ctx.invoke(self.bot.get_command("fly"), region, 5, nick=nick)
                    await self.bot.get_content(base_url + "work/ajax", data={"action": "work"})
                tree = await self.bot.get_content(base_url + "work.html", return_tree=True)
                if not tree.xpath('//*[@id="taskButtonWork"]//@href'):
                    data = await utils.find_one(server, "info", nick)
                    data["Worked at"] = datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%Y-%m-%d %H:%M:%S")
                    await utils.replace_one(server, "info", nick, data)
                    await ctx.send(f"**{nick}** Worked successfully")
                else:
                    await ctx.send(f"**{nick}** ERROR: Couldn't work")
            else:
                await ctx.send(f"**{nick}** Already worked")
            if not train_first and tree.xpath('//*[@id="taskButtonTrain"]//@href'):
                await sleep(uniform(3, 30))
                await self.bot.get_content(base_url + "train/ajax", data={"action": "train"})
                await ctx.send(f"**{nick}** Trained successfully")
            if randint(1, 100) < 37:  # 37%
                await sleep(uniform(1, 3))
                await ctx.invoke(self.bot.get_command("read"), nicks=nick)

    @command()
    async def auto_work(self, ctx, work_sessions: Optional[int] = 1, chance_to_skip_work: Optional[int] = 7, *, nicks):
        """Works at random times throughout every day"""
        async for nick in utils.get_nicks(ctx.channel.name, nicks):
            data = {"work_sessions": work_sessions, "chance_to_skip_work": chance_to_skip_work}
            if await utils.save_command(ctx, "auto", "work", data):
                await ctx.send(f"**{nick}** The command already running. I will update the data if needed.")
                return  # Command already running
            await ctx.send(f"**{nick}** I will work from now on {work_sessions} times every day, with {chance_to_skip_work}% chance to skip work."
                           f"If you wish to stop it, type `.cancel auto_work`")

            tz = timezone('Europe/Berlin')
            while not self.bot.should_break(ctx):  # for every day:
                sec_between_works = (24 * 60 * 60) // work_sessions
                now = datetime.now(tz)
                midnight = tz.localize(datetime.combine(now + timedelta(days=1), time(0, 0, 0, 0)))

                for i in range(work_sessions):
                    sec_til_midnight = (midnight - now).seconds
                    work_session_start = sec_between_works if i else 0
                    work_session_end = sec_til_midnight % sec_between_works + (sec_between_works if i else 0)
                    if work_session_start < min(work_session_end, sec_til_midnight-20):
                        await sleep(uniform(work_session_start, min(work_session_end, sec_til_midnight - 20)))
                    now = datetime.now(tz)
                    if self.bot.should_break(ctx):
                        break
                    if randint(1, 100) > chance_to_skip_work:
                        await ctx.invoke(self.bot.get_command("work"), nicks=nick)
                    if (midnight - now).seconds < sec_between_works:
                        break

                # Updated the data once a day (allow the user to change chance_to_skip_work or work_sessions)
                data = (await utils.find_one("auto", "work", os.environ['nick']))[ctx.channel.name]
                chance_to_skip_work = data["chance_to_skip_work"]
                work_sessions = data["work_sessions"]

                # sleep till midnight
                await sleep((midnight - now).seconds + 20)
            await utils.remove_command(ctx, "auto", "work")

    @command()
    async def send_contracts(self, ctx, contract_id: Id, contract_name, *, nick: IsMyNick):
        """
        Sending specific contract to all your friends,
        unless you have already sent them that contract, they have rejected your previous one, or they are staff members"""
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        blacklist = set()
        blacklist = await staff_list(self.bot, base_url, blacklist)
        blacklist = await _received(self.bot, base_url, blacklist, contract_name)
        blacklist = await remove_rejected(self.bot, base_url, blacklist)
        async for friend in _friends_list(self.bot, nick, server):
            if self.bot.should_break(ctx):
                break
            if friend not in blacklist:
                payload = {'id': contract_id, 'action': "PROPOSE", 'citizenProposedTo': friend, 'submit': 'Propose'}
                for _ in range(10):
                    try:
                        url = await self.bot.get_content(base_url + "contract.html", data=payload)
                        await ctx.send(f"**{friend}:** <{url}>")
                        break  # sent
                    except Exception as error:
                        await ctx.send(f"**{nick}** {error} while sending to {friend}")
        await ctx.send(f"**{nick}** done.")


async def remove_rejected(bot, base_url, blacklist, alerts_filter="CONTRACTS", text="has rejected your"):
    """remove rejected contracts"""
    tree = await bot.get_content(base_url + 'notifications.html?filter=' + alerts_filter, return_tree=True)
    last_page = utils.get_ids_from_path(tree, "//ul[@id='pagination-digg']//li[last()-1]/") or ['1']
    last_page = int(last_page[0])
    for page in range(1, int(last_page)+1):
        if page != 1:
            tree = await bot.get_content(f'{base_url}notifications.html?filter={alerts_filter}&page={page}', return_tree=True)
        for tr in range(2, 22):
            if text in " ".join(tree.xpath(f"//tr[{tr}]//td[2]/text()")):
                blacklist.add(tree.xpath(f"//tr[{tr}]//td[2]//a[1]/text()")[0].strip())
    return blacklist


async def _friends_list(bot, nick, server, skip_banned_and_inactive=True):
    base_url = f"https://{server}.e-sim.org/"
    api_citizen = await bot.get_content(f'{base_url}apiCitizenByName.html?name={nick.lower()}')

    for page in range(1, 100):
        tree = await bot.get_content(f'{base_url}profileFriendsList.html?id={api_citizen["id"]}&page={page}', return_tree=True)
        for div in range(1, 13):
            friend = tree.xpath(f'//div//div[1]//div[{div}]/a/text()')
            if skip_banned_and_inactive:
                status = (tree.xpath(f'//div//div[1]//div[{div}]/a/@style') or [""])[0]
                if "color: #f00" in status or "color: #888" in status:  # Banned or inactive
                    continue
            if not friend:
                return
            yield friend[0].strip()


async def staff_list(bot, base_url, blacklist):
    """Get staff list"""
    tree = await bot.get_content(f"{base_url}staff.html", return_tree=True)
    nicks = tree.xpath('//*[@id="esim-layout"]//a/text()')
    for nick in nicks:
        blacklist.add(nick.strip())
    return blacklist


async def _received(bot, base_url, blacklist, contract_name):
    tree = await bot.get_content(f'{base_url}contracts.html', return_tree=True)
    li = 0
    while True:
        try:
            li += 1
            line = tree.xpath(f'//*[@id="esim-layout"]//div[2]//ul//li[{li}]/a/text()')
            if contract_name.lower() in line[0].strip().lower() and "offered to" in tree.xpath(f'//*[@id="esim-layout"]//div[2]//ul//li[{li}]/text()')[1]:
                blacklist.add(line[1].strip())
        except Exception:
            break
    return blacklist


def setup(bot):
    """setup"""
    bot.add_cog(Eco(bot))
