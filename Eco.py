"""Eco.py"""
import os
import json
from asyncio import sleep
from datetime import datetime, time, timedelta
from random import choice, randint, uniform
from typing import Optional

from discord import Embed
from discord.ext.commands import Cog, command
from pytz import timezone

import utils
from Converters import Country, Id, IsMyNick, Product, Quality


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
    async def bid(self, ctx, auction: Id, price: float, delay: Optional[bool] = False, *, nick: IsMyNick):
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
        if not delay or not utils.should_break(ctx):
            payload = {'action': "BID", 'id': auction, 'price': f"{float(price):.2f}"}
            url = await self.bot.get_content(base_url + "auctionAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")

    @command(hidden=True)
    async def set_auctions_prices(self, ctx, nick: IsMyNick, *, prices: str = "{}"):
        """For each item, you can specify prices in the following formats:
        1. A single price, for example: `"helmet3": 1.1`. In this case, the bot will bid 1.1 gold on all Q3 helmets.
        2. Multimple prices, for example `"helmet3": "1, 1.1, 1.2"`. In this case, the bot will bid any price from that list randomly.
        3. Range of prices, for example `"helmet3": "1-1.2"`. In this case, the bot will bid any price from that range (min 1, max 1.2).
        4. Any combination of the above, for example `"helmet3": "2, 1-1.2, 1.5-1.8"`. In this case, the bot will bid 2g on third of the auctions, another third will be from the range 1-1.2, and the rest from the range 1.5-1.8

        - Leave `prices` untouched if you want to see the current prices.
        - You can also bid companies by qualities: `{"q1": "0", "q2": "0", "q3": "0", "q4": "0", "q5": "0"}
        """
        server = ctx.channel.name
        file_name = f"auctions_prices_{server}.json"
        prices = json.loads(prices.replace("'", '"'))
        if not prices:
            if file_name in os.listdir():
                with open(file_name, "r", encoding="utf-8") as file:
                    await ctx.send("Current prices:\n" + file.read())
            else:
                await ctx.send(
                    "Here's a draft:\n"
                    f'.set_auctions_prices "{nick}" ' +
                    '```json\n{"helmet1": "0.1-0.3", "helmet2": "0.6,0.7", "helmet3": "0", "helmet4": "0", "helmet5": "0", "helmet6": "0", "helmet7": "0",\n'
                    '"vision1": "0", "vision2": "0", "vision3": "0", "vision4": "0", "vision5": "0", "vision6": "0", "vision7": "0",\n'
                    '"weapon1": "0", "weapon2": "0", "weapon3": "0", "weapon4": "0", "weapon5": "0", "weapon6": "0", "weapon7": "0",\n'
                    '"offhand1": "0", "offhand2": "0", "offhand3": "0", "offhand4": "0", "offhand5": "0", "offhand6": "0", "offhand7": "0",\n'
                    '"armor1": "0", "armor2": "0", "armor3": "0", "armor4": "0", "armor5": "0", "armor6": "0", "armor7": "0",\n'
                    '"pants1": "0", "pants2": "0", "pants3": "0", "pants4": "0", "pants5": "0", "pants6": "0", "pants7": "0",\n'
                    '"shoes1": "0", "shoes2": "0", "shoes3": "0", "shoes4": "0", "shoes5": "0", "shoes6": "0", "shoes7": "0",\n'
                    '"charm1": "0", "charm2": "0", "charm3": "0", "charm4": "0", "charm5": "0", "charm6": "0", "charm7": "0",\n\n'

                    '"jinxedElixirMili": "0", "jinxedElixirMini": "0", "jinxedElixirStandard": "0", "jinxedElixirMajor": "0", "jinxedElixirHuge": "0", "jinxedElixirExceptional": "0",\n'
                    '"fineseElixirMili": "0", "fineseElixirMini": "0", "fineseElixirStandard": "0", "fineseElixirMajor": "0", "fineseElixirHuge": "0", "fineseElixirExceptional": "0",\n'
                    '"bloodyMessElixirMili": "0", "bloodyMessElixirMini": "0", "bloodyMessElixirStandard": "0", "bloodyMessElixirMajor": "0", "bloodyMessElixirHuge": "0", "bloodyMessElixirExceptional": "0",\n'
                    '"luckyElixirMili": "0", "luckyElixirMini": "0", "luckyElixirStandard": "0", "luckyElixirMajor": "0", "luckyElixirHuge": "0", "luckyElixirExceptional": "0",\n\n'

                    '"reshuffle": "0", "upgrade": "0", "vacations": "0", "spa": "0", "resistance": "0", "bunker": "0", "steroids": "0", "tank": "0",\n'
                    '"camouflage_first_class": "0", "camouflage_second_class": "0", "camouflage_third_class": "0",\n'
                    '"bandagea": "0","bandageb": "0","bandagec": "0","bandaged": "0","bandagee": "0","bandagef": "0",\n'
                    '"painDealer1h": "0", "painDealer10h": 0, "painDealer25h": ""}```')
                await ctx.send_help("set_auctions_prices")
        else:
            with open(file_name, "w", encoding="utf-8") as file:
                json.dump(prices, file)
            await ctx.send(f"**{nick}** I have created a file named `{file_name}` containing those prices.\n"
                           f"You can edit it any time, or invoke the command again with all prices.\n"
                           f'You can now use `.bid_all_auctions {nick}`')

    @command()
    async def bid_all_auctions(self, ctx, *, nick: IsMyNick):
        """Bidding on all auctions.
        Type `.help set_auctions_prices` to see how to set the prices."""
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        file_name = f"auctions_prices_{server}.json"
        if file_name not in os.listdir():
            return await ctx.invoke(self.bot.get_command("set_auctions_prices"), nick=nick)
        else:
            with open(file_name, "r", encoding="utf-8") as file:
                prices = json.load(file)
        await ctx.send(f"**{nick}** Ok. You can cancel with `.cancel bid_all_auctions {nick}`")

        page = 1
        while not utils.should_break(ctx):
            tree = await self.bot.get_content(f"{base_url}auctions.html?page={page}", return_tree=True)
            buttons = tree.xpath("//*[@class='auctionButtons']/button[last()]")
            items = tree.xpath("//*[@class='auctionItem']//img[last()]//@src")
            current_prices = tree.xpath("//*[@class='auctionBidder']//b/text()")
            if not buttons:  # last page
                break
            results = []
            for item, price, button in zip(items, current_prices, buttons):
                item = item.split("/")[-1].split(".png")[0].replace("-", "_").replace("bandage_", "bandage")
                if item.count("_") == 1:
                    item = item.split("_")[0]
                elif item.count("_") == 2:  # eq_reshuffle_big.png
                    item = item.split("_")[1].split("-")[0]
                auction_id = button.attrib['data-id']
                min_bid = button.attrib['data-minimal-outbid']
                buyer = button.attrib['data-top-bidder']

                price = str(prices.get(item, "0")) or "0"
                price = choice(price.split(","))
                if "-" in price:
                    min_price, max_price = price.split("-")
                    price = round(uniform(float(min_price), float(max_price)), 2)
                if float(min_bid) > float(price) or buyer.lower() == nick.lower():
                    continue
                if utils.should_break(ctx):
                    break
                payload = {'action': "BID", 'id': auction_id, 'price': price}
                await self.bot.get_content(base_url + "auctionAction.html", data=payload)
                results.append(f"{base_url}auction.html?id={auction_id}, type: {item}, price: {price}")
                await sleep(randint(2, 7))
            if results:
                await ctx.send(f"**{nick}**\n" + "\n".join(results))
            page += 1
        if not utils.should_break(ctx):
            await ctx.send(f"**{nick}** Done bidding all auctions.")

    @command()
    async def cc(self, ctx, countries, max_price: float, amount: float, *, nick: IsMyNick):
        """Buying specific amount of coins, up to a pre-determined price.
        (It can help if there are many small offers, like NPC)"""
        countries = [await Country().convert(ctx, country.strip()) for country in countries.split(",")]
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        for country in countries:
            bought_amount = 0
            error = False
            for page in range(10):
                tree = await self.bot.get_content(f"{base_url}monetaryMarketOffers?sellerCurrencyId=0&buyerCurrencyId={country}&page=1", return_tree=True)
                amounts = tree.xpath("//*[@class='amount']//b/text()")
                ratios = tree.xpath("//*[@class='ratio']//b/text()")
                offers_ids = [int(x.attrib['data-id']) for x in tree.xpath("//*[@class='buy']/button")]
                try:
                    cc = tree.xpath("//*[@class='buy']/button")[0].attrib['data-buy-currency-name']
                except IndexError:
                    await ctx.send(f"**{nick}** country {country} - no offers found.")
                    break
                for offer_id, offer_amount, ratio in zip(offers_ids, amounts, ratios):
                    if utils.should_break(ctx):
                        return
                    try:
                        offer_amount, ratio = float(offer_amount), float(ratio)
                        if ratio > max_price:
                            await ctx.send(f"**{nick}** The price is too high ({ratio} per {cc}).")
                            error = True
                            break

                        payload = {'action': "buy", 'id': offer_id, 'ammount': round(min(offer_amount, amount - bought_amount), 2),
                                   'stockCompanyId': '', 'submit': 'Buy'}
                        url = await self.bot.get_content(f"{base_url}monetaryMarketOfferBuy.html", data=payload)
                        if "MM_POST_OK_BUY" not in str(url):
                            await ctx.send(f"ERROR: <{url}>")
                            error = True
                            break
                        await ctx.send(f"**{nick}** Bought {payload['ammount']} {cc} at {ratio} each.")
                        bought_amount += payload['ammount']
                        if bought_amount >= amount:
                            error = True
                            break
                        await sleep(uniform(0, 2))
                        # sleeping for a random time between 0 and 2 seconds. feel free to change it

                    except Exception as exc:
                        error = True
                        await ctx.send(f"**{nick}** ERROR {exc}")
                        await sleep(5)
                if error:
                    break

            if bought_amount > 0:
                await ctx.send(f"**{nick}** bought total {round(bought_amount, 2)} {cc}.")
                await sleep(uniform(0, 4))

    @command()
    async def buy(self, ctx, market: Country, amount: int, quality: Optional[Quality], product: Product, *, nick: IsMyNick):
        """Buy products at the given market."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        if not quality:
            quality = 5
        if not product:
            return await ctx.send(f"**{nick}** ERROR: Invalid input")

        while 0 < amount and not utils.should_break(ctx):
            tree = await self.bot.get_content(f"{base_url}productMarket.html?resource={product}&quality={quality}&countryId={market}", return_tree=True)
            data = tree.xpath("//*[@class='buy']/button")
            try:
                (data or tree.xpath('//*[@class="buy"]/button'))[0]
            except IndexError:
                await ctx.send(f"**{nick}** ERROR: there are no Q{quality} {product} in the market.")
                break
            if data:  # new format
                offer_id = data[0].attrib['data-id']
                stock = int(data[0].attrib['data-quantity'])
                cost = float(data[0].attrib['data-price'])
            else:
                offer_id = tree.xpath('//*[@id="command"]/input[1]')[0].value
                stock = int(tree.xpath("//tr[2]//td[3]/text()")[0])
                cost = float([x.strip() for x in tree.xpath("//tr[2]//td[4]//text()") if x.strip()][0])
            quantity = min(stock, amount)
            payload = {'action': "buy", 'id': offer_id, 'quantity': quantity, "submit": "Buy"}
            url = await self.bot.get_content(base_url + "productMarket.html", data=payload)
            await ctx.send(f"**{nick}** Quantity: {quantity}. Price: {cost} each. <{url}>")
            if "POST_PRODUCT_BUY_OK" not in url:
                break
            amount -= quantity

    @command()
    async def donate(self, ctx, donation_type, data, receiver_name: str, *, nick: IsMyNick):
        """
        Donating specific EQ ID(s) to a specific user.
        `donation_type` can be eq or gold.
        if you want to donate eq, write its ids at `data`, separated by adjacent commas.
        if you want to donate gold, write the amount at `data`.
        if you want to donate product, use this:
         .click nick https://primera.e-sim.org/donateProducts.html?id=0000  {"product": "5-WEAPON", "quantity": X}
        if you want to donate specific coin or specify reason, use this:
         .click nick https://primera.e-sim.org/donateMoney.html?id=0000     {"currencyId": 0, "sum": 0, "reason": ""}
         .click nick https://primera.e-sim.org/donateEquipment.html?id=0000 {"equipmentId": XX, "id": XXX, "reason": ""}

        You can also input receiver_id instead of receiver_name. If your nick is numerical, write it with a leading dot: ".000"
        """
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        if receiver_name.startswith("."):
            receiver_id = receiver_name[1:]
        elif receiver_name.isdigit():
            receiver_id = receiver_name
        else:
            api_citizen = await self.bot.get_content(f"{base_url}apiCitizenByName.html?name={receiver_name.lower()}")
            receiver_id = api_citizen["id"]

        if "eq" in donation_type.lower():
            results = []
            ids = [int(x.strip()) for x in data.split(",") if x.strip()]
            for index, eq_id in enumerate(ids):
                payload = {"equipmentId": eq_id, "id": receiver_id, "reason": "", "submit": "Donate"}
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
            if not await ctx.invoke(self.bot.get_command("fly"), region, ticket_quality, nick=nick):
                return
            job_ids = [job_id.value for job_id in tree.xpath('//tr//td[4]//form[1]/input[1]')]
            skills = [int(x) for x in tree.xpath('//td[1]/text()') if x.isdigit()]
            job_id = None
            for _job_id, skill in zip(job_ids, skills):
                if api_citizen["economySkill"] >= skill:
                    job_id = _job_id
                    break
            if job_id is None:
                return await ctx.send(f"**{nick}** ERROR: There are no job offers in <{base_url}company.html?id={company_id}> for your skill.")
        else:
            tree = await self.bot.get_content(base_url + "jobMarket.html", return_tree=True)
            job_id = tree.xpath("//*[@class='job-offer-footer']//@value")[0]

        url = await self.bot.get_content(base_url + "jobMarket.html", data={"id": job_id, "submit": "Apply"})
        if "APPLY_FOR_JOB_ALREADY_HAVE_JOB" in url:
            await self.bot.get_content(base_url + "work.html", data={'action': "leave", "submit": "Leave job"})
            url = await self.bot.get_content(base_url + "jobMarket.html", data={"id": job_id, "submit": "Apply"})
            if "APPLY_FOR_JOB_ALREADY_HAVE_JOB" in url:
                return await ctx.send(f"**{nick}** ERROR: Couldn't apply for a new job. Perhaps you should wait 6 hours.")
        await ctx.send(f"**{nick}** <{url}>")
        await ctx.invoke(self.bot.get_command("work"), nick=nick)

    @command(aliases=["split"])
    async def merge(self, ctx, ids_or_quality: str, *, nick: IsMyNick):
        """
        Merges a specific EQ IDs / all EQs up to specific Q (included) / elixirs.

        Examples:
        .merge 36191,34271,33877 My Nick  ->   Merges eqs id 36191, 34271 and 33877
        .merge 5 My Nick                  ->   Merges all Q1-Q5 eqs in your storage.
        .split 36191 My Nick              ->   Splits eq id 36191
        .merge mini_lucky My Nick         ->   Merges 3 mini elixirs into lucky
        .merge mini_bloody My Nick        ->   Merges 3 mili bloody mess elixirs into mini

        * You can also use blue/green/red/yellow instead of Jinxed/Finesse/bloody_mess/lucky
        * You can also use Q1-6 instead of mili/mini/standard/major/huge/exceptional

        IMPORTANT NOTE: No spaces in `ids_or_quality`! only commas (or within quotes)
        """

        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        if ctx.invoked_with.lower() == "split":
            payload = {'action': "SPLIT", "itemId": int(ids_or_quality.strip())}
            url = await self.bot.get_content(base_url + "equipmentAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")
            await ctx.invoke(self.bot.get_command("eqs"), nick=nick)
        elif "," in ids_or_quality:
            eq1, eq2, eq3 = [eq.strip() for eq in ids_or_quality.split(",")]
            payload = {'action': "MERGE", f'itemId[{eq1}]': eq1, f'itemId[{eq2}]': eq2, f'itemId[{eq3}]': eq3}
            url = await self.bot.get_content(base_url + "equipmentAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")
            await ctx.invoke(self.bot.get_command("eqs"), nick=nick)

        elif ids_or_quality.isdigit():
            await ctx.send(f"**{nick}** On it! You can cancel with `.cancel merge {nick}`")
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
                        if utils.should_break(ctx):
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

        else:
            elixir_type = utils.fix_elixir(ids_or_quality)
            if "LUCKY" in elixir_type:
                payload = {"luckyElixirType": elixir_type, "action": "MERGE_THREE_ELIXIRS_INTO_LUCKY_ONE", "submit": "Merge"}
            else:
                payload = {"elixirType": elixir_type, "action": "MERGE_ELIXIRS_INTO_BIGGER", "submit": "Merge"}
            url = await self.bot.get_content(base_url + "elixirAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def mm(self, ctx, *, nick: IsMyNick):
        """Sells all currencies in your account in the appropriate markets & edit current offers if needed."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        api = await self.bot.get_content(base_url + "apiCountries.html")
        money_tree = await self.bot.get_content(base_url + "storage.html?storageType=MONEY", return_tree=True)
        money = [x.strip() for x in money_tree.xpath("//*[@class='currencyDiv']//text()") if x.strip()]
        coins = dict(zip(money[1::2], money[0::2]))
        if "Gold" in coins:
            del coins["Gold"]
        for currency, amount in coins.items():
            if utils.should_break(ctx):
                return
            currency_id = [i["id"] for i in api if i["currencyName"] == currency][0]
            tree = await self.bot.get_content(f'{base_url}monetaryMarket.html?buyerCurrencyId={currency_id}&sellerCurrencyId=0', return_tree=True)
            try:
                rate = float(tree.xpath("//*[@class='buy']/button")[0].attrib['data-sell-currency'])
            except Exception:
                rate = 0.1
            payload = {"offeredCurrencyId": currency_id, "buyerCurrencyId": 0, "amount": amount,
                       "rate": round(rate - 0.0001, 4)}
            await self.bot.get_content(base_url + "monetaryMarketOfferPost.html", data=payload)
            await ctx.send(f"**{nick}** posted {amount} {currency} for {payload['rate']}")

        money_tree = await self.bot.get_content(base_url + "storage.html?storageType=MONEY", return_tree=True)
        ids = money_tree.xpath('//*[@id="command"]//input[1]')
        currencies = [x.strip() for x in money_tree.xpath(f"//*[@class='amount']//text()") if x.strip()][1::2]
        for i in range(len(currencies)):
            if utils.should_break(ctx):
                return
            currency_id = [x["id"] for x in api if x["currencyName"] == currencies[i]][0]
            tree = await self.bot.get_content(f'{base_url}monetaryMarketOffers?buyerCurrencyId={currency_id}&sellerCurrencyId=0&page=1', return_tree=True)
            seller = tree.xpath("//*[@class='seller']/a/text()")[0].strip()
            rate = float(tree.xpath("//*[@class='buy']/button")[0].attrib['data-sell-currency'])
            if seller.lower() != nick.lower():
                payload = {"id": ids[i].value, "rate": round(rate - 0.0001, 4), "submit": "Edit"}
                await self.bot.get_content(base_url + "monetaryMarket.html?action=change", data=payload)
                await ctx.send(f"**{nick}** edited {currencies[i]} for {payload['rate']}")

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
            if utils.should_break(ctx):
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
    async def work(self, ctx, *, nick: IsMyNick):
        """`work+` -> for premium users (https://primera.e-sim.org/taskQueue.html)"""

        server = ctx.channel.name
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
                    region = tree.xpath("//*[@class='companyStats']//a/@href")[-1].split("=")[-1]
                except IndexError:
                    try:
                        region = utils.get_ids_from_path(
                            tree, '//div[1]//div[2]//div[5]//div[1]//div//div[1]//div//div[4]//a')[0]
                    except IndexError:
                        return await ctx.send(f"**{nick}** ERROR: I couldn't find in which region your work is. If you don't have a job, see `.help job`")
                if await ctx.invoke(self.bot.get_command("fly"), region, 5, nick=nick):
                    await self.bot.get_content(base_url + "work/ajax", data={"action": "work"})
            tree = await self.bot.get_content(base_url + "work.html", return_tree=True)
            if not tree.xpath('//*[@id="taskButtonWork"]//@href'):
                data = await utils.find_one(server, "info", nick)
                data["Worked at"] = datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%d/%m  %H:%M")
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
        await sleep(uniform(1, 3))
        await ctx.invoke(self.bot.get_command("read"), nick=nick)

    @command()
    async def auto_fly(self, ctx, ticket_quality: int, country: Optional[Country] = 26, total_days: Optional[int] = 1, *, nick: IsMyNick):
        """Fly at random times throughout every day (for drops)
        Currently, max drops per 24h = 6. 80% of them are Q1 shoes/pants, 16 Q2 and 4% Q3.
        There's 2% chance to get a drop when you use Q5 ticket, and 3% if you use Q1."""

        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        regions = [row['id'] for row in await self.bot.get_content(base_url + "apiRegions.html") if row['homeCountry'] == country]
        max_flights_per_day = 300
        flights_per_restore = (10 // (5 - ticket_quality)) if ticket_quality != 5 else 10
        for day in range(total_days):
            found = 0
            last_region = 0
            flights = 0
            output = f"**{nick}** "
            for i in range(max_flights_per_day // flights_per_restore):
                for j in range(flights_per_restore):
                    region = last_region
                    while region == last_region:
                        region = choice(regions)
                    last_region = region
                    payload = {'countryId': country, 'regionId': region, 'ticketQuality': ticket_quality}
                    tree = await self.bot.get_content(f"https://{ctx.channel.name}.e-sim.org/travel.html", data=payload, return_tree=True)
                    flights += 1
                    if tree.xpath("//*[@class='travelEquipmentDrop']"):
                        output += f"found drop after {(i+1)*(j+1)} flights\n"
                        found += 1
                    await sleep(uniform(3, 7))
                    if found == 6 or utils.should_break(ctx):
                        break
                if found == 6 or utils.should_break(ctx):
                    break
                await utils.random_sleep()

            await ctx.send(output + f"Found total {found} drops for today. Total flights: {flights}")
            if utils.should_break(ctx):
                break
            await sleep(uniform(24, 30)*60*60)

    @command()
    async def auto_work(self, ctx, work_sessions: Optional[int] = 1, chance_to_skip_work: Optional[int] = 3, *, nick: IsMyNick):
        """Works at random times throughout every day"""
        data = {"work_sessions": work_sessions, "chance_to_skip_work": chance_to_skip_work}
        await utils.save_command(ctx, "auto", "work", data)
        await ctx.send(f"**{nick}** I will work from now on {work_sessions} times every day, with {chance_to_skip_work}% chance to skip a work.\n"
                       f"If you wish to stop it, type `.cancel auto_work {nick}`")

        tz = timezone('Europe/Berlin')
        while not utils.should_break(ctx):  # for every day:
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
                if utils.should_break(ctx):
                    break
                if randint(1, 100) > chance_to_skip_work:
                    await ctx.invoke(self.bot.get_command("work"), nick=nick)
                if (midnight - now).seconds < sec_between_works:
                    break

            # Updated the data once a day (allow the user to change chance_to_skip_work or work_sessions)
            data = (await utils.find_one("auto", "work", os.environ['nick']))[ctx.channel.name]
            if isinstance(data, list):
                data = data[0]
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
        await get_staff_list(self.bot, base_url, blacklist)
        await get_received_contracts(self.bot, base_url, blacklist, contract_name)
        await get_rejected_contracts(self.bot, base_url, blacklist)
        async for friend in get_friends_list(self.bot, nick, server):
            if utils.should_break(ctx):
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


async def get_rejected_contracts(bot, base_url: str, blacklist: set, alerts_filter: str = "CONTRACTS", text: str = "has rejected your") -> None:
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


async def get_friends_list(bot, nick: str, server: str, skip_banned_and_inactive: bool = True) -> iter:
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


async def get_staff_list(bot, base_url: str, blacklist: set) -> None:
    """Get staff list"""
    tree = await bot.get_content(f"{base_url}staff.html", return_tree=True)
    nicks = tree.xpath('//*[@id="esim-layout"]//a/text()')
    for nick in nicks:
        blacklist.add(nick.strip())


async def get_received_contracts(bot, base_url: str, blacklist: set, contract_name: str) -> None:
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


def setup(bot):
    """setup"""
    bot.add_cog(Eco(bot))
