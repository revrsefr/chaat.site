import json
import requests

class AnopeRPC:
    def __init__(self, host="http://127.0.0.1:5600/jsonrpc"):  # Updated port to 5600
        self.host = host

    def run(self, method, params=None):
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": method,
            "params": params or []
        }
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(self.host, json=payload, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            if "result" in data:
                return data["result"]
            elif "error" in data:
                print(f"Anope Error: {data['error']}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"RPC Request Failed: {e}")
            return None

    def list_channels(self):
        return self.run("anope.listChannels")

    def get_channel(self, channel):
        result = self.run("anope.channel", [channel])
        if not result:
            return {"name": channel, "users": [], "topic": {"value": "No topic set"}}
        return result

    def list_users(self):
        return self.run("anope.listUsers")

    def get_user(self, user):
        return self.run("anope.user", [user])
