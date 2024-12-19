"""
Example glue service that is run from cron

Sends the same stateless incident each time, like a heart beat
"""

import argparse
from contextlib import contextmanager
from datetime import datetime
import os
import sys
from urllib.parse import urlparse

from pyargus.client import Client
from pyargus.models import Incident, STATELESS
from simple_rest_client import exceptions


__version__ = "0.1"
__progname__ = os.path.basename(sys.argv[0])
__description__ = "Send heart beat to argus"


API_VERSION = 2
API_TEMPLATE = f"api/v{API_VERSION}/"
DEFAULT_MESSAGE = "Beep-boop, Johnny 5 is alive!"


# helpers

class ValidateUrl(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        url = urlparse(values)
        if not (url.scheme and url.netloc):
            parser.error(f"Please enter a valid url. Got: {values}")
        setattr(namespace, self.dest, values)


def _str_localized_datetime(timestamp: datetime) -> str:
    timestamp = timestamp.isoformat()
    pieces = timestamp.split("+")
    if len(pieces) == 2 and pieces[-1] == "+00:00":
        return pieces[0] + "Z"
    return timestamp


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


def push_heartbeat_incident(client, config=None):
    tags = {
        "still_alive": _str_localized_datetime(timestamp),
    }
    incident = Incident(
        description=config.message,
        start_time=datetime.now().astimezone(),
        end_time=STATELESS,
        tags=tags,
    )
    client.post_incident(incident)


# configuration/argument parsing

def make_argparser():
    parser = argparse.ArgumentParser(
        prog=__progname__,
        description=__description__,
    )

    parser.add_argument("host", help="Argus API host url (with scheme)", action=ValidateUrl)
    parser.add_argument("token", help="Token to authenticate with")
    parser.add_argument("-m", "--message", help="Message to send", default=DEFAULT_MESSAGE)
    return parser


def get_config(args):
    args.endpoint = f"{args.host}/{API_TEMPLATE}"
    return args


# action!

def run(args):
    config = get_config(args)
    client = Client(api_root_url=config.endpoint, token=config.token)
    with translate_api_error():
        push_heartbeat_incident(client, config)


def main(*rawargs):
    parser = make_argparser()
    args = parser.parse_args(*rawargs)
    run(args)


if __name__ == "__main__":
    main()
