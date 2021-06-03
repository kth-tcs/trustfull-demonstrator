#!/usr/bin/env python3
import argparse
import json
import os
import string
import sys
from collections import Counter
from subprocess import check_output

import requests

VALID_CHARS = " -_.,()" + string.ascii_letters + string.digits


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "file",
        default="plaintexts",
        help="Plaintexts as produced by vmn",
        nargs="?",
    )
    parser.add_argument(
        "server",
        nargs="?",
        default="https://vmn-webapp.azurewebsites.net",
        help="Where to POST the results",
    )
    parser.add_argument(
        "--endpoint",
        default="results",
        help="Which endpoint to use to POST the results",
    )

    args = parser.parse_args()
    args.server = args.server.rstrip("/") + "/"
    args.endpoint = args.endpoint.strip("/")
    if not os.path.exists(args.file):
        raise RuntimeError("File not found")

    return args


def main(args):
    r = requests.post(args.server + args.endpoint, json=_print(vbt(args.file)))
    if r.ok:
        return 0

    print(r.status_code, r.text, file=sys.stderr)
    return 1


def vbt(fname):
    return Counter(
        map(
            lambda x: "".join(
                # Plaintexts is a byte tree with N children where each child is
                # a byte tree with 2 children. The first of the inner children
                # is the vote in ASCII bytes.
                c
                for c in map(chr, bytes.fromhex(x[0]))
                if c in VALID_CHARS
            ),
            _check_output_vbt(fname),
        )
    )


def _check_output_vbt(fname):
    COMMAND = ["vbt"]
    # vbt converts the RAW plaintexts to JSON.
    return json.loads(
        # Read output from vbt but discard null bytes
        # See: https://github.com/verificatum/verificatum-vcr/pull/4
        bytes(
            filter(
                bool,
                check_output(
                    COMMAND
                    + [
                        fname,
                    ]
                ),
            )
        ).decode()
    )


def _print(x, **kwargs):
    print(x, **kwargs)
    return x


if __name__ == "__main__":
    sys.exit(main(parse_args()))
