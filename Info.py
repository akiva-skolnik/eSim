from asyncio import sleep
from datetime import date, datetime, timedelta
from os import environ
from random import randint

from discord import Embed
from discord.ext.commands import Cog, command
from lxml.html import fromstring
from pytz import timezone

from Converters import IsMyNick
import utils


class Info(Cog):
    """Info Commands"""

    def __init__(self, bot):
        self.bot = bot

    @command(hidden=True)
    async def ping(self, ctx, *, nicks):
        """Shows who is connected to host"""
        for nick in [x.strip() for x in nicks.split(",") if x.strip()]:
            if nick.lower() == "all":
                nick = environ.get(ctx.channel.name, environ["nick"])
                await sleep(randint(1, 3))

            if nick.lower() == environ.get(ctx.channel.name, environ["nick"]).lower():
                await ctx.send(f'**{environ.get(ctx.channel.name, environ["nick"])}** - online')

    @command()
    async def eqs(self, ctx, *, nick: IsMyNick):
        """Shows list of EQs in storage."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(URL + 'storage.html?storageType=EQUIPMENT', return_tree=True)
        original_IDs = tree.xpath(f'//*[starts-with(@id, "cell")]/a/text()')
        IDs = [f"[{ID}]({URL}showEquipment.html?id={ID.replace('#', '')})" for ID in original_IDs]
        if sum([len(x) for x in IDs]) > 1000:
            IDs = [ID for ID in original_IDs]
            # Eq id instead of link
        items = tree.xpath(f'//*[starts-with(@id, "cell")]/b/text()')
        embed = Embed(title=nick)
        embed.add_field(name="ID", value="\n".join(IDs), inline=True)
        embed.add_field(name="Item", value="\n".join(items), inline=True)
        await ctx.send(embed=embed)

    @command(aliases=["inventory"])
    async def inv(self, ctx, *, nick: IsMyNick):
        """Shows all of your in-game inventory."""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(f"{URL}storage.html?storageType=PRODUCT", return_tree=True)
        tree2 = await self.bot.get_content(f"{URL}storage.html?storageType=SPECIAL_ITEM", return_tree=True)
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
        products = ["Gold"]
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

        embed = Embed(title=nick)
        for i in range(len(products) // 5 + 1):
            value = [f"**{a}**: {b}" for a, b in zip(products[i * 5:(i + 1) * 5], quantity[i * 5:(i + 1) * 5])]
            embed.add_field(name="**Products: **" if not i else u"\u200B",
                            value="\n".join(value) if value else u"\u200B")
        embed.set_footer(text="Inventory")
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
            products[f"{quality.title()} {name}" if quality else f"{name}"] = int(
                item.xpath("div[1]/text()")[0].strip())

        tree = await self.bot.get_content(f"{URL}militaryUnitMoneyAccount.html", return_tree=True)
        amounts = tree.xpath('//*[@id="esim-layout"]//div[4]//div//b/text()')[:len(products)]
        coins = tree.xpath('//*[@id="esim-layout"]//div[4]/div/text()')[2::3][:len(products)]

        embed = Embed(title=nick)
        embed.add_field(name="**Products:**",
                        value="\n".join(f"**{product}**: {amount:,}" for product, amount in products.items()))
        embed.add_field(name=f"**Coins (first {len(products)}):**",
                        value="\n".join(
                            f"**{coin.strip()}**: {float(amount):,}" for coin, amount in zip(coins, amounts)))
        embed.set_footer(text="Military Unit Inventory")
        await ctx.send(embed=embed)

    @command()
    async def limits(self, ctx, *, nick: IsMyNick):
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(URL, return_tree=True)
        gold = tree.xpath('//*[@id="userMenu"]//div//div[4]//div[1]/b/text()')[0]
        food_storage = tree.xpath('//*[@id="foodQ5"]/text()')[0]
        gift_storage = tree.xpath('//*[@id="giftQ5"]/text()')[0]
        food_limit = tree.xpath('//*[@id="foodLimit2"]')[0].text
        gift_limit = tree.xpath('//*[@id="giftLimit2"]')[0].text
        await ctx.send(
            f"**{nick}** Limits: {food_limit}/{gift_limit}, storage: {food_storage}/{gift_storage}, {gold} Gold.")

    @command(aliases=["info-", "info+"])
    async def info(self, ctx, *, nick: IsMyNick):
        """Shows some info about a given user"""
        if ctx.invoked_with.lower() == "info-":
            values = await utils.find(ctx.channel.name, "info")
            values.sort(key=lambda x: x['Buffed at'])
            embed = Embed()
            embed.add_field(name="Nick: GOld",
                            value="\n".join([f'{row["_id"]}: {row.get("Gold", "Unknown")}' for row in values]))
            embed.add_field(name="Worked At", value="\n".join([row.get("Worked at", "-") for row in values]))
            embed.add_field(name="Buffed At", value="\n".join([row.get("Buffed at", "-") for row in values]))
            embed.set_footer(text="Type .info <nick> for more info on a nick")
            return await ctx.send(embed=embed)

        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        tree = await self.bot.get_content(URL + "storage.html?storageType=PRODUCT", return_tree=True)
        medkits = str(tree.xpath('//*[@id="medkitButton"]')[0].text).replace("Use medkit", "").replace("(you have", "").replace(")", "").strip() or "0"

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
        if not storage:
            storage = ["Empty"]

        api = await self.bot.get_content(URL + 'apiCitizenByName.html?name=' + nick.lower())
        data = await utils.find_one(server, "info", nick)
        date_format = "%Y-%m-%d %H:%M:%S"

        now = datetime.now().astimezone(timezone('Europe/Berlin')).strftime(date_format)

        if "Buffed at" not in data:
            data["Buffed at"] = "-"
        else:
            days = 2 if api["premium"] else 3
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

        all_parameters = {"avoid": "Chance to avoid damage",
                          "max": "Increased maximum damage",
                          "crit": "Increased critical hit chance",
                          "damage": "Increased damage", "dmg": "Increased damage",
                          "miss": "Miss chance reduction",
                          "flight": "Chance for free flight",
                          "consume": "Save ammunition",
                          "eco": "Increased economy skill",
                          "str": "Increased strength",
                          "hit": "Increased hit",
                          "less": "Less weapons for Berserk",
                          "find": "Find a weapon",
                          "split": "Improved split",
                          "production": "Bonus * production",
                          "merging": "Merge bonus",
                          "merge": "Reduced equipment merge price",
                          "restore": "Restoration",
                          "increase": "Increase other parameters"}
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
                for x in all_parameters:
                    if x in parameter_string.lower():
                        parameters.append(x)
                        try:
                            values.append(float(parameter_string.split(" ")[-1].replace("%", "").strip()))
                            break
                        except:
                            pass
            eqs.append(f"**[{Type}]({URL+eq_link}):** " + ", ".join(f"{val} {p}" for val, p in zip(values, parameters)))

        mu = await self.bot.get_content(f"{URL}apiMilitaryUnitById.html?id={api['militaryUnitId']}")
        links = {f"MU: {mu['name']}": f"{URL}militaryUnit.html?id={api['militaryUnitId']}",
                 "Send Message": link.replace("profile", "composeMessage"),
                 "Friend Request": f"{URL}friends.html?action=PROPOSE&id={api['id']}",
                 "Donate Money": link.replace("profile", "donateMoney"),
                 "Donate Products": link.replace("profile", "donateProducts"),
                 "Donate EQ": link.replace("profile", "donateEquipment")}

        api_regions = await self.bot.get_content(URL + "apiRegions.html")
        api_countries = await self.bot.get_content(URL + "apiCountries.html")

        region, country = utils.get_region_and_country_names(api_regions, api_countries, api['currentLocationRegionId'])
        links[f"Location: {region}, {country}"] = f"{URL}region.html?id={api['currentLocationRegionId']}"
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
        embed.add_field(name="__Links__", value="\n".join([f"[{k}]({v})" for k, v in links.items() if v]))
        embed.add_field(name="__Storage__", value="\n".join([f'{v:,} {k}' for k, v in storage1.items()]))
        embed.add_field(name="__Special Items__", value=", ".join(storage) or "-")

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
        embed.set_footer(text="Code Version: " + self.bot.VERSION)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Info(bot))
