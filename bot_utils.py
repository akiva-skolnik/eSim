import os
import re
from asyncio import sleep
from difflib import unified_diff
from typing import Union
from io import StringIO
from discord import File
from aiohttp import ClientSession
from lxml.html import fromstring
from datetime import datetime

import utils


class BotUtils:
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def create_session(server: str = None) -> ClientSession:
        """create session"""
        headers = {"User-Agent": os.environ["headers"]}
        if server:
            headers["Host"] = server + ".e-sim.org"
        return ClientSession(headers=headers)

    async def get_session(self, server: str) -> ClientSession:
        """get session"""
        if server not in self.bot.sessions:
            self.bot.sessions[server] = await self.create_session(server)
        return self.bot.sessions[server]

    async def close_session(self, server: str) -> None:
        """close session"""
        if server in self.bot.sessions:
            await self.bot.sessions[server].close()
            del self.bot.sessions[server]

    async def inner_get_content(self, link: str, server: str, data=None, return_tree=False, extra_headers: dict = None) \
            -> Union[str, fromstring, tuple]:
        """inner get content"""
        method = "get" if data is None else "post"
        headers = {"User-Agent": os.environ["headers"]}
        if extra_headers:
            for k, v in extra_headers.items():
                headers[k] = v
        return_type = "json" if "api" in link or "battleScore" in link else "html"
        session = await self.get_session("incognito" if "api" in link else server)
        async with session.get(link, ssl=True, headers=headers) if method == "get" else \
                session.post(link, data=data, ssl=True, headers=headers) as respond:
            if "google.com" in str(respond.url) or respond.status == 403:
                raise ConnectionError

            if any(t in str(respond.url) for t in ("notLoggedIn", "error")):
                raise ConnectionError("notLoggedIn")

            if respond.status == 200:
                if return_type == "json":
                    api = await respond.json(content_type=None)
                    if "error" in api:
                        raise ConnectionError(api["error"])
                    return api if "apiBattles" not in link else api[0]
                respond_text = await respond.text(encoding='utf-8')
                tree = fromstring(respond_text)
                logged = tree.xpath('//*[@id="command"]')
                if server != "incognito" and any("login.html" in x.action for x in logged):
                    raise ConnectionError("notLoggedIn")
                await self.compare_and_save_page(link, respond_text)
                if isinstance(return_tree, str):
                    return tree, str(respond.url)
                return tree if return_tree else str(respond.url)
            await sleep(5)

    async def get_content(self, link, data=None, return_tree=False, incognito=False, extra_headers: dict = None) -> Union[str, fromstring, tuple]:
        """get content"""
        link = link.split("#")[0].replace("http://", "https://")
        server = "incognito" if incognito else link.split("https://", 1)[1].split(".e-sim.org", 1)[0]
        nick = utils.my_nick(server)
        base_url = f"https://{server}.e-sim.org/"
        not_logged_in = False
        tree = None
        try:
            tree = await self.inner_get_content(link, server, data, return_tree, extra_headers)
        except ConnectionError as exc:
            if "notLoggedIn" != str(exc):
                raise exc
            not_logged_in = True
        if not_logged_in and not incognito:
            await self.close_session(server)

            payload = {'login': nick, 'password': os.environ.get(server + "_password", os.environ.get('password')), "submit": "Login"}
            async with (await self.get_session(server)).get(base_url, ssl=True) as _:
                async with (await self.get_session(server)).post(base_url + "login.html", data=payload, ssl=True) as r:
                    print(datetime.now(), nick, server, r.url)
                    if "index.html?act=login" not in str(r.url):
                        raise ConnectionError(f"{nick} - Failed to login {r.url}")
            tree = await self.inner_get_content(link, server, data, return_tree, extra_headers)
        if tree is None:
            tree = await self.inner_get_content(link, server, data, return_tree, extra_headers)
        return tree

    @staticmethod
    def extract_functions_from_html(html_content):
        tree = fromstring(html_content)

        # Find all <script> tags
        script_tags = tree.xpath('//script')

        functions = []
        for script_tag in script_tags:
            # Extract the text content of the <script> tag
            script_content = script_tag.text_content()

            # Use regular expressions to find JavaScript functions inside the <script> tag
            function_pattern = re.compile(r'function\s+(\w+)\s*\([^)]*\)\s*{([^}]*)}', re.DOTALL)
            matches = function_pattern.findall(script_content)

            for match in matches:
                function_name, function_body = match
                functions.append(
                    "function " + function_name + "(...)\n" + function_body.strip())  # Remove leading/trailing whitespace

        return functions

    @staticmethod
    def measure_page_similarity(content1, content2):
        function_content1 = BotUtils.extract_functions_from_html(content1)
        function_content2 = BotUtils.extract_functions_from_html(content2)

        diff_changes = []
        diff_ratios = []

        for func1, func2 in zip(function_content1, function_content2):
            diff = unified_diff(func1.splitlines(), func2.splitlines(), lineterm='')
            diff_lines = list(diff)  # Convert the generator to a list
            num_diff_lines = sum(1 for line in diff_lines if not line.startswith(' '))

            max_lines = max(len(func1.splitlines()), len(func2.splitlines()))
            if max_lines != 0:
                diff_ratio = 1 - num_diff_lines / max_lines
                diff_ratios.append(diff_ratio)

            changes = []
            for line in diff_lines:
                if line.startswith('+'):
                    changes.append({'oldContent': '', 'newContent': line})
                elif line.startswith('-'):
                    changes.append({'oldContent': line, 'newContent': ''})
            diff_changes.extend(changes)

        average_similarity = sum(diff_ratios) / len(diff_ratios)

        return diff_changes, average_similarity

    @staticmethod
    def generate_diff_html(diff_changes):
        diff_html = f'''
    <!DOCTYPE html>
    <html>
    <head>
    <title>Function Differences</title>
    <style>
      body {{
        font-family: Arial, sans-serif;
      }}
      .diff-container {{
        display: flex;
      }}
      .diff-column {{
        flex: 1;
        padding: 10px;
        border: 1px solid #ccc;
        overflow: auto;
        white-space: pre;
      }}
      .added {{
        background-color: #aaffaa;
      }}
      .removed {{
        background-color: #ffaaaa;
      }}
    </style>
    </head>
    <body>
    
    <h1>Function Differences</h1>
    
    <div class="diff-container">
      <div class="diff-column" id="old-column"></div>
      <div class="diff-column" id="new-column"></div>
    </div>
    
    <script>
    function generateDiff(diffChanges) {{
      var oldColumn = document.getElementById('old-column');
      var newColumn = document.getElementById('new-column');
    
      for (var i = 0; i < diffChanges.length; i++) {{
        var change = diffChanges[i];
    
        var oldSpan = document.createElement('span');
        oldSpan.textContent = change.oldContent;
        oldSpan.className = 'removed';
        oldColumn.appendChild(oldSpan);
        oldColumn.appendChild(document.createElement('br'));
    
        var newSpan = document.createElement('span');
        newSpan.textContent = change.newContent;
        newSpan.className = 'added';
        newColumn.appendChild(newSpan);
        newColumn.appendChild(document.createElement('br'));
      }}
    }}
    
    var diffChanges = {diff_changes};
    generateDiff(diffChanges);
    </script>
    
    </body>
    </html>
    '''

        return diff_html

    @staticmethod
    def sanitize_filename(filename):
        # Remove invalid characters for both Linux and Windows file systems
        return re.sub(r'[/:*?"<>|]', '_', filename)

    @staticmethod
    async def compare_and_save_page(link, new_content):
        # Load the saved content from the previous session if it exists
        link = BotUtils.sanitize_filename(link)
        saved_content = None
        saved_pages_dir = "saved_pages"
        if not os.path.exists(saved_pages_dir):
            os.makedirs(saved_pages_dir)

        saved_pages_file = os.path.join(saved_pages_dir, f"{link}.txt")
        if os.path.exists(saved_pages_file):
            with open(saved_pages_file, "r", encoding="utf-8") as f:
                saved_content = f.read()
        # Save the new content
        with open(saved_pages_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        # Calculate similarity and handle based on the threshold
        if saved_content:
            diff_changes, average_similarity = BotUtils.measure_page_similarity(saved_content, new_content)

            if average_similarity < 0.98:  # TODO: custom (per page?)
                html_content = BotUtils.generate_diff_html(diff_changes)

                # Send the generated HTML content to a file
                raise Exception("message",
                                {"content": f"Page {link.replace('___', '://').replace('_', '/')} has significant changes since the last time you accessed it!\n"
                                            f"(Similarity of functions between the pages: {average_similarity:.2%})\n"
                                            f"If you still want to proceed, try again (at least download and open the first file below)",
                                 "files": [File(fp=StringIO(html_content), filename="function_diff.html"),
                                           File(fp=StringIO(saved_content), filename=f"old_{link}.html"),
                                           File(fp=StringIO(new_content), filename=f"new_{link}.html")]})
