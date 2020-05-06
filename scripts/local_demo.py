#!/usr/bin/env python3

import argparse
import json
import os
import string
from collections import Counter
from itertools import chain
from subprocess import Popen
from subprocess import call as subprocess_call
from subprocess import check_output


def main(args):
    print(args)

    if args.vmni:
        vmni(args)
    if args.vmn:
        vmn(args)
    if args.vbt and not args.dry_run:
        print(vbt())

    return 0


def vmni(args):
    """See:
    2 - Info File Generator
    2.1 - Basic Usage
    """
    vmni_common_parameters(args)
    vmni_individual_protocol_info_files(args)
    vmni_merge_protocol_info_files(args)


def vmni_common_parameters(args):
    """See:
    1. Agree on common parameters
    """
    args.call(
        [
            "vmni",
            "-prot",
            "-sid",
            args.session_id,
            "-name",
            args.name,
            "-nopart",
            args.num_part,
            "-thres",
            args.threshold,
            "stub.xml",
        ]
    )


def vmni_individual_protocol_info_files(args):
    """See:
    2. Generate individual info files
    """
    for idx, ip in enumerate(args.ips):
        name = args.party_format.format(idx=idx)
        priv = f"{idx}/privInfo.xml"
        prot = f"{idx}/protInfo.xml"
        http = args.http_format.format(ip=ip, idx=idx, port=args.http_port + idx)
        hint = args.hint_format.format(ip=ip, idx=idx, port=args.hint_port + idx)
        if not args.dry_run:
            os.makedirs(f"{idx}", exist_ok=True)
        args.call(
            [
                "vmni",
                "-party",
                "-name",
                name,
                "-http",
                http,
                "-hint",
                hint,
                "stub.xml",
                "-dir",
                f"{idx}/dir",
                priv,
                prot,
            ]
        )


def vmni_merge_protocol_info_files(args):
    """See:
    3. Merge protocol info files.
    """
    args.call(
        ["vmni", "-merge"]
        + [f"{idx}/protInfo.xml" for idx in range(args.num_parties)]
        + ["merged.xml"]
    )


def vmn(args):
    """See:
    3.Mix-Net
    """
    processes = [
        args.call(
            ["vmn", "-keygen", "privInfo.xml", "../merged.xml", "publicKey"],
            popen=True,
            cwd=str(idx),
        )
        for idx in range(args.num_parties)
    ]
    # return [p.communicate() for p in processes]
    for p in processes:
        p.communicate()

    if args.demo:
        args.call(["vmnd", "-ciphs", "0/publicKey", 100, "ciphertexts"])
    elif args.dry_run:
        pass
    elif args.post:
        with open("0/publicKey", "rb") as f:
            request("POST", f"{args.post}/publicKey", files={"publicKey": f})
        input("Vote and press Enter ")
        with open("ciphertexts", "wb") as f:
            r = request("GET", f"{args.post}/ciphertexts")
            f.write(r.content)
    else:
        while not os.path.exists("ciphertexts"):
            input("Please collect ciphertexts and press Enter ")

    processes = [
        args.call(
            [
                "vmn",
                "-mix",
                "privInfo.xml",
                "../merged.xml",
                "../ciphertexts",
                "plaintexts",
            ],
            popen=True,
            cwd=str(idx),
        )
        for idx in range(args.num_parties)
    ]
    for p in processes:
        p.communicate()


def request(method, *args, **kwargs):
    import requests

    method = {"post": requests.post, "get": requests.get}[method.lower()]
    print(method.__name__, args, kwargs)

    r = method(*args, **kwargs)
    r.raise_for_status()
    return r


VALID_CHARS = " -_.,()" + string.ascii_letters + string.digits


def vbt():
    """
    Output & tallying
    """
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
            # vbt converts the RAW plaintexts to JSON.
            json.loads(
                # Read output from vbt but discard null bytes
                # TODO: fix this in vbt
                bytes(filter(bool, check_output(["vbt", "0/plaintexts"]))).decode()
            ),
        )
    )


def call(cmd, popen=False, **kwargs):
    cmd_strings = [str(x) for x in cmd]
    print(" ".join(cmd_strings))

    out_basename = os.path.join(
        kwargs.get("cwd", "."), str_to_fname(chain.from_iterable(cmd_strings))
    )
    with open(out_basename + "-stdout.txt", "w") as out, open(
        out_basename + "-stderr.txt", "w"
    ) as err:
        kwargs.setdefault("stdout", out)
        kwargs.setdefault("stderr", err)

        if popen:
            return Popen(cmd_strings, **kwargs)
        assert subprocess_call(cmd_strings, **kwargs) == 0, "subprocess.call failed"
        return None


def call_print(cmd, popen=False, **_):
    cmd_strings = [str(x) for x in cmd]
    print(" ".join(cmd_strings))
    if popen:

        class FakePopen:
            def communicate(self):
                pass

        return FakePopen()
    return 0


def str_to_fname(iterable):
    return "".join(c for c in iterable if c in VALID_CHARS)


def parse_args():
    parser = argparse.ArgumentParser()

    # TODO: Which phases to run
    parser.add_argument("--no-vmni", action="store_false", dest="vmni")
    parser.add_argument("--no-vmn", action="store_false", dest="vmn")
    parser.add_argument("--no-vbt", action="store_false", dest="vbt")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--post", nargs="?", default=None, const="https://vmn-webapp.azurewebsites.net/"
    )

    # 2.1.1 common parameters
    parser.add_argument("-sid", "--session-id", default="Session1")
    parser.add_argument("-name", "--name", default="myElection")
    parser.add_argument("-nopart", "--num-part", default=3, type=int)
    parser.add_argument("-thres", "--threshold", default=0, type=int)

    # 2.1.2 Individual info files
    parser.add_argument("-n", "--num-parties", default=3, type=int)
    parser.add_argument("--http-format", default="http://{ip}:{port}")
    parser.add_argument("--http-port", default=25432, type=int)
    parser.add_argument("--hint-format", default="{ip}:{port}")
    # parser.add_argument("--hint-format", default="http://verificatum.assert-team.eu:{port}")
    parser.add_argument("--hint-port", default=24321, type=int)
    parser.add_argument("--party-format", default="party{idx}")
    parser.add_argument("--ip", "-i", action="append", dest="ips")

    args = parser.parse_args()

    if args.threshold <= 0:
        args.threshold = args.num_part

    if args.ips is None:
        args.ips = ["localhost"] * args.num_parties
    elif len(args.ips) != args.num_parties:
        raise ValueError("Wrong number of IPs passed")

    args.call = call_print if args.dry_run else call
    if args.post:
        args.post = args.post.rstrip("/")

    return args


if __name__ == "__main__":
    import sys

    sys.exit(main(parse_args()))
