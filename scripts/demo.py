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
from multiprocessing import Pool
from urllib.parse import urljoin


def error(*args, **kwargs):
    print_color("\033[91m", *args, **kwargs)  # Red


def info(*args, **kwargs):
    print_color("\033[33m", *args, **kwargs)  # Red


def print_color(color, *args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    args = list(args)
    args[0] = color + str(args[0])
    args[-1] = str(args[-1]) + "\033[0m"  # Reset
    print(*args, **kwargs)


try:
    import requests
except ImportError:
    requests = None
    error(
        "Python library `requests` is not installed, commands `start` and `tally` will not work."
    )


class VirtualMachine:
    def __init__(self, vm_id, args):
        d = json.loads(
            azure_call(
                ["az", "vm", "show", "--show-details", "--ids", vm_id],
                args.container,
            )
        )

        self.name = d["name"]
        self.ip = d["publicIps"]
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

    def ssh_call(self, cmds, **kwargs):
        self.communicate()
        self._last_p = p = ssh_call(self.ip, self.args.username, cmds, **kwargs)
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
        "--name",
        default="vmn",
        help="Naming pattern to use for Azure resources. Affects the resource tag and server names",
    )

    # Subparsers
    subparsers = parser.add_subparsers(dest="subparser_name", required=True)
    deploy_parser = subparsers.add_parser(
        "deploy",
        help="Deploy Azure servers and install verificatum",
    )
    start_election_parser = subparsers.add_parser(
        "start",
        help="Start election",
    )
    tally_election_parser = subparsers.add_parser(
        "tally",
        help="Collect and tally election results",
    )
    stop_parser = subparsers.add_parser(
        "stop",
        help="Deallocate Azure servers",
    )

    # Deploy
    deploy_parser.add_argument(
        "--count",
        "-n",
        default=3,
        help="Amount of virtual machines to create",
        metavar="N",
        type=int,
    )
    deploy_parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete existing resources with given tag before creating new ones",
    )
    deploy_parser.add_argument(
        "--ssh-key",
        default="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDpaG3VTq+lsrcWeD4+jdq4lnZGu40WPQN04DOACAkMQsq8PixzZK00UWS9rltGAg64jtnkrsr+omVPfS6979i8ZFG1mEZXTJoc+9T7QRHxWbuMOYiQw07cWJPXsnYAbTqew1IxvB6K4+QMSP20OswrH6EmVTgU1GG9OC/++s5lVaGy6x7gPLofmY4F3jrkMPiSVz9i1cxBNTMDOnQ9lVobbOh3BkCFB75owEX9+R93MfPAp4L4GPII9lUgClYvhaWPZCwfWmPW34MBJB/s+UO//cpYk23AJgZz7dmz9OSjnN/reXmBIHV5nC68NylEH55ZOXR9VYWMKyubmZBpkZe2BN07ZhyY1a1Mz2OUgxieXvIqvH3Um7hujmmh4jmMck6VMLRSud4OxiyAqow+v7J0XyIriSvrcC0o0RTvECDCor/eQnRuQhp8i5N9uKcF1dRSlRRdud1kHgLndPP67tQp+yjCS1E4Uye5O+tBND9G5ReXqQoCMtMHWvMTaX/wmCfeiaPrhwBo7wmXKqmdC3ylaRkYCs6YWPlJrRqQkOaZ1I/tnuD4ElQqAm6fH7z7ybguL5JvKUbOvSbagLUTK+Hf7jGoXU7aQOOODNHKM8kjrnoD0siJTPrd/BiWS0bNruMHacQ/4vJ2YGX218Tnf19fHI7m6kB3/KAwtegqZ5eO3w== Verificatum azure server key",
        help="Public key to use for ssh login",
        metavar="KEY",
    )
    deploy_parser.add_argument(
        "--image",
        default="Canonical:UbuntuServer:18.04-LTS:latest",
        help="The name of the operating system image. See `az vm create --help` for more",
    )
    deploy_parser.add_argument(
        "--size",
        default="Standard_B2s",
        help="The VM size to be created. See `az vm create --help` for more",
    )

    # Deploy / Start
    multi_add_argument(
        (deploy_parser, start_election_parser),
        "--port_http",
        default=8042,
        help="VMN http port",
        metavar="PORT",
        type=int,
    )
    multi_add_argument(
        (deploy_parser, start_election_parser),
        "--port_udp",
        default=4042,
        help="VMN udp port",
        metavar="PORT",
        type=int,
    )

    # Start / Tally
    multi_add_argument(
        (start_election_parser, tally_election_parser),
        "--vote-collecting-server",
        default="https://vmn-webapp.azurewebsites.net/",
        help="Address of vote collecting server where the script POSTs the public key and GETs the ciphertexts",
        dest="server",
    )

    # Tally
    tally_election_parser.add_argument(
        "--file",
        default="plaintexts",
        help="Plaintexts file as produced by vmn",
    )

    # Stop
    stop_parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete resources with given tag instead of just stopping them",
    )

    args = parser.parse_args()
    args.tag = f"project={args.name}"
    return args


def multi_add_argument(parsers, *args, **kwargs):
    for parser in parsers:
        parser.add_argument(*args, **kwargs)


def main(args):
    start_docker(args)

    return globals()[f"{args.subparser_name}_main"](args)


def deploy_main(args):
    if args.delete:
        resources = azure_resources_by_tag(args)
        if resources:
            azure_delete(resources, args.container)

    azure_create_nsg(args)
    names = [args.name + str(idx) for idx in range(1, 1 + args.count)]
    # Create VMs in the background
    for name in names:
        azure_create_vm(name, args)
    # Wait for them to be deployed
    for name in names:
        azure_call(
            ["az", "vm", "wait", "-g", args.group, "--created", "--name", name],
            args.container,
        )
    vms = get_vms(args, start=False)

    with Pool(args.count) as p:
        for res in p.imap_unordered(azure_install_server, vms):
            info(res)

    # TODO: create web app


def start_main(args):
    require_requests()

    vms = get_vms(args)
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
    for vm in vms:
        vm.communicate()

    scp(f"{args.username}@{vms[0].ip}:~/election/publicKey", "publicKey", override=True)

    with open("publicKey", "rb") as f:
        requests.post(
            urljoin(args.server, "publicKey"), files={"publicKey": f}
        ).raise_for_status()
    info(
        f"Public key pushed to {args.server}. Proceed with voting and run this script `tally` command when ready."
    )


def tally_main(args):
    require_requests()

    with open("ciphertexts", "wb") as f:
        r = requests.get(urljoin(args.server, "ciphertexts"))
        r.raise_for_status()
        f.write(r.content)

    # Or, generate the ciphertexts with vmnd:
    # subprocess.run(["vmnd", "-ciphs", "publicKey", "130", "ciphertexts"], check=True)

    vms = get_vms(args, start=False)
    for vm in vms:
        scp("ciphertexts", f"{args.username}@{vm.ip}:~/election/ciphertexts")
        vm.ssh_call(
            [
                "cd ~/election",
                'export _JAVA_OPTIONS="-Djava.net.preferIPv4Stack=true"',
                f"vmn -mix $HOME/election/[0-9]*/privInfo.xml merged.xml ciphertexts plaintexts",
            ]
        )
    for vm in vms:
        vm.communicate()
    scp(
        f"{args.username}@{vms[0].ip}:~/election/plaintexts",
        "plaintexts",
        override=True,
    )

    if not os.path.exists(args.file):
        raise RuntimeError("File not found")
    vbt_json = vbt(args.file)
    print(vbt_json)
    r = requests.post(urljoin(args.server, "results"), json=vbt_json)
    if r.ok:
        return 0

    error(r.status_code, r.text)
    return 1


def require_requests():
    if not requests:
        error("This command is not supported because `requests` is not installed.")
        sys.exit(1)


def get_vms(args, start=True):
    vms = azure_vms_by_tag(args)
    if not vms:
        raise RuntimeError(f"No VMs found with tag `{args.tag}`, did you forget to deploy?")
    if start:
        azure_start(vms, args.container)
    return [
        VirtualMachine(
            vm_id,
            args,
        )
        for vm_id in vms
    ]


def stop_main(args):
    if not args.delete:
        vms = azure_vms_by_tag(args)
        azure_deallocate(vms, args.container)
        return 0

    while True:
        resources = azure_resources_by_tag(args)
        if not resources:
            break
        azure_delete(resources, args.container)


def ssh_call(ip, username, cmds, **kwargs):
    if isinstance(cmds, str):
        cmds = [cmds]
    # kwargs.setdefault("stdout", subprocess.PIPE)
    info("Running ssh commands", cmds)
    return subprocess.Popen(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking no",
            f"{username}@{ip}",
            " && ".join(cmds),
        ],
        **kwargs,
    )


def scp(src, dest, override=False):
    if override:
        try:
            os.unlink(dest)
        except FileNotFoundError:
            pass
    return subprocess.run(["scp", src, dest], check=True)


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

    info("Running azure command", cmd)
    return subprocess.check_output(
        ["docker", "exec", container] + list(cmd), **kwargs
    ).decode()


def azure_create_vm(name, args):
    return azure_call(
        [
            "az",
            "vm",
            "create",
            "--name",
            name,
            "-g",
            args.group,
            "--image",
            args.image,
            "--admin-username",
            args.username,
            "--location",
            "northeurope",
            "--size",
            args.size,
            "--ssh-key-values",
            args.ssh_key,
            "--nsg",
            args.name + "-nsg",
            "--tags",
            args.tag,
            "--storage-sku",
            "Standard_LRS",
            "--verbose",
            "--no-wait",
        ],
        args.container,
    )


def azure_create_nsg(args):
    nsg = args.name + "-nsg"
    azure_call(
        [
            "az",
            "network",
            "nsg",
            "create",
            "--name",
            nsg,
            "-g",
            args.group,
            "--location",
            "northeurope",
            "--tags",
            args.tag,
        ],
        args.container,
    )

    rules = [
        ("vmn-TCP", str(args.port_http), "tcp"),
        ("vmn-UDP", str(args.port_udp), "udp"),
        ("ssh", "22", "tcp"),
    ]
    for idx, (name, port, protocol) in enumerate(rules):
        azure_call(
            [
                "az",
                "network",
                "nsg",
                "rule",
                "create",
                "-g",
                args.group,
                "--nsg-name",
                nsg,
                "--name",
                name,
                "--priority",
                str(111 + idx),
                "--destination-port-ranges",
                port,
                "--access",
                "Allow",
                "--protocol",
                protocol,
            ],
            args.container,
        )


def azure_show_vm(name, args):
    try:
        return azure_call(
            f"az vm show -g {args.group} --name {name}",
            args.container,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def azure_delete(to_delete, container):
    return azure_call(
        ["az", "resource", "delete", "--ids"] + to_delete,
        container,
    )


def azure_start(to_start, container):
    return azure_call(
        ["az", "vm", "start", "--ids"] + to_start,
        container,
    )


def azure_deallocate(to_stop, container):
    return azure_call(
        ["az", "vm", "deallocate", "--ids"] + to_stop,
        container,
    )


def azure_vms_by_tag(args):
    return [
        x
        for x in azure_resources_by_tag(args)
        if ".compute/virtualmachines/" in x.lower()
    ]


def azure_resources_by_tag(args):
    tag = args.tag.strip()
    if not tag:
        raise ValueError("Empty tag")
    tag = shlex.quote(tag)

    return azure_call(
        f"az resource list --tag {tag} -otable --query '[].id' -otsv",
        args.container,
    ).split()


INSTALL_SCRIPT = b"""
#!/bin/bash
set -e
set -x

export DEBIAN_FRONTEND=noninteractive

sudo apt-get update -q
sudo apt-get full-upgrade -y
sudo apt-get install -y \
    tmux vim wget zip \
    build-essential m4 cpp gcc make libtool automake autoconf libgmp-dev openjdk-11-jdk

# Workaround for SSL issue https://askubuntu.com/a/1233456
cat << EOF > ~/ssl.conf
openssl_conf = default_conf

[ default_conf ]

ssl_conf = ssl_sect

[ssl_sect]

system_default = system_default_sect

[system_default_sect]
MinProtocol = TLSv1.2
CipherString = DEFAULT:@SECLEVEL=1
EOF

# https://www.verificatum.org/html/install_vmn.html#ubuntu_18.04.4
# Fetch, build, and install VMN as a single demonstration package.
OPENSSL_CONF="$HOME/ssl.conf" wget https://www.verificatum.org/files/verificatum-vmn-3.0.4-full.tar.gz
tar xvfz verificatum-vmn-3.0.4-full.tar.gz
rm verificatum*.tar.gz
cd verificatum-vmn-3.0.4-full
make install

echo 'done!'
sudo reboot
"""


def azure_install_server(vm):
    p = vm.ssh_call("bash -s", stdin=subprocess.PIPE)
    return p.communicate(input=INSTALL_SCRIPT)


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
