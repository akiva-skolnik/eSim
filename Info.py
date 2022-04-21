from asyncio import sleep
from datetime import date, datetime, timedelta
from random import randint

from discord import Embed
from discord.ext.commands import Cog, check, command
from lxml.html import fromstring
from pytz import timezone

import utils
from Converters import IsMyNick


class Info(Cog):
    """Info Commands"""

    def __init__(self, bot):
        self.bot = bot

    @command(hidden=True)
    async def ping(self, ctx, *, nicks):
        """Shows who is connected to host"""
        server = ctx.channel.name
        for nick in [x.strip() for x in nicks.split(",") if x.strip()]:
            if nick.lower() == "all":
                nick = utils.my_nick(server)
                await sleep(randint(1, 3))

            if nick.lower() == utils.my_nick(server).lower():
                await ctx.send(f'**{utils.my_nick(server)}** Code Version: {self.bot.VERSION}')

    @command()
    async def eqs(self, ctx, *, nick: IsMyNick):
        """Shows the list of EQs in storage."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(URL + 'storage.html?storageType=EQUIPMENT', return_tree=True)
        items = tree.xpath(f'//*[starts-with(@id, "cell")]/b/text()')
        original_ids = [ID.replace('#', '') for ID in tree.xpath(f'//*[starts-with(@id, "cell")]/a/text()')]
        parameters = [[utils.get_parameter(p) for p in tree.xpath(f'//*[@id="cell{ID}"]/text()')[3:]] for ID in original_ids]
        ids = [f"[{ID}]({URL}showEquipment.html?id={ID})" for ID in original_ids]
        if sum([len(x) for x in ids]) > 1000:
            ids = [ID for ID in original_ids]
            # Eq id instead of link
        embed = Embed(title=nick)
        embed.add_field(name="ID", value="\n".join(ids[:50]))
        embed.add_field(name="Item", value="\n".join(items[:50]))
        embed.add_field(name="Parameters", value="\n".join(", ".join(f"{par_val[1]} {par_val[0]}" for par_val in eq) for eq in parameters[:50]))
        if len(ids) > 50:
            embed.set_footer(text="(first 50 items)")
        await ctx.send(embed=embed)

    @command(aliases=["inventory"])
    async def inv(self, ctx, *, nick: IsMyNick):
        """Shows all of your in-game inventory."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        storage_tree = await self.bot.get_content(f"{URL}storage.html?storageType=PRODUCT", return_tree=True)
        special_tree = await self.bot.get_content(f"{URL}storage.html?storageType=SPECIAL_ITEM", return_tree=True)
        special = {}
        products = {}
        for item in special_tree.xpath('//div[@class="specialItemInventory"]'):
            if item.xpath('span/text()'):
                special[item.xpath('b/text()')[0]] = item.xpath('span/text()')[0]

        for item in storage_tree.xpath("//div[@class='storage']"):
            name = item.xpath("div[2]/img/@src")[0].replace("//cdn.e-sim.org//img/productIcons/", "").replace(
                "Rewards/", "").replace(".png", "")
            if name.lower() in ["iron", "grain", "diamonds", "oil", "stone", "wood"]:
                quality = ""
            else:
                quality = item.xpath("div[2]/img/@src")[1].replace(
                    "//cdn.e-sim.org//img/productIcons/", "").replace(".png", "")
            products[f"{quality.title()} {name}"] = item.xpath("div[1]/text()")[0].strip()

        embed = Embed(title=nick, description=storage_tree.xpath('//div[@class="sidebar-money"][1]/b/text()')[0] + " Gold")
        if products:
            embed.add_field(name="**Storage:**", value="\n".join(f"**{k}**: {v}" for k, v in products.items()))
        if special:
            embed.add_field(name="**Special Items:**", value="\n".join(f"**{k}**: {v}" for k, v in special.items()))
        await ctx.send(embed=embed)

    @command()
    async def muinv(self, ctx, *, nick: IsMyNick):
        """Shows all of your in-game Military Unit inventory."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(f"{URL}militaryUnitStorage.html", return_tree=True)
        products = dict()
        for item in tree.xpath("//div[@class='storage']"):
            name = item.xpath("div[2]/img/@src")[0].replace("//cdn.e-sim.org//img/productIcons/", "").replace(
                "Rewards/", "").replace(".png", "")
            if name.lower() in ("iron", "grain", "diamonds", "oil", "stone", "wood"):
                quality = ""
            else:
                quality = item.xpath("div[2]/img/@src")[1].replace("//cdn.e-sim.org//img/productIcons/",
                                                                   "").replace(".png", "")
            products[f"{quality.title()} {name}"] = int(item.xpath("div[1]/text()")[0].strip())

        coins_len = max(5, len(products))
        tree = await self.bot.get_content(f"{URL}militaryUnitMoneyAccount.html", return_tree=True)
        amounts = tree.xpath('//*[@id="esim-layout"]//div[4]//div//b/text()')[:coins_len]
        coins = tree.xpath('//*[@id="esim-layout"]//div[4]/div/text()')[2::3][:coins_len]

        embed = Embed(title=nick)
        if products:
            embed.add_field(name="**Products:**",
                            value="\n".join(f"**{product}**: {amount:,}" for product, amount in products.items()))
        if coins:
            embed.add_field(name=f"**Coins (first {coins_len}):**",
                            value="\n".join(f"**{coin.strip()}**: {round(float(amount), 2):,}" for coin, amount in zip(coins, amounts)))
        embed.set_footer(text="Military Unit Inventory")
        await ctx.send(embed=embed)

    @command()
    async def limits(self, ctx, *, nick: IsMyNick):
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(URL, return_tree=True)
        try:
            gold = tree.xpath('//*[@id="userMenu"]//div//div[4]//div[1]/b/text()')[0]
        except IndexError:
            return await ctx.send(f"**{nick}** you are not logged in! Please type `.login {nick}` and try again")
        food_storage = tree.xpath('//*[@id="foodQ5"]/text()')[0]
        gift_storage = tree.xpath('//*[@id="giftQ5"]/text()')[0]
        food_limit = tree.xpath('//*[@id="foodLimit2"]')[0].text
        gift_limit = tree.xpath('//*[@id="giftLimit2"]')[0].text
        await ctx.send(
            f"**{nick}** Limits: {food_limit}/{gift_limit}, storage: {food_storage}/{gift_storage}, {gold} Gold.")

    @command()
    @check(utils.is_helper)
    async def regions(self, ctx, country):
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        api_regions = await self.bot.get_content(URL + "apiRegions.html")
        api_countries = await self.bot.get_content(URL + "apiCountries.html")
        country_id = next(x['id'] for x in api_countries if x["name"].lower() == country.lower())
        regions = [region for region in api_regions if region["homeCountry"] == country_id]
        embed = Embed(title=f"Core Regions {country}")
        embed.add_field(name="Region", value="\n".join(f"[{region['name']}]({URL}region.html?id={region['id']})" +
                                                       (" (capital)" if region["capital"] else "") for region in regions))
        embed.add_field(name="Resource", value="\n".join(f"{region['rawRichness'].title()} {region.get('resource', '').title()}" for region in regions))
        embed.add_field(name="Neighbours Ids", value="\n".join(", ".join(str(x) for x in region['neighbours']) for region in regions))
        await ctx.send(embed=embed)

    @command()
    @check(utils.is_helper)
    async def country(self, ctx, country):
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        api_countries = await self.bot.get_content(URL + "apiCountries.html")
        country = next(x for x in api_countries if x["name"].lower() == country.lower())
        embed = Embed(title=country["name"])
        embed.add_field(name="Id", value=country["id"])
        embed.add_field(name="Capital", value=f'[{country["capitalName"]}]({URL}region.html?id={country["capitalRegionId"]})')
        embed.add_field(name="Currency", value=country["currencyName"])
        embed.add_field(name="Short Name", value=country["shortName"])
        if "president" in country:
            president = await self.bot.get_content(f'{URL}apiCitizenById.html?id={country["president"]}')
            embed.add_field(name="President", value=f"[{president['login']}]({URL}profile.html?id={country['president']})")
        else:
            embed.add_field(name="President", value="-")
        await ctx.send(embed=embed)

    @command()
    @check(utils.is_helper)
    async def auctions(self, ctx):
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(URL + "auctions.html", return_tree=True)
        col1 = list()
        col2 = list()
        col3 = list()
        for tr in range(2, 13):
            try:
                seller = tree.xpath(f'//tr[{tr}]//td[1]/a/text()')[0].strip()
            except IndexError:  # No more auctions
                break
            buyer = (tree.xpath(f'//tr[{tr}]//td[2]/a/text()') or ["None"])[0].strip()
            item = tree.xpath(f'//tr[{tr}]//td[3]/b/text()')
            parameters = tree.xpath(f'//tr[{tr}]//td[3]/text()')
            if not item:
                parameters = parameters[1]
            else:
                item = item[0].lower().replace("personal", "").replace("charm", "").replace("weapon upgrade", "WU").title()
                parameters = f"**{item}:** " + ", ".join(f"{par_val[1]} {par_val[0]}" for par_val in (utils.get_parameter(p) for p in parameters[5:]))

            price = tree.xpath(f'//tr[{tr}]//td[4]/b/text()')[0]
            link = tree.xpath(f'//tr[{tr}]//td[5]/a/@href')[0]
            time = tree.xpath(f'//tr[{tr}]//td[6]/span/text()')[0]
            col1.append(f"{seller} : {buyer}"[:30])
            col2.append(parameters[:30])
            col3.append(f"{float(price):,}g : [{time}]({URL + link})")
        embed = Embed(title="First 10 auctions")
        embed.add_field(name="Seller : Buyer", value="\n".join(col1))
        embed.add_field(name="Item", value="\n".join(col2))
        embed.add_field(name="Gold : Time Reminding", value="\n".join(col3))
        await ctx.send(embed=embed)

    @command(name="info-", hidden=True)
    @check(utils.is_helper)
    async def info_(self, ctx):
        values = await utils.find(ctx.channel.name, "info")
        if values:
            values.sort(key=lambda x: x['Buffed at'])
            embed = Embed()
            embed.add_field(name="Nick", value="\n".join([row["_id"] for row in values]))
            embed.add_field(name="Worked At", value="\n".join([row.get("Worked at", "-") for row in values]))
            embed.add_field(name="Buffed At", value="\n".join([row.get("Buffed at", "-") for row in values]))
            embed.set_footer(text="Type .info <nick> for more info on a nick")
            await ctx.send(embed=embed)
        else:
            await ctx.send("No data available")

    @command()
    async def info(self, ctx, *, nick: IsMyNick):
        """Shows some info about a given user.
        .info- will give you a brief info about all users connected to MongoDB
        (if you did not set it via config.json, the info is only about you)"""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        tree = await self.bot.get_content(URL + "storage.html?storageType=PRODUCT", return_tree=True)
        medkits = (tree.xpath('//*[@id="medkitButton"]/text()') or "0")[0].replace("Use medkit", "").replace("(you have", "").replace(")", "").strip()

        gold = tree.xpath('//*[@id="userMenu"]//div//div[4]//div[1]/b/text()')[0]
        storage1 = {}
        for num in range(2, 22):
            try:
                item = str(tree.xpath(f'//*[@id="resourceInput"]/option[{num}]')[0].text).strip().replace(
                    "(available", "").replace(")", "").split(":")
                while "  " in item[0]:
                    item[0] = item[0].replace("  ", "")
                storage1[item[0]] = int(item[1])
            except:
                break

        tree = await self.bot.get_content(URL + 'storage.html?storageType=SPECIAL_ITEM', return_tree=True)
        storage = []
        for num in range(1, 16):
            try:
                amount = tree.xpath(f'//*[@id="storageConteiner"]//div//div//div[1]//div[{num}]/span')[0].text
                if "x" in amount:
                    item = str(
                        tree.xpath(f'//*[@id="storageConteiner"]//div//div//div[1]//div[{num}]/b')[0].text).replace(
                        "Extra", "").replace("Equipment parameter ", "")
                if item != "Medkit" and "Bandage" not in item:
                    storage.append(f'{amount.replace("x", "")} {item}')
            except:
                break

        api = await self.bot.get_content(URL + 'apiCitizenByName.html?name=' + nick.lower())
        data = await utils.find_one(server, "info", nick)
        date_format = "%Y-%m-%d %H:%M:%S"

        now = datetime.now().astimezone(timezone('Europe/Berlin')).strftime(date_format)

        if "Buffed at" not in data:
            data["Buffed at"] = "-"
        else:
            days = 2 if api["premiumDays"] else 3
            buffed_seconds = (
                    datetime.strptime(now, date_format) - datetime.strptime(data["Buffed at"], date_format)).total_seconds()
            day_seconds = 24 * 60 * 60
            debuff_ends = (timedelta(days=days) + datetime.strptime(data["Buffed at"], date_format)).strftime(date_format)
            if buffed_seconds < day_seconds:  # buff lasts 24h
                seconds = day_seconds - buffed_seconds
            elif buffed_seconds < day_seconds * days:  # debuff ends
                seconds = (datetime.strptime(debuff_ends, date_format) - datetime.strptime(now,
                                                                                           date_format)).total_seconds()
            else:
                seconds = 0
            data["Buffed at"] += f" ({timedelta(seconds=seconds)}h left)"

        link = f"{URL}profile.html?id={api['id']}"
        tree = await self.bot.get_content(link, return_tree=True)

        embed = Embed(colour=0x3D85C6, url=link)
        embed.title = ("\U0001f7e2" if tree.xpath('//*[@id="loginBar"]/span[2]/@class')[0] == "online" else "\U0001f534") + \
                      f" {api['login']}, {api['citizenship']} (id {api['citizenshipId']})"

        buffs_debuffs = [x.split("/specialItems/")[-1].split(".png")[0] for x in
                         tree.xpath(f'//*[@class="profile-row" and (strong="Debuffs" or strong="Buffs")]//img/@src') if
                         "//cdn.e-sim.org//img/specialItems/" in x]
        buffs = ', '.join([x.split("_")[0].lower().replace("vacations", "vac").replace("resistance", "sewer").replace(
            "paindealer", "PD ").replace("bonusdamage", "") + ("% Bonus" if "bonusdamage" in x else "") for x in
                           buffs_debuffs if "positive" in x.split("_")[1:]]).title()
        debuffs = ', '.join([x.split("_")[0].lower().replace("vacations", "vac").replace(
            "resistance", "sewer") for x in buffs_debuffs if "negative" in x.split("_")[1:]]).title()

        stats = {"Buffs": buffs or "-", "Debuffs": debuffs or "-",
                 "Total DMG": f"{api['totalDamage'] - api['damageToday']:,}",
                 "Today's DMG": f"{api['damageToday']:,}", "XP": f"{api['xp']:,}",
                 "Premium": f"till {date.today() + timedelta(days=int(api['premiumDays']))} ({api['premiumDays']} days)" if
                            api['premiumDays'] else "", "Economy skill": round(api['economySkill'], 1),
                 "Birthday": (tree.xpath(f'//*[@class="profile-row" and span = "Birthday"]/span/text()') or [1])[0],
                 "Medals": f"{api['medalsCount']:,}", "Friends": f"{api['friendsCount']:,}", "Medkits": medkits, "Gold": gold}
        data.update(stats)

        eqs = []
        for slot_path in tree.xpath('//*[@id="profileEquipmentNew"]//div//div//div//@title'):
            tree = fromstring(slot_path)
            try:
                Type = tree.xpath('//b/text()')[0].lower().replace("personal", "").replace("charm", "").replace(
                    "weapon upgrade", "WU").replace("  ", " ").title().strip()
            except IndexError:
                continue
            eq_link = tree.xpath("//a/@href")[0]
            parameters = []
            values = []
            for parameter_string in tree.xpath('//p/text()'):
                parameter, value = utils.get_parameter(parameter_string)
                parameters.append(parameter)
                values.append(value)
            eqs.append(f"**[{Type}]({URL+eq_link}):** " + ", ".join(f"{val} {p}" for val, p in zip(values, parameters)))

        if api['militaryUnitId']:
            mu = await self.bot.get_content(f"{URL}apiMilitaryUnitById.html?id={api['militaryUnitId']}")
            data["MU"] = f"[{mu['name']}]({URL}militaryUnit.html?id={api['militaryUnitId']})"
        else:
            data["MU"] = "No MU"

        api_regions = await self.bot.get_content(URL + "apiRegions.html")
        api_countries = await self.bot.get_content(URL + "apiCountries.html")

        region, country = utils.get_region_and_country_names(api_regions, api_countries, api['currentLocationRegionId'])
        data["Location"] = f"[{region}, {country}]({URL}region.html?id={api['currentLocationRegionId']})"
        parameters = {"Crit": api['eqCriticalHit'],
                      "Avoid": api['eqAvoidDamage'],
                      "Miss": api['eqReduceMiss'],
                      "Dmg": api['eqIncreaseDamage'],
                      "Max": api['eqIncreaseMaxDamage'],
                      "Inc. Eco Skill": api['eqIncreaseEcoSkill'],
                      "Less Weapons": api['eqLessWeapons'],
                      "Find Weapon": api['eqFindAWeapon'],
                      "Inc. Strength": api['eqIncreaseStrength'],
                      "Increase Hit": api['eqIncreaseHit'],
                      "Free Flight": api['eqFreeFlight']}

        embed.add_field(name="__Stats__", value="\n".join([f"**{k}**: {v}" for k, v in data.items()]))
        embed.add_field(name="__Parameters__", value="\n".join([f"**{k}**: {v}" for k, v in parameters.items()]))
        embed.add_field(name="__Slots__", value="\n".join(eqs) or "- no eqs found -")

        if 'companyId' in api:
            comp_link = f"{URL}company.html?id={api['companyId']}"
            tree = await self.bot.get_content(comp_link, return_tree=True)
            company_type = tree.xpath("//div[1]/div/div[1]/div/div[3]/b/span/@title")[0]
            company_quality = tree.xpath("//div[1]/div/div[1]/div/div[3]/b/text()[2]")[0].strip()
            company_name = tree.xpath('//a[@style="font-weight: bold;clear:both;"]/text()')[0]
            region_id = [a.split("=")[1] for a in tree.xpath("//div[1]/div/div[1]/div/div[4]/b/a/@href")][0]
            region, country = utils.get_region_and_country_names(api_regions, api_countries, int(region_id))
            embed.add_field(name=f"Works in a {company_quality} {company_type} company",
                            value=f"[{company_name}]({comp_link}) ([{region}]({URL}region.html?id={region_id}), {country})")
        embed.add_field(name="__Storage__", value="\n".join([f'{v:,} {k}' for k, v in storage1.items()]) or "-")
        embed.add_field(name="__Special Items__", value="\n".join(storage) or "-")
        embed.set_footer(text="Code Version: " + self.bot.VERSION)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Info(bot))
