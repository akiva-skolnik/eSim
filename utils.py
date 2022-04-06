import json
import os

if "database_url" in os.environ:
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except:
        import pip
        pip.main(['install', "dnspython"])
        pip.main(['install', "motor"])
        from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ['database_url'])
else:
    client = None


async def find(server: str, collection: str) -> list:
    if client is not None:
        database = client[server][collection]
        return await database.find().to_list(50)
    else:
        filename = f"{server}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r") as file:
                return [{**v, **{"_id": k}} for k, v in json.load(file).items()][:50]
        else:
            return list()


async def find_one(server: str, collection: str, ID: str) -> dict:
    if client is not None:
        database = client[server][collection]
        return await database.find_one({"_id": ID.lower()}, {"_id": 0}) or {}
    else:
        filename = f"{server}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r") as file:
                return json.load(file).get(ID.lower(), {})
        else:
            return dict()


async def replace_one(server: str, collection: str, ID: str, data: dict) -> None:
    if client is not None:
        database = client[server][collection]
        await database.replace_one({'_id': ID.lower()}, data, True)
    else:
        filename = f"{server}_{collection}.json"
        if filename in os.listdir():
            with open(filename, "r") as file:
                big_dict = json.load(file)
        else:
            big_dict = dict()
        big_dict[ID.lower()] = data
        with open(filename, "w") as file:
            json.dump(big_dict, file)
