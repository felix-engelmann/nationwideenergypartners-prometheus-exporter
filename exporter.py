import os
import time
import base64
import json
import requests
from datetime import datetime, timedelta

from pycognito import Cognito
from prometheus_client import start_http_server, REGISTRY
from prometheus_client.core import GaugeMetricFamily

# -----------------------
# Configuration
# -----------------------

USER_POOL_ID = "us-west-1_9FOe8eHZU"
CLIENT_ID = "2cubklfeh6j7qe9b46h7fs9k4t"
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

ACCOUNT_URL = "https://nep-api.cloud-thehth.com/v2/account"
USAGE_URL = "https://nep-api.cloud-thehth.com/v2/usage"

EXPORTER_PORT = 8000
REQUEST_TIMEOUT = 10  # seconds

SERVICES = ["WATER", "ELECTRIC"]

# -----------------------
# Cognito Session Wrapper
# -----------------------

class CognitoSession:
    def __init__(self, user_pool_id, client_id, username, password):
        self.u = Cognito(user_pool_id, client_id, username=username)
        self.password = password
        self.expiry = 0
        self.authenticate()

    def _decode_exp(self, token):
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        return decoded["exp"]

    def authenticate(self):
        self.u.authenticate(self.password)
        self.expiry = self._decode_exp(self.u.access_token)

    def get_access_token(self):
        if time.time() > self.expiry - 300:
            self.u.renew_access_token()
            self.expiry = self._decode_exp(self.u.access_token)
        return self.u.access_token

# -----------------------
# Extract latest usage
# -----------------------

def extract_latest_usage(usage_json):
    try:
        usage_history = usage_json["usage"]["usageHistory"]
        meter_data = usage_history[0]["usageData"]
        latest = meter_data[-1]
        return float(latest["value"])
    except Exception as e:
        print("Failed to parse usage JSON:", e)
        return 0

# -----------------------
# Collector
# -----------------------

class UsageCollector:
    def __init__(self, session, premise_id):
        self.session = session
        self.premise_id = premise_id

    def collect(self):
        api_up = GaugeMetricFamily(
            "nep_api_up",
            "API availability (1=up, 0=down)"
        )
        usage_gauge = GaugeMetricFamily(
            "nep_usage",
            "Latest usage for service",
            labels=["service","premise"]
        )

        try:
            token = self.session.get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            # End date = tomorrow
            end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")

            for service in SERVICES:
                payload = {
                    "admin": False,
                    "startDate": start_date,
                    "endDate": end_date,
                    "frequency": "M",
                    "premiseId": self.premise_id,
                    "service": service
                }

                resp = requests.post(
                    USAGE_URL,
                    headers=headers,
                    json=payload,
                    timeout=REQUEST_TIMEOUT
                )
                resp.raise_for_status()
                data = resp.json()

                usage_value = extract_latest_usage(data)
                usage_gauge.add_metric([service, self.premise_id], usage_value)

            api_up.add_metric([], 1)

        except Exception as e:
            api_up.add_metric([], 0)
            print("Error fetching usage:", e)

        yield usage_gauge
        yield api_up

# -----------------------
# Main
# -----------------------

def main():
    session = CognitoSession(USER_POOL_ID, CLIENT_ID, USERNAME, PASSWORD)

    print(session.get_access_token())
    # Fetch premiseId once at startup
    try:
        token = session.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        acc = requests.post(ACCOUNT_URL, headers=headers, timeout=REQUEST_TIMEOUT)
        acc.raise_for_status()
        services = acc.json()["myAccount"].get("serviceAddresses", [])
        premise_id_set = set(a["premiseId"] for a in services if "premiseId" in a)
        premise_id = next(iter(premise_id_set))  # take first
        print(f"Using premise ID: {premise_id}")
    except Exception as e:
        print("Failed to fetch account:", e)
        return

    # Register collector
    REGISTRY.register(UsageCollector(session, premise_id))

    start_http_server(EXPORTER_PORT)
    print(f"Exporter running on :{EXPORTER_PORT}/metrics")

    # Keep process alive; Prometheus scrapes trigger usage queries
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
