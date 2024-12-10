"""
Send a fixed stateless incident to argus

"""

import argparse
from datetime import datetime
import os
import sys
from urllib.parse import urlparse

from pyargus.client import Client
from pyargus.models import Incident, STATELESS


__version__ = "0.1"
__progname__ = os.path.basename(sys.argv[0])
__description__ = "Send minimalistic message to argus"


API_VERSION = 2
API_TEMPLATE = f"api/v{API_VERSION}/"


# argus API calls

def push_minimalistic_incident(client, config=None):
    incident = Incident(
        description="Minimalistic one-off incident",
        start_time=datetime.now().astimezone(),
        end_time=STATELESS,
    )
    client.post_incident(incident)


# configuration/argument parsing

def make_argparser():
    parser = argparse.ArgumentParser(
        prog=__progname__,
        description=__description__,
    )

    parser.add_argument("host", help="Argus API host url (with scheme)")
    parser.add_argument("token", help="Token to authenticate with")
    return parser


def get_config(args):
    args.endpoint = f"{args.host}/{API_TEMPLATE}"
    return args


# action!

def run(args):
    config = get_config(args)
    client = Client(api_root_url=config.endpoint, token=config.token)
    push_minimalistic_incident(client, config)


def main(*rawargs):
    parser = make_argparser()
    args = parser.parse_args(*rawargs)
    run(args)


if __name__ == "__main__":
    main()
