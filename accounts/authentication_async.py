import aiohttp
import logging

ATHEME_JSONRPC_URL = "http://127.0.0.1:7001/jsonrpc"
logger = logging.getLogger(__name__)


async def authenticate_atheme_async(username: str, password: str):
    """Authenticate a user with Atheme's JSON-RPC API asynchronously."""
    payload = {"method": "atheme.login", "params": [username, password], "id": "1"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(ATHEME_JSONRPC_URL, json=payload, timeout=5) as response:
                if response.status != 200:
                    logger.error(f"❌ Atheme authentication failed (HTTP {response.status})")
                    return None

                data = await response.json()
                return data.get("result")

        except aiohttp.ClientError as e:
            logger.error(f"❌ Atheme authentication request failed: {str(e)}")
            return None


async def get_nickserv_info(username: str):
    """Fetch NickServ INFO for a given user asynchronously."""
    payload = {
        "method": "atheme.command",
        "params": [".", username, ".", "NickServ", "INFO", "."],
        "id": "1",
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(ATHEME_JSONRPC_URL, json=payload, timeout=5) as response:
                if response.status != 200:
                    logger.error(f"❌ Atheme NickServ INFO failed (HTTP {response.status})")
                    return None

                data = await response.json()
                return data.get("result", "")

        except aiohttp.ClientError as e:
            logger.error(f"❌ Atheme NickServ INFO request failed: {str(e)}")
            return None


import aiohttp
import logging

logger = logging.getLogger(__name__)

ATHEME_JSONRPC_URL = "http://127.0.0.1:7001/jsonrpc"

async def get_nickserv_list(authcookie: str, username: str):
    """Fetch a list of registered users from NickServ."""
    if not authcookie:
        logger.error("❌ Authcookie is missing!")
        return []

    payload = {
        "method": "atheme.command",
        "params": [authcookie, username, ".", "NickServ", "LIST", "*"],
        "id": "1",
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(ATHEME_JSONRPC_URL, json=payload, timeout=5) as response:
                if response.status != 200:
                    logger.error(f"❌ Atheme LIST command failed (HTTP {response.status})")
                    return []

                data = await response.json(content_type=None)  # ✅ Prevent JSON decode errors

                if not data or not isinstance(data, dict):  # ✅ Handle empty/invalid responses
                    logger.error("❌ Atheme returned an empty or invalid response.")
                    return []

                if "error" in data:
                    logger.error(f"❌ Atheme LIST error: {data['error'].get('message', 'Unknown error')}")
                    return []

                raw_list = data.get("result", "").split("\n")
                user_list = [
                    line.split(" - ")[1].split(" (")[0] for line in raw_list if "- NickServ -" in line
                ]  # ✅ Extract usernames

                return NickServQuerySet(user_list)  # ✅ Convert to a Django-like QuerySet
        except aiohttp.ClientError as e:
            logger.error(f"❌ Atheme LIST request failed: {str(e)}")
            return NickServQuerySet([])
        except Exception as e:
            logger.error(f"❌ Unexpected error while fetching NickServ list: {str(e)}")
            return NickServQuerySet([])


class NickServQuerySet:
    """Custom QuerySet-like class for Atheme NickServ users."""
    def __init__(self, user_list):
        self.user_list = user_list

    def all(self):
        """Return all users as objects with only the `username` field."""
        return [CustomUser(username=user) for user in self.user_list]

    def filter(self, **kwargs):
        """Filter usernames using Django-style ORM filters."""
        filtered_users = self.user_list
        username_filter = kwargs.get("username__icontains")
        if username_filter:
            filtered_users = [user for user in filtered_users if username_filter.lower() in user.lower()]
        return NickServQuerySet(filtered_users)