#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
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
        udp = self.args.port_udp
        return f"vmni -party -name party{idx} -http http://{self.ip}:{http} -httpl http://{hostname}:{http} -hint {self.ip}:{udp} -hintl {hostname}:{udp} stub.xml -dir {idx}/dir {idx}/privInfo.xml {idx}/protInfo.xml"

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
        "--port_http",
        default=8042,
        help="VMN http port",
        metavar="PORT",
        type=int,
    )
    parser.add_argument(
        "--port_udp",
        default=4042,
        help="VMN udp port",
        metavar="PORT",
        type=int,
    )
    parser.add_argument(
        "--server",
        default="https://vmn-webapp.azurewebsites.net/",
        help="Where to POST the public key and GET the ciphertexts from",
    )

    return parser.parse_args()


def main(args):
    if args.login:
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

    subprocess.call(["docker", "start", args.container], stdout=subprocess.DEVNULL)
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


def azure_call(cmd, container):
    return subprocess.check_output(
        ["docker", "exec", container] + cmd.split(" ")
    ).decode()


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


if __name__ == "__main__":
    sys.exit(main(parse_args()))
