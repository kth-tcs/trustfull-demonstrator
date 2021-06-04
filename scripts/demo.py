#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import string
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from urllib.parse import urljoin

import requests


class VirtualMachine:
    def __init__(self, d, args):
        self.name = d["name"]
        self.ip = azure_call(
            f"az vm show -d -g {args.group} -n {self.name} --query publicIps -o tsv",
            args.container,
        ).strip()
        self.idx = None
        self._last_p = None
        self.args = args

    def index(self, idx):
        self.idx = idx
        self.ip = self.ip.format(idx=idx + 1)

    def party(self, idx):
        self.idx = idx
        hostname = "0.0.0.0"
        http = self.args.port_http
        protocol = "http"
        udp = self.args.port_udp
        return f"vmni -party -name party{idx} -http {protocol}://{self.ip}:{http} -httpl {protocol}://{hostname}:{http} -hint {self.ip}:{udp} -hintl {hostname}:{udp} stub.xml -dir {idx}/dir {idx}/privInfo.xml {idx}/protInfo.xml"

    def ssh_call(self, cmds):
        self.communicate()
        self._last_p = p = ssh_call(self.ip, self.args.username, cmds)
        return p

    def communicate(self):
        p = self._last_p
        self._last_p = None
        if p is not None:
            return p.communicate()
        return None

    def get_prot_info(self):
        if self.idx is None:
            raise ValueError("No idx")

        self.communicate()

        dest = f"{self.idx}-protInfo.xml"
        scp(
            f"{self.args.username}@{self.ip}:~/election/{self.idx}/protInfo.xml",
            dest,
            override=True,
        )

    def send_prot_info(self, n):
        if self.idx is None:
            raise ValueError("No idx")

        self.communicate()

        for idx in range(n):
            if idx == self.idx:
                continue

            fname = f"{idx}-protInfo.xml"
            if not os.path.exists(fname):
                raise RuntimeError(f"{fname} not found")

            scp(fname, f"{self.args.username}@{self.ip}:~/election/{idx}/protInfo.xml")


def parse_args():
    parser = argparse.ArgumentParser()
    # Globals
    parser.add_argument(
        "--container",
        default="azure-cli",
        help="Logged-in azure-cli docker container. Setup using --login",
        metavar="NAME",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Initialize azure-cli container and login",
    )
    parser.add_argument(
        "--prefix",
        default="vmn",
        help="Azure server names start with this prefix string",
    )
    parser.add_argument(
        "--username",
        default="vmn",
        help="User used to ssh to servers",
    )
    parser.add_argument(
        "--group",
        default="tcs",
        help="Azure resource group to use",
    )
    parser.add_argument(
        "--vote-collecting-server",
        default="https://vmn-webapp.azurewebsites.net/",
        help="Where to POST the public key and GET the ciphertexts from",
        dest="server",
    )

    # Subparsers
    subparsers = parser.add_subparsers(dest="subparser_name", required=True)
    deploy_parser = subparsers.add_parser("deploy")
    start_election_parser = subparsers.add_parser("start")
    tally_election_parser = subparsers.add_parser("tally")
    stop_parser = subparsers.add_parser("stop")

    # Start election
    start_election_parser.add_argument(
        "--port_http",
        default=8042,
        help="VMN http port",
        metavar="PORT",
        type=int,
    )
    start_election_parser.add_argument(
        "--port_udp",
        default=4042,
        help="VMN udp port",
        metavar="PORT",
        type=int,
    )

    # Tally election
    tally_election_parser.add_argument(
        "--file",
        default="plaintexts",
        help="Plaintexts file as produced by vmn",
    )

    return parser.parse_args()


def main(args):
    return globals()[f"{args.subparser_name}_main"](args)


def deploy_main(args):
    print(args)
    raise NotImplementedError()


def start_main(args):
    start_docker(args)

    vms = json.loads(azure_call(f"az vm list -g {args.group}", args.container))
    vms = [
        VirtualMachine(vm, args)
        for vm in vms
        if vm.get("name", "").startswith(args.prefix)
    ]
    n = len(vms)

    for idx, vm in enumerate(vms):
        vm.index(idx)

    prot = f"vmni -prot -sid Session1 -name myElection -nopart {n} -thres {n} stub.xml"
    for idx, vm in enumerate(vms):
        vm.ssh_call(
            [
                "killall java || true",
                "rm -rf ~/election",
                "mkdir -p ~/election",
                "cd ~/election",
                "mkdir " + " ".join(map(str, range(n))),
                prot,
                vm.party(idx),
            ]
        )
        vm.get_prot_info()
    for vm in vms:
        vm.send_prot_info(n)
    prots = " ".join(f"{idx}/protInfo.xml" for idx in range(n))
    for vm in vms:
        vm.ssh_call(["cd ~/election", f"vmni -merge {prots} merged.xml"])
    for vm in vms:
        vm.ssh_call(
            [
                "cd ~/election",
                'export _JAVA_OPTIONS="-Djava.net.preferIPv4Stack=true"',
                f"vmn -keygen {vm.idx}/privInfo.xml merged.xml publicKey",
            ]
        )
    communicate_all(vms)

    scp(f"{args.username}@{vms[0].ip}:~/election/publicKey", "publicKey", override=True)

    with open("publicKey", "rb") as f:
        requests.post(
            urljoin(args.server, "publicKey"), files={"publicKey": f}
        ).raise_for_status()
    input(
        f"Public key pushed to {args.server}. Proceed with voting and press Enter when ready."
    )

    with open("ciphertexts", "wb") as f:
        r = requests.get(urljoin(args.server, "ciphertexts"))
        r.raise_for_status()
        f.write(r.content)

    # Or, generate the ciphertexts with vmnd:
    # subprocess.run(["vmnd", "-ciphs", "publicKey", "130", "ciphertexts"], check=True)

    for vm in vms:
        scp("ciphertexts", f"{args.username}@{vm.ip}:~/election/ciphertexts")
        vm.ssh_call(
            [
                "cd ~/election",
                'export _JAVA_OPTIONS="-Djava.net.preferIPv4Stack=true"',
                f"vmn -mix {vm.idx}/privInfo.xml merged.xml ciphertexts plaintexts",
            ]
        )
    communicate_all(vms)
    scp(
        f"{args.username}@{vms[0].ip}:~/election/plaintexts",
        "plaintexts",
        override=True,
    )

    return 0


def tally_main(args):
    if not os.path.exists(args.file):
        raise RuntimeError("File not found")
    vbt_json = vbt(args.file)
    print(vbt_json)
    r = requests.post(urljoin(args.server, "results"), json=vbt_json)
    if r.ok:
        return 0

    error(r.status_code, r.text)
    return 1


def stop_main(args):
    print(args)
    raise NotImplementedError()


def ssh_call(ip, username, cmds):
    if isinstance(cmds, str):
        cmds = [cmds]
    print(cmds)
    return subprocess.Popen(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking no",
            f"{username}@{ip}",
            " && ".join(cmds),
        ],
        stdout=subprocess.PIPE,
    )


def scp(src, dest, override=False):
    if override:
        try:
            os.remove(dest)
        except FileNotFoundError:
            pass
    return subprocess.run(["scp", src, dest], check=True)


def communicate_all(iterable):
    return [x.communicate() for x in iterable]


def start_docker(args):
    if args.login:
        login(args)

    ret = subprocess.call(
        ["docker", "start", args.container], stdout=subprocess.DEVNULL
    )
    if ret != 0:
        error(
            f"Starting docker container {args.container} failed.",
            "Did you setup the container with --login first?",
        )
        sys.exit(ret)


def login(args):
    subprocess.run(
        ["docker", "rm", "-f", args.container],
        check=False,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-it",
            "--name",
            args.container,
            "mcr.microsoft.com/azure-cli",
            "az",
            "login",
        ],
        check=True,
    )


def azure_call(cmd, container, **kwargs):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    elif not isinstance(cmd, Sequence):
        raise TypeError(f"cmd should be some type of Sequence, got {type(cmd)} instead")

    return subprocess.check_output(
        ["docker", "exec", container] + list(cmd), **kwargs
    ).decode()


def error(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    args = list(args)
    args[0] = "\033[91m" + args[0]  # Red
    args[-1] += "\033[0m"  # Reset
    print(*args, **kwargs)


def vbt(fname):
    valid_chars = " -_.,()" + string.ascii_letters + string.digits

    return Counter(
        map(
            lambda x: "".join(
                # Plaintexts is a byte tree with N children where each child is
                # a byte tree with 2 children. The first of the inner children
                # is the vote in ASCII bytes.
                c
                for c in map(chr, bytes.fromhex(x[0]))
                if c in valid_chars
            ),
            _check_output_vbt(fname),
        )
    )


def _check_output_vbt(fname):
    command = ["vbt"]

    # vbt converts the RAW plaintexts to JSON.
    return json.loads(
        # Read output from vbt but discard null bytes
        # See: https://github.com/verificatum/verificatum-vcr/pull/4
        bytes(
            filter(
                bool,
                subprocess.check_output(
                    command
                    + [
                        fname,
                    ]
                ),
            )
        ).decode()
    )


if __name__ == "__main__":
    sys.exit(main(parse_args()))
