from asyncio import sleep
from base64 import b64encode
from datetime import datetime
from io import BytesIO
from os import environ
import json
from random import choice, randint

from aiohttp import ClientSession
from discord.ext.commands import Cog, command
from pytz import timezone

from Converters import Id, IsMyNick, Quality


class Mix(Cog):
    """Mix Commands"""

    def __init__(self, bot):
        self.bot = bot

    @command()
    async def candidate(self, ctx, *, nick: IsMyNick):
        """
        Candidate for congress / president elections.
        It will also auto join to the first party (by members) if necessary."""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        today = int(datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%d"))  # game time
        if 1 < today < 5:
            payload = {"action": "CANDIDATE", "presentation": "http://", "submit": "Candidate for president"}
            link = "presidentalElections.html"
        elif 20 < today < 24:
            payload = {"action": "CANDIDATE", "presentation": "http://", "submit": "Candidate for congress"}
            link = "congressElections.html"
        else:
            return await ctx.send(f"**{nick}** ERROR: I can't candidate today. Try another time.")

        try:
            tree = await self.bot.get_content(URL + "partyStatistics.html?statisticType=MEMBERS", return_tree=True)
            ID = str(tree.xpath('//*[@id="esim-layout"]//table//tr[2]//td[3]//@href')[0]).split("=")[1]
            party_payload = {"action": "JOIN", "id": ID, "submit": "Join"}
            url = await self.bot.get_content(URL + "partyStatistics.html", data=party_payload)
            if str(url) != URL + "?actionStatus=PARTY_JOIN_ALREADY_IN_PARTY":
                await ctx.send(f"**{nick}** <{url}>")

        except:
            pass

        url = await self.bot.get_content(URL + link, data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def avatar(self, ctx, *, nick):
        """
        Change avatar img.
        If you don't want the default img, write it like that:
        `.avatar https://picsum.photos/150, Your Nick` (with a comma)"""

        if "," in nick:
            imgURL, nick = nick.split(",")
        else:
            imgURL = "https://source.unsplash.com/random/150x150"
        await IsMyNick().convert(ctx, nick)
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        async with ClientSession() as session:
            async with session.get(imgURL.strip()) as resp:
                avatarBase64 = str(b64encode((BytesIO(await resp.read())).read()))[2:-1]

        payload = {"action": "CONTINUE", "v": f"data:image/png;base64,{avatarBase64}",
                   "h": "none", "e": "none", "b": "none", "a": "none", "c": "none", "z": 1, "r": 0,
                   "hh": 1, "eh": 1, "bh": 1, "ah": 1, "hv": 1, "ev": 1, "bv": 1, "av": 1, "act": ""}
        url = await self.bot.get_content(URL + "editAvatar.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def missions(self, ctx, nick: IsMyNick, action="ALL", missions_to_complete: int = 30):
        """Auto finish missions.
        * "action" must be one of: start / complete / skip / ALL"""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        if action.lower() != "all":
            if action.lower() == "start":
                c = await self.bot.get_content(URL + "betaMissions.html?action=START",
                                               data={"submit": "Start mission"})
                if "MISSION_START_OK" not in c and "?action=START" not in c:
                    return await ctx.send(f"**{nick}** <{c}>")
            elif action.lower() == "complete":
                c = await self.bot.get_content(URL + "betaMissions.html?action=COMPLETE",
                                               data={"submit": "Collect"})
                if "MISSION_REWARD_OK" not in c and "?action=COMPLETE" not in c:
                    return await ctx.send(f"**{nick}** <{c}>")
            elif action.lower() == "skip":
                c = await self.bot.get_content(URL + "betaMissions.html",
                                               data={"action": "SKIP", "submit": "Skip"})
                if "MISSION_SKIPPED" not in c:
                    return await ctx.send(f"**{nick}** <{c}>")
            else:
                return await ctx.send(f"**{nick}** ERROR: action must be `start`/`complete`/`skip`/`ALL`, not `{action}`")
            return await ctx.send(f"**{nick}** Done")
        prv_num = 0
        for _ in range(missions_to_complete):
            if self.bot.should_break(ctx):
                break
            try:
                tree = await self.bot.get_content(URL, return_tree=True)
                my_id = str(tree.xpath('//*[@id="userName"]/@href')[0]).split("=")[1]
                try:
                    num = int(str(tree.xpath('//*[@id="inProgressPanel"]/div[1]/div/strong')[0].text).split("#")[1])
                except:
                    if tree.xpath('//*[@id="missionDropdown"]//div[2]/text()'):
                        return await ctx.send(f"**{nick}** You have completed all your missions for today, come back tomorrow!")
                    c = await self.bot.get_content(URL + "betaMissions.html?action=COMPLETE", data={"submit": "Collect"})
                    await ctx.send(f"**{nick}** <{c}>")
                    continue
                if prv_num == num:
                    c = await self.bot.get_content(URL + "betaMissions.html",
                                                   data={"action": "SKIP", "submit": "Skip"})
                    if "MISSION_SKIPPED" not in c:
                        return
                    else:
                        await ctx.send(f"**{nick}** WARNING: Skipped mission {num}")
                        continue

                await ctx.send(f"**{nick}** Mission number {num}")
                c = await self.bot.get_content(URL + "betaMissions.html?action=START", data={"submit": "Start mission"})
                if "MISSION_START_OK" not in c:
                    c = await self.bot.get_content(URL + "betaMissions.html?action=COMPLETE", data={"submit": "Collect"})
                if "MISSION_REWARD_OK" not in c:
                    if num == 1:
                        await self.bot.get_content(URL + "inboxMessages.html")
                    elif num in (2, 4, 16, 27, 28, 36, 43, 59):
                        await ctx.invoke(self.bot.get_command("work"), nick=nick)
                    elif num in (3, 7):
                        await ctx.invoke(self.bot.get_command("auto_fight"), nick, 1)
                    elif num in (5, 26, 32, 35, 38, 40, 47, 51, 53, 64):
                        if num == 31:
                            restores = "3"
                            await ctx.send(f"**{nick}** Hitting {restores} restores, it might take a while")
                        elif num == 46:
                            restores = "2"
                            await ctx.send(f"**{nick}** Hitting {restores} restores, it might take a while")

                        await ctx.invoke(self.bot.get_command("auto_fight"), nick, 1)
                    elif num == 6:
                        for q in range(1, 6):
                            try:
                                await self.bot.get_content(f"{URL}food.html", data={'quality': q})
                            except:
                                pass
                    elif num == 8:
                        await self.bot.get_content(URL + "editCitizen.html")
                    elif num == 9:
                        await self.bot.get_content(URL + "notifications.html")
                    elif num == 10:
                        await self.bot.get_content(URL + "newMap.html")
                    elif num == 11:
                        tree = await self.bot.get_content(f"{URL}productMarket.html", return_tree=True)
                        productId = tree.xpath('//*[@id="command"]/input[1]')[0].value
                        payload = {'action': "buy", 'id': productId, 'quantity': 1, "submit": "Buy"}
                        await self.bot.get_content(URL + "productMarket.html", data=payload)
                    elif num in (12, 54):
                        Citizen = await self.bot.get_content(f'{URL}apiCitizenById.html?id={my_id}')
                        capital = [row['id'] for row in await self.bot.get_content(URL + "apiRegions.html") if row[
                            'homeCountry'] == Citizen['citizenshipId'] and row['capital']][0]
                        await ctx.invoke(self.bot.get_command("fly"), capital, 5, nick=nick)
                    elif num in (13, 66):
                        await self.bot.get_content(URL + 'friends.html?action=PROPOSE&id=8')
                        await self.bot.get_content(URL + "citizenAchievements.html",
                                                   data={"id": my_id, "submit": "Recalculate achievements"})
                    elif num == 14:
                        tree = await self.bot.get_content(URL + 'storage.html?storageType=EQUIPMENT', return_tree=True)
                        ID = tree.xpath(f'//*[starts-with(@id, "cell")]/a/text()')[0].replace("#", "")
                        payload = {'action': "EQUIP", 'itemId': ID.replace("#", "")}
                        await self.bot.get_content(URL + "equipmentAction.html", data=payload)
                    elif num == 15:
                        await self.bot.get_content(f"{URL}vote.html", data={"id": randint(1, 15)})
                    # day 2
                    elif num == 18:
                        shout_body = choice(["Mission: Say hello", "Hi", "Hello", "Hi guys :)", "Mission"])
                        payload = {'action': "POST_SHOUT", 'body': shout_body, 'sendToCountry': "on",
                                   "sendToMilitaryUnit": "on", "sendToParty": "on", "sendToFriends": "on"}
                        await self.bot.get_content(f"{URL}shoutActions.html", data=payload)
                    elif num == 19:
                        Citizen = await self.bot.get_content(f'{URL}apiCitizenById.html?id={my_id}')
                        tree = await self.bot.get_content(
                            URL + 'monetaryMarket.html?buyerCurrencyId=0&sellerCurrencyId=' + str(
                                int(Citizen['currentLocationRegionId'] / 6)))
                        ID = tree.xpath("//tr[2]//td[4]//form[1]//input[@value][2]")[0].value
                        payload = {'action': "buy", 'id': ID, 'ammount': 0.5, "submit": "OK"}
                        await self.bot.get_content(URL + "monetaryMarket.html", data=payload)
                    elif num == 21:
                        tree = await self.bot.get_content(URL + 'storage.html?storageType=EQUIPMENT')
                        ID = tree.xpath(f'//*[starts-with(@id, "cell")]/a/text()')[0].replace("#", "")
                        await ctx.invoke(self.bot.get_command("sell"), ID, 0.01, 48, nick=nick)
                    elif num == 22:
                        Citizen = await self.bot.get_content(f'{URL}apiCitizenById.html?id={my_id}')
                        payload = {'product': "GRAIN", 'countryId': Citizen['citizenshipId'], 'storageType': "PRODUCT",
                                   "action": "POST_OFFER", "price": 0.1, "quantity": 100}
                        sell_grain = await self.bot.get_content(URL + "storage.html", data=payload)
                        await ctx.send(f"**{nick}** <{sell_grain}>")
                    elif num == 25:
                        payload = {'setBg': "LIGHT_I", 'action': "CHANGE_BACKGROUND"}
                        await self.bot.get_content(URL + "editCitizen.html", data=payload)
                    # day 3
                    elif num == 29:
                        for article_id in range(2, 7):
                            await self.bot.get_content(f"{URL}vote.html", data={"id": article_id})
                    elif num == 30:
                        await self.bot.get_content(f"{URL}sub.html", data={"id": randint(1, 21)})
                    elif num == 31:
                        ctx.invoked_with = "mu"
                        await ctx.invoke(self.bot.get_command("citizenship"), randint(1, 21), nick=nick)
                    # day 4
                    elif num == 37:
                        shout_body = choice(["Mission: Get to know the community better", "Hi",
                                             "Hello", "Hi guys :)", "Mission", "IRC / Skype / TeamSpeak"])
                        payload = {'action': "POST_SHOUT", 'body': shout_body, 'sendToCountry': "on",
                                   "sendToMilitaryUnit": "on", "sendToParty": "on", "sendToFriends": "on"}
                        await self.bot.get_content(f"{URL}shoutActions.html", data=payload)
                    elif num == 39:
                        await self.bot.get_content(URL + 'friends.html?action=PROPOSE&id=1')
                    elif num == 41:
                        for _ in range(10):
                            ID = randint(1, 100)
                            payload = {"action": "NEW", "key": f"Article {ID}", "submit": "Publish",
                                       "body": choice(["Mission", "Hi", "Hello there", "hello", "Discord?"])}
                            comment = await self.bot.get_content(URL + "comment.html", data=payload)
                            if "MESSAGE_POST_OK" in comment:
                                break
                    elif num == 42:
                        try:
                            tree = await self.bot.get_content(URL + "partyStatistics.html?statisticType=MEMBERS", return_tree=True)
                            ID = str(tree.xpath('//*[@id="esim-layout"]//table//tr[2]//td[3]//@href')[0]).split("=")[1]
                            payload1 = {"action": "JOIN", "id": ID, "submit": "Join"}
                            b = await self.bot.get_content(URL + "partyStatistics.html", data=payload1)
                            await ctx.send(f"**{nick}** <{b}>")
                        except:
                            pass
                    # day 5
                    elif num == 45:
                        await self.bot.get_content(URL + f"replyToShout.html?id={randint(1, 21)}",
                                                   data={"body": choice(["OK", "Whatever", "Thanks", "Discord?"]),
                                                         "submit": "Shout!"})
                    elif num == 46:
                        payload = {'itemType': "STEROIDS", 'storageType': "SPECIAL_ITEM", 'action': "BUY",
                                   "quantity": 1}
                        await self.bot.get_content(URL + "storage.html", data=payload)
                    elif num == 49:
                        tree = await self.bot.get_content(URL + 'storage.html?storageType=EQUIPMENT', return_tree=True)
                        ID = tree.xpath(f'//*[starts-with(@id, "cell")]/a/text()')[0].replace("#", "")
                        payload = {'action': "EQUIP", 'itemId': ID.replace("#", "")}
                        await self.bot.get_content(URL + "equipmentAction.html", data=payload)
                    elif num == 50:
                        await self.bot.get_content(f"{URL}shoutVote.html", data={"id": randint(1, 20), "vote": 1})
                    elif num == 52:
                        await ctx.invoke(self.bot.get_command("fly"), 1, 3, nick=nick)
                    elif num in (61, 55):
                        await ctx.invoke(self.bot.get_command("motivate"), nick=nick)
                    elif num == 57:
                        Citizen = await self.bot.get_content(f'{URL}apiCitizenById.html?id={my_id}')
                        payload = {'receiverName': f"{Citizen['citizenship']} Org", "title": "Hi",
                                   "body": choice(["Hi", "Can you send me some gold?", "Hello there!", "Discord?"]),
                                   "action": "REPLY", "submit": "Send"}
                        await self.bot.get_content(URL + "composeMessage.html", data=payload)

                    elif num == 58:
                        await self.bot.get_content(f"{URL}sub.html", data={"id": randint(1, 20)})

                    elif num == 60:
                        await ctx.invoke(self.bot.get_command("friends"), nick=nick)
                    elif num == 63:
                        await self.bot.get_content(f"{URL}medkit.html", data={})
                        # if food & gift limits >= 10 it won't work.
                    else:
                        await ctx.send(f"**{nick}** ERROR: I don't know how to finish this mission ({num}).")
                    await sleep(randint(1, 7))
                    c = await self.bot.get_content(URL + "betaMissions.html?action=COMPLETE",
                                                   data={"submit": "Collect"})
                    if "MISSION_REWARD_OK" not in c and "?action=COMPLETE" not in c:
                        c = await self.bot.get_content(URL + "betaMissions.html?action=COMPLETE",
                                                       data={"submit": "Collect"})
                        if "MISSION_REWARD_OK" not in c and "?action=COMPLETE" not in c:
                            c = await self.bot.get_content(URL + "betaMissions.html",
                                                           data={"action": "SKIP", "submit": "Skip"})
                            if "MISSION_SKIPPED" not in c and "?action=SKIP" not in c:
                                return
                            else:
                                await ctx.send(f"**{nick}** WARNING: Skipped mission {num}")
                await ctx.send(f"**{nick}** <{c}>")
                prv_num = num
            except Exception as error:
                await ctx.send(f"**{nick}** ERROR: {error}")
                await sleep(5)
        await ctx.send(f"**{nick}** missions command reached its end.")
    """
    Mission #1: Check messages.
    Mission #2: First training.
    Mission #3: Your first job.
    Mission #4: First day of work.
    Mission #5: Five hits.
    Mission #6: Restore your health points.
    Mission #7: Go 'Berserk' in practice battle.
    Mission #8: Choose your avatar.
    Mission #9: Check notifications.
    Mission #10: Look at the map.
    Mission #11: Buy product
    Mission #12 Travel to the capital of your country.
    Mission #13 Learn about achievements.
    Mission #14 Wear something.
    Mission #15: Upvote one article.
    """

    @command(aliases=["hospital"])
    async def building(self, ctx, region_id: Id, quality: Quality, round: int, *, nick: IsMyNick):
        """Proposing a building law (for presidents)"""
        URL = f"https://{ctx.channel.name}.e-sim.org/"
        product_type = "DEFENSE_SYSTEM" if ctx.invoked_with.lower() == "building" else "HOSPITAL"
        payload = {'action': "PLACE_BUILDING", 'regionId': region_id, "productType": product_type,
                   "quality": quality, "round": round, 'submit': "Propose building"}
        url = await self.bot.get_content(URL + "countryLaws.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command(hidden=True)
    async def config(self, ctx, key, value, *, nick: IsMyNick):
        """Examples:
            .config alpha Admin  my_nick
            .config alpha_pw 1234  my_nick
            .config help ""  my_nick
        """
        filename = "config.json"
        with open(filename, "r") as file:
            big_dict = json.load(file)
        if not value and key in big_dict:
            del big_dict[key]
            del environ[key]
            await ctx.send(f"I have deleted the `{key}` key from {nick}'s config.json file")
        else:
            big_dict[key] = value
            environ[key] = value
            await ctx.send(f"I have added the following pair to {nick}'s config.json file: `{key} = {value}`")
        with open(filename, "w") as file:
            json.dump(big_dict, file)

    @command()
    async def register(self, ctx, lan, country_id: int, *, nick: IsMyNick):
        """User registration.
        If you want to register with a different nick or with another password, see .help config"""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        headers = {"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 5.1.1; AFTM Build/LVY48F) CTV"}
        async with ClientSession(headers=headers) as session:
            async with session.get(URL, ssl=True) as _:
                async with session.get(URL + "index.html?advancedRegistration=true&lan=" + lan.replace(f"{URL}lan.", ""), ssl=True) as _:
                    payload = {"login": nick, "password": environ.get(server+"_pw", environ['pw']), "mail": "",
                               "countryId": country_id, "checkHuman": "Human"}
                    async with session.post(URL + "registration.html", data=payload, ssl=True) as registration:
                        if "profile" not in str(registration.url) and URL + "index.html" not in str(registration.url):
                            await ctx.send(f"**{nick}** ERROR: Could not register")
                        else:
                            await ctx.send(f"**{nick}** <{registration.url}>\nHINT: type `.help avatar` and `.help job`")

    @command()
    async def report(self, ctx, target_citizen: Id, category, report_reason, *, nick: IsMyNick):
        """Reporting a citizen.
        * The report_reason should be within quotes"""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"

        categories = ["STEALING_ORG", "POSSIBLE_MULTIPLE_ACCOUNTS", "AUTOMATED_SOFTWARE_OR_SCRIPTS", "UNPAID_DEBTS",
                      "SLAVERY", "EXPLOITING_GAME_MECHANICS", "ACCOUNT_SITTING", "PROFILE_CONTENT", "OTHER"]
        if category in categories:
            payload = {"id": target_citizen, 'action': "REPORT_MULTI", "ticketReportCategory": category,
                       "text": report_reason, "submit": "Report"}
            url = await self.bot.get_content(f"{URL}ticket.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")
        else:
            await ctx.send(f"**{nick}** category can be one of:\n" + ", ".join(categories) + f"\n(not {category})")

    @command()
    async def elect(self, ctx, your_candidate, *, nick: IsMyNick):
        """Voting in congress / president elections."""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        today = int(datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%d"))  # game time

        if today == 5:
            president = True
            link = "presidentalElections.html"
        elif today == 25:
            president = False
            link = "congressElections.html"
        else:
            return await ctx.send(f"**{nick}** ERROR: There are not elections today")

        tree = await self.bot.get_content(URL + link, return_tree=True)
        payload = None
        for tr in range(2, 100):
            try:
                name = tree.xpath(f'//*[@id="esim-layout"]//tr[{tr}]//td[2]/a/text()')[0].strip().lower()
            except:
                return await ctx.send(f"**{nick}** ERROR: No such candidate ({your_candidate})")
            if name == your_candidate.lower():
                if president:
                    candidateId = tree.xpath(f'//*[@id="esim-layout"]//tr[{tr}]/td[4]/form/input[2]')[0].value
                else:
                    candidateId = tree.xpath(f'//*[@id="esim-layout"]//tr[{tr}]//td[5]//*[@id="command"]/input[2]')[0].value
                payload = {'action': "VOTE", 'candidateId': candidateId, "submit": "Vote"}
                break

        if payload:
            url = await self.bot.get_content(URL + link, data=payload)
            await ctx.send(f"**{nick}** <{url}>")
        else:
            await ctx.send(f"**{nick}** candidate {your_candidate} was not found")

    @command()
    async def law(self, ctx, link_or_id: Id, your_vote, *, nick: IsMyNick):
        """Voting a law"""
        server = ctx.channel.name
        URL = f"https://{server}.e-sim.org/"
        if your_vote.lower() not in ("yes", "no"):
            return await ctx.send(f"**{nick}** ERROR: Parameter 'vote' can be 'yes' or 'no' only! (not {your_vote})")
        link_or_id = f"{URL}law.html?id={link_or_id}"

        payload = {'action': f"vote{your_vote.capitalize()}", "submit": f"Vote {your_vote.upper()}"}
        url = await self.bot.get_content(link_or_id, data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command(hidden=True)
    async def click(self, ctx, link, *, nick: IsMyNick):
        """Clicks on a given link.
        (redeem code, add friend etc.)"""
        url = await self.bot.get_content(link)
        await ctx.send(f"**{nick}** <{url}>")

    @command(hidden=True)
    async def login(self, ctx, *, nick: IsMyNick):
        server = ctx.channel.name
        if server in self.bot.cookies:
            del self.bot.cookies[server]
        if not self.bot.cookies:
            self.bot.cookies["not"] = "empty"
        await ctx.send(f"**{nick}:** done")

    @command(hidden=True)
    async def shutdown(self, ctx, *, nick: IsMyNick):
        """Shutting down specific nick (in case of ban or something)
        Warning: It shutting down from all servers."""
        await ctx.send(f"**{nick}** shut down")
        await self.bot.close()


def setup(bot):
    bot.add_cog(Mix(bot))
