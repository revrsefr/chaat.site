import base64
import os
import uuid

import requests


DEFAULT_RPC_TOKEN = os.getenv("ANOPE_RPC_TOKEN")


class RPCError(RuntimeError):
    """Raised when the JSON-RPC endpoint reports an error."""


class AnopeRPC:
    """Thin client modeled after docs/RPC/jsonrpc.rb."""

    def __init__(self, host="http://127.0.0.1:5600/jsonrpc", token=None):
        self.host = host
        self.token = token or DEFAULT_RPC_TOKEN

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.token:
            encoded = base64.b64encode(self.token.encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Bearer {encoded}"
        return headers

    def run(self, method, *params):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": [str(param) for param in params],
            "id": uuid.uuid4().hex,
        }

        try:
            response = requests.post(self.host, json=payload, headers=self._headers(), timeout=5)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise RPCError(f"RPC request failed: {exc}") from exc

        data = response.json()
        if "error" in data:
            err = data["error"]
            raise RPCError(f"JSON-RPC returned {err.get('code')}: {err.get('message')}")
        return data.get("result")

    # rpc_data helpers

    def list_accounts(self, detail="name"):
        return self.run("anope.listAccounts", detail)

    def account(self, name):
        return self.run("anope.account", name)

    def list_channels(self, detail="name"):
        return self.run("anope.listChannels", detail)

    def channel(self, name):
        return self.run("anope.channel", name)

    def list_opers(self, detail="name"):
        return self.run("anope.listOpers", detail)

    def oper(self, name):
        return self.run("anope.oper", name)

    def list_servers(self, detail="name"):
        return self.run("anope.listServers", detail)

    def server(self, name):
        return self.run("anope.server", name)

    def list_users(self, detail="name"):
        return self.run("anope.listUsers", detail)

    def user(self, name):
        return self.run("anope.user", name)

    # rpc_message helpers

    def message_network(self, *messages):
        return self.run("anope.messageNetwork", *messages)

    def message_server(self, server_name, *messages):
        return self.run("anope.messageServer", server_name, *messages)

    def message_user(self, source, target, *messages):
        return self.run("anope.messageUser", source, target, *messages)

    # rpc_user helpers

    def check_credentials(self, account, password):
        return self.run("anope.checkCredentials", account, password)

    def identify(self, account, user):
        return self.run("anope.identify", account, user)

    def list_commands(self, *services):
        return self.run("anope.listCommands", *services)

    def command(self, account, service, *command):
        return self.run("anope.commands", account, service, *command)

    # chanstats_plus (third-party)

    def chanstatsplus_get_channel(self, channel, nick="", period="total", period_start=""):
        return self.run("anope.chanstatsplus.getChannel", channel, nick, period, period_start)

    def chanstatsplus_get_nick(self, nick, channel="", period="total", period_start=""):
        return self.run("anope.chanstatsplus.getNick", nick, channel, period, period_start)

    def chanstatsplus_top(self, channel="", period="total", metric="lines", limit=10, period_start=""):
        return self.run("anope.chanstatsplus.top", channel, period, metric, limit, period_start)

    def chanstatsplus_top_channels(self, period="total", metric="lines", limit=10, period_start=""):
        return self.run("anope.chanstatsplus.topChannels", period, metric, limit, period_start)

    def chanstatsplus_top_nicks_global(self, period="total", metric="lines", limit=10, period_start=""):
        return self.run("anope.chanstatsplus.topNicksGlobal", period, metric, limit, period_start)

    def chanstatsplus_list_nicks_in_channel(self, channel, period="total", period_start="", limit=50, offset=0):
        return self.run(
            "anope.chanstatsplus.listNicksInChannel",
            channel,
            period,
            period_start,
            limit,
            offset,
        )

    def chanstatsplus_list_channels_for_nick(self, nick, period="total", period_start="", limit=50, offset=0):
        return self.run(
            "anope.chanstatsplus.listChannelsForNick",
            nick,
            period,
            period_start,
            limit,
            offset,
        )

    # Backwards compat alias used by early templates
    def get_channel(self, name):
        return self.channel(name)
