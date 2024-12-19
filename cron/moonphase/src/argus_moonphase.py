"""
Example glue service that is run from cron

Sends the same stateless incident each time, like a heart beat
"""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import sys
from urllib.parse import urlparse

from moontool import moon
from pyargus.client import Client
from pyargus.models import Incident
from simple_rest_client import exceptions


__version__ = "0.1"
__progname__ = os.path.basename(sys.argv[0])
__description__ = "Send heart beat to argus"


API_VERSION = 2
API_TEMPLATE = f"api/v{API_VERSION}/"
MESSAGE = "Current moon phase: {moon_phase_icon} {moon_phase_name}"


# helpers


class ValidateUrl(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        url = urlparse(values)
        if not (url.scheme and url.netloc):
            parser.error(f"Please enter a valid url. Got: {values}")
        setattr(namespace, self.dest, values)


# talk to source


@dataclass
class MoonPhase:
    id: int
    name: str
    icon: str
    phase_fraction: float
    lunation: int
    timestamp: datetime


def get_moonphase(timestamp=None):
    if not timestamp:
        timestamp = datetime.now(timezone.utc)
    if not timestamp.tzinfo:
        timestamp = timestamp.astimezone(timezone.utc)
    mc = moon.mooncal(timestamp)
    mp = moon.moonphase(timestamp)
    moonphase = MoonPhase(
        id=mp.phase,
        phase_fraction=mp.fraction_of_lunation,
        name=mp.phase_name,
        icon=mp.phase_icon,
        lunation=mc.lunation,
        timestamp=mp.utc_datetime,
    )
    return moonphase


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


def get_last_moonphase_incident(client):
    incidents = list(client.get_my_incidents(open=True))
    assert 0 <= len(incidents) < 2, "Too many open moon phase incidents!"
    if not incidents:
        return None
    if len(incidents) == 1:
        return incidents[0]
    # TBD: there's been an error, close all irrelevant incidents


def close_former_moonphase(client, incident, moonphase):
    if not incident:
        # First run, nothing to close
        return
    message = f'''End of moon phase "{incident.tags['moon_phase_name']}"'''
    client.resolve_incident(incident, message, timestamp=moonphase.timestamp)


def push_changed_moonphase(client, moonphase):
    tags = {
        "moon_phase_id": moonphase.id,
        "moon_phase_fraction": moonphase.phase_fraction,
        "moon_phase_name": moonphase.name,
        "moon_phase_icon": moonphase.icon,
        "lunation": moonphase.lunation,
    }
    message = MESSAGE.format(**tags)
    incident = Incident(
        source_incident_id=moonphase.lunation,
        description=message,
        start_time=moonphase.timestamp,
        tags=tags,
    )
    client.post_incident(incident)


def update_moonphase(client):
    moonphase = get_moonphase()
    previous_incident = get_last_moonphase_incident(client)
    if previous_incident:
        previous_phase = int(previous_incident.tags["moon_phase_id"])
        if previous_phase == moonphase.phase:
            # still in current moonphase
            return False, moonphase
        close_former_moonphase(client, previous_incident, moonphase)
    push_changed_moonphase(client, moonphase)
    return True, moonphase


# configuration/argument parsing


def make_argparser():
    parser = argparse.ArgumentParser(
        prog=__progname__,
        description=__description__,
    )

    parser.add_argument("host", help="Argus API host (hostname)")
    parser.add_argument("token", help="Token to authenticate with")
    parser.add_argument("-v", "--verbose", help="Output to CLI", action="store_true")
    return parser


def get_config(args):
    args.endpoint = f"{args.host}/{API_TEMPLATE}"
    return args


# action!


def run(args):
    config = get_config(args)
    client = Client(api_root_url=config.endpoint, token=config.token)
    with translate_api_error():
        updated, moonphase = update_moonphase(client)
    if args.verbose:
        if not updated:
            sys.stdout.write(f"Moonphase is still {moonphase.name}\n")
        else:
            sys.stdout.write(f"Moonphase changed to {moonphase.name}\n")


def main():
    parser = make_argparser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
