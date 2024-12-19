"""
Pomodoro-timer as an argus glue-service

Make an incident for taking a break every N minutes then close the incident
M minutes later.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta
import os
import sys
import time

from pyargus.client import Client
from pyargus.models import Incident
from simple_rest_client import exceptions
import httpx


__version__ = "0.1"
__progname__ = os.path.basename(sys.argv[0])
__description__ = "Pomodoro-timer as an argus glue-service"


API_VERSION = 2
API_TEMPLATE = f"api/v{API_VERSION}/"


# argus API

@contextmanager
def translate_api_error(context=None):
    error_msg = ""
    try:
        yield
    except httpx.ConnectError as e:
        error_msg = f"Connection error: {e}"
    except httpx.UnsupportedProtocol as e:
        error_msg = f"Unsupprted protocol: {e}"
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


def check_connection(client, config):
    with translate_api_error("Failed to connect on check"):
        next(client.get_my_incidents())
    if config.debug:
        print("Checking: host and token ok")
    sys.exit(0)


def find_previous_break_incident(client):
    incidents = list(client.get_my_incidents(open=True))
    assert 0 <= len(incidents) < 2, "Too many open pomodoro incidents!"
    if not incidents:
        return None
    if len(incidents) == 1:
        return incidents[0]
    # TBD: there's been an error, close all irrelevant incidents


def start_break_incident(client, config):
    tags = {
        "break_duration": config.break_duration,
        "time_between_breaks": config.work_duration,
    }
    incident = Incident(
        description="Break time!",
        start_time=datetime.now().astimezone(),
        tags=tags,
    )
    client.post_incident(incident)
    return incident


def stop_break_incident(incident, client):
    client.resolve_incident(
        incident=incident.pk,
        description="Break over!",
        timestamp=datetime.now().astimezone(),
    )


# configuration/argument parsing


def make_argparser():
    parser = argparse.ArgumentParser(
        prog=__progname__,
        description=__description__,
    )

    parser.add_argument("host", help="Argus API host url (with scheme)")
    parser.add_argument("token", help="Token to authenticate with")
    parser.add_argument(
        "-b",
        "--break-duration",
        type=int,
        help="How many minutes to take a break",
        default=5,
    )
    parser.add_argument(
        "-w",
        "--work-duration",
        type=int,
        help="How many minutes between breaks",
        default=15,
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Print debug info",
    )
    parser.add_argument(
        "-c",
        "--check",
        action="store_true",
        help="Check host and token by connecting to the host",
    )
    return parser


def get_config(args):
    args.endpoint = f"{args.host}/{API_TEMPLATE}"
    return args


# action!


def run(args):
    config = get_config(args)

    client = Client(api_root_url=config.endpoint, token=config.token)

    if config.check:
        check_connection(client, config)

    loop(client, config)


def loop(client, config):
    break_duration = timedelta(minutes=config.break_duration)
    work_duration = timedelta(minutes=config.work_duration)
    if config.debug:
        print("Break duration:", break_duration)
        print("Work duration:", work_duration)
        print()

    while True:
        now = datetime.now().astimezone()
        with translate_api_error("Failed when looking for previous incident"):
            incident = find_previous_break_incident(client)
        if not incident:
            with translate_api_error("Failed when creating break incident"):
                incident = start_break_incident(client, config)
        break_start = incident.start_time
        break_end = break_start + break_duration
        if config.debug:
            print("Break started at", break_start)
            print("         ends at", break_end)
        if now >= break_end:
            with translate_api_error("Failed when closing break incident"):
                stop_break_incident(incident, client)
                time_to_sleep = work_duration.total_seconds()
                if config.debug:
                    print(f"Next break in {time_to_sleep} seconds")
                    print()
                time.sleep(time_to_sleep)
                continue
        # on break!
        time_to_sleep = (break_end - now).total_seconds()
        if config.debug:
            print(f"Break over in {time_to_sleep} seconds")
            print()
        time.sleep(time_to_sleep)


def main(*rawargs):
    parser = make_argparser()
    args = parser.parse_args(*rawargs)
    run(args)


if __name__ == "__main__":
    main()
