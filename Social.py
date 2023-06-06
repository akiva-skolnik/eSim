"""Social.py"""
from asyncio import sleep
from json import loads
from typing import Union

from discord import Embed
from discord.ext.commands import Cog, command

import Eco
import utils
from Converters import Country, Id, IsMyNick


class Social(Cog):
    """Social Commands"""

    def __init__(self, bot):
        self.bot = bot

    @command()
    async def comment(self, ctx, action, shout_or_article_link, body, *, nick: IsMyNick):
        """Commenting an article or a shout.

        - `action` parameter can be: reply, edit or delete (for edit and delete comment, the link should contain id=<comment_id>)
        - `body` parameter MUST be within quotes.
        - You can find the shout & comment id by clicking F12 on the page where you see the shout."""

        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        shout_or_article_id = shout_or_article_link.split("?id=")[1].split("&")[0]
        action = action.lower()
        if "article" in shout_or_article_link:
            if action == "reply":
                payload = {"action": "NEW", "key": f"Article {shout_or_article_id}", "submit": "Publish", "body": body}
            elif action == "edit":
                payload = {"action": "EDIT", "id": shout_or_article_id, "submit": "Edit", "text": body}
            elif action == "delete":
                payload = {"action": "DELETE", "id": shout_or_article_id, "submit": "Delete"}
            else:
                return await ctx.send(f"action must be `reply`, `edit` or `delete`, not `{action}`")
            url = await self.bot.get_content(base_url + "comment.html", data=payload)
        elif "Shout" in shout_or_article_link:
            if action == "reply":
                payload = {"body": body, "submit": "Shout!"}
                link = f"replyToShout.html?id={shout_or_article_id}"
            elif action == "edit":
                payload = {"action": "EDIT_SHOUT", "id": shout_or_article_id, "submit": "Edit", "text": body}
                link = "shoutActions.html"
            elif action == "delete":
                payload = {"action": "DELETE_SHOUT", "id": shout_or_article_id, "submit": "Delete"}
                link = "shoutActions.html"
            else:
                return await ctx.send(f"action must be `reply`, `edit` or `delete`, not `{action}`")
            url = await self.bot.get_content(f"{base_url}{link}", data=payload)
        else:
            return await ctx.send(f"**{nick}** ERROR: invalid article/shout link.")
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def read(self, ctx, *, nick: IsMyNick):
        """Reading all new msgs and notifications + accept friend requests"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(base_url + "home.html", return_tree=True)
        msgs = int(str(tree.xpath("//*[@id='inboxMessagesMission']/b")[0].text))
        alerts = int(str(tree.xpath('//*[@id="numero1"]/a/b')[0].text))
        if alerts:
            reminding_alerts = alerts
            for page in range(1, reminding_alerts // 20 + 2):
                tree = await self.bot.get_content(f"{base_url}notifications.html?page={page}", return_tree=True)
                embed = Embed(title=f"**{nick}** {base_url}notifications.html?page={page}\n")
                for div in range(1, min(20, reminding_alerts) + 1):
                    try:
                        alert_date = tree.xpath(f'//*[@id="command"]/div/div[2]/div[{div}]/div/div[1]/div/b')[
                            0].text.strip()
                        alert = tree.xpath(f'//*[@id="command"]/div/div[2]/div[{div}]/div/div[2]')[
                            0].text_content().strip()
                        links = tree.xpath(f'//*[@id="command"]/div/div[2]/div[{div}]/div/div[2]/a/@href')
                    except IndexError:  # old format
                        try:
                            alert = tree.xpath(f'//tr[{div+1}]//td[2]')[0].text_content().strip()
                            alert_date = tree.xpath(f'//tr[{div+1}]//td[3]')[0].text_content().strip()
                            links = tree.xpath(f"//tr[{div+1}]//td[2]/a[2]/@href")
                        except IndexError:
                            break
                    if "has requested to add you as a friend" in alert:
                        await self.bot.get_content(base_url + str(links[-1]))
                    elif "has offered you to sign" in alert:
                        alert = alert.replace("contract", f'[contract]({base_url}{links[-1]})').replace(
                            "Please read it carefully before accepting it, make sure that citizen doesn't want to cheat you!",
                            f"\ntype `.contract {links[-1].split('=')[1]} {nick}` to accept it.")
                    elif len(links) > 1:
                        link = [x for x in links if "profile" not in x]
                        if link:
                            alert = f'[{alert}]({base_url}{link[0]})'
                        else:
                            alert = f'[{alert}]({base_url}{links[0]})'
                    elif links:
                        alert = f'[{alert}]({base_url}{links[0]})'
                    reminding_alerts -= 1
                    embed.add_field(name=alert_date, value=alert, inline=False)
                await ctx.send(embed=embed)

        if msgs:
            tree = await self.bot.get_content(base_url + "inboxMessages.html", return_tree=True)
            embed = Embed(title=f"**{nick}** {base_url}inboxMessages.html")
            for tr in range(2, msgs + 2):
                author = tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[1]//div/a[2]/text()')[0].strip()
                content = tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[2]/div[1]')[0].text_content().strip()
                title = tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[2]/b[1]//div')[0].text_content().strip()
                date = str(tree.xpath(f'//*[@id="inboxTable"]//tr[{tr}]//td[3]/b')[0].text).strip()
                embed.add_field(name=author, value=f"**{title}**\n{content}\n{date}", inline=False)
            await ctx.send(embed=embed)
        if not alerts and not msgs:
            await ctx.send(f"**{nick}:** There are no new alerts or messages!")

    @command(aliases=["MU"])
    async def citizenship(self, ctx, country_or_mu: Union[Country, Id], message: str, *, nick: IsMyNick):
        """Send application to a MU / country.
        The message should be within quotes."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        if ctx.invoked_with.lower() == "citizenship":
            payload = {'action': "APPLY", 'countryId': country_or_mu, "message": message, "submit": "Apply for citizenship"}
            link = "citizenshipApplicationAction.html"
            await self.bot.get_content(base_url + "countryLaws.html")
            await self.bot.get_content(base_url + "countryLaws.html", data={"action": "LEAVE_CONGRESS", "submit": "Leave congress"})
            await self.bot.get_content(base_url + "partyStatistics.html", data={"action": "LEAVE", "submit": "Leave party"})
            tree = await self.bot.get_content(base_url + "pendingCitizenshipApplications.html", return_tree=True)
            application_ids = tree.xpath("//*[@id='mobileYourApplication']//div//div[2]//form//input[2]/@value")
            if application_ids:
                await self.bot.get_content(base_url + "citizenshipApplicationAction.html",
                                           data={"action": "CANCEL", "applicationId": application_ids[0], "submit": "Cancel"})
        else:
            payload = {'action': "SEND_APPLICATION", 'id': country_or_mu, "message": message, "submit": "Send application"}
            link = "militaryUnitsActions.html"
            await self.bot.get_content(base_url + link, data={"action": "LEAVE_MILITARY_UNIT", "submit": "Leave military unit"})
            await self.bot.get_content(base_url + link, data={"action": "CANCEL_APPLICATION", "submit": "Cancel application"})
            await self.bot.get_content(base_url + link, data={"action": "LEAVE_MILITARY_UNIT", "submit": "Leave military unit"})

        url = await self.bot.get_content(base_url + link, data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def msg(self, ctx, receiver_name, title, body, *, nick: IsMyNick):
        """Sending a msg.
        If receiver_name, title or body contains more than 1 word - it must be within quotes"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        payload = {'receiverName': receiver_name, "title": title, "body": body, "action": "REPLY", "submit": "Send"}
        url = await self.bot.get_content(base_url + "composeMessage.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def shout(self, ctx, shout_body, *, nick: IsMyNick):
        """Publishing a shout.
        `shout_body` MUST be within quotes"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        payload = {'action': "POST_SHOUT", 'body': shout_body, 'sendToCountry': "on",
                   "sendToMilitaryUnit": "on", "sendToParty": "on", "sendToFriends": "on"}
        url = await self.bot.get_content(f"{base_url}shoutActions.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command(aliases=["vote", "vote_shout"])
    async def sub(self, ctx, id: Id, *, nick: IsMyNick):
        """Subscribe to specific newspaper / vote an article or a shout.
        (for voting a shout you will have to click F12 on the shouts page to find the id)"""

        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        if ctx.invoked_with.lower() == "sub":
            url = await self.bot.get_content(f"{base_url}sub.html", data={"id": id})
        elif ctx.invoked_with.lower() == "vote":
            url = await self.bot.get_content(f"{base_url}vote.html", data={"id": id})
        else:
            url = await self.bot.get_content(f"{base_url}shoutVote.html", data={"id": id, "vote": 1})
        await ctx.send(f"**{nick}** <{url}>")

    @command(aliases=["friends+"])
    async def friends(self, ctx, *, nick: IsMyNick):
        """Sending friend request to the entire server / all online citizens"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        await ctx.send(f"**{nick}** on it")
        blacklist = set()
        await Eco.get_rejected_contracts(self.bot, base_url, blacklist, "OTHER", "has removed you")
        results = []
        if ctx.invoked_with.lower() == "friends":
            for index, row in enumerate(await self.bot.get_content(f"{base_url}apiOnlinePlayers.html")):
                if utils.should_break(ctx):
                    break
                if (index+1) % 10 == 0 and results:
                    await ctx.send(f"**{nick}**\n" + "\n".join(results))
                    results.clear()
                row = loads(row)
                if row['login'] not in blacklist:
                    try:
                        url = f"{base_url}friends.html?action=PROPOSE&id={row['id']}"
                        send = await self.bot.get_content(url)
                        if send == url:
                            return await ctx.send(f"**{nick}** ERROR: you are not logged in, see `.help login`")
                        results.append(row['login'] + f": <{send}>")
                        await sleep(1)
                    except Exception as error:
                        await ctx.send(f"**{nick}** ERROR: {error}")

        else:
            tree = await self.bot.get_content(base_url + 'citizenStatistics.html?statisticType=DAMAGE&countryId=0', return_tree=True)
            last = utils.get_ids_from_path(tree, "//ul[@id='pagination-digg']//li[last()-1]/")[0]
            for page in range(1, int(last) + 1):
                if page != 1:
                    tree = await self.bot.get_content(
                        base_url + 'citizenStatistics.html?statisticType=DAMAGE&countryId=0&page=' + str(page), return_tree=True)
                friends = tree.xpath("//td/a/text()")
                links = utils.get_ids_from_path(tree, "//td/a")
                for friend, link in zip(friends, links):
                    if utils.should_break(ctx):
                        return
                    friend = friend.strip()
                    if friend not in blacklist:
                        try:
                            url = f"{base_url}friends.html?action=PROPOSE&id={link}"
                            send = await self.bot.get_content(url)
                            if send == url:
                                return await ctx.send(f"**{nick}** ERROR: you are not logged in, see `.help login`")
                            results.append(friend + f": <{send}>")
                            await sleep(1)
                        except Exception as error:
                            await ctx.send(f"**{nick}** ERROR: {error}")
                if results:
                    await ctx.send(f"**{nick}**, page {page}\n" + "\n".join(results))
                    results.clear()
        if results:
            await ctx.send(f"**{nick}**\n" + "\n".join(results))
        await ctx.send(f"**{nick}** done.")


def setup(bot):
    """setup"""
    bot.add_cog(Social(bot))
