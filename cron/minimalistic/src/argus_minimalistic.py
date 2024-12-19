"""
Send a fixed stateless incident to argus

"""

import argparse
from contextlib import contextmanager
from datetime import datetime
import os
import sys

from pyargus.client import Client
from pyargus.models import Incident, STATELESS
from simple_rest_client import exceptions


__version__ = "0.1"
__progname__ = os.path.basename(sys.argv[0])
__description__ = "Send minimalistic message to argus"


API_VERSION = 2
API_TEMPLATE = f"api/v{API_VERSION}/"


# argus API

@contextmanager
def translate_api_error(context=None):
    error_msg = ""
    try:
        yield
    except exceptions.ErrorWithResponse as e:
        response = e.response
        error_msg = f"{response.status_code} {response.client_response.reason_phrase} ({response.url})"
        if isinstance(response.body, dict):
            # HTTP status codes that have no content
            detail = response.body.get("detail", "")
            error_msg += f": {detail}"
    except exceptions.ClientConnectionError as e:
        error_msg = f"Failed to connect: {e}"
    except exceptions.ActionNotFound as e:
        error_msg = f"Unknown API call: {e}"
    except exceptions.ActionURLMatchError as e:
        error_msg = f"Unknown API endpoint: {e}"

    if not error_msg:
        return

    sys.stderr.write(error_msg + "\n")
    if context:
        sys.stderr.write(f"More context: {context}\n")
    sys.stderr.flush()

    sys.exit(1)


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
    with translate_api_error():
        push_minimalistic_incident(client, config)


def main(*rawargs):
    parser = make_argparser()
    args = parser.parse_args(*rawargs)
    run(args)


if __name__ == "__main__":
    main()
