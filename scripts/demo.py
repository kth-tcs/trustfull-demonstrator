#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import shutil
import string
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Sequence
from functools import wraps
from itertools import count
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

BYTETREE_PATH = "../webdemo/"


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

    def party(self, idx=None):
        if idx is None:
            idx = self.idx
        else:
            self.idx = idx
        if idx is None:
            raise ValueError("idx is not set")

        hostname = "0.0.0.0"
        http = self.args.port_http
        protocol = "http"
        udp = self.args.port_udp
        return f"vmni -party -name party{idx} -http {protocol}://{self.ip}:{http} -httpl {protocol}://{hostname}:{http} -hint {self.ip}:{udp} -hintl {hostname}:{udp} stub.xml -dir ./dir privInfo.xml {idx}-protInfo.xml"

    def ssh_call(self, cmds, **kwargs):
        self.communicate()
        self._last_p = p = ssh_call(self.ip, cmds, self.args, **kwargs)
        return p

    def communicate(self):
        p = self._last_p
        self._last_p = None
        if p is not None:
            ret = p.communicate()
            return p.returncode, *ret
        return None

    def get_prot_info(self):
        if self.idx is None:
            raise ValueError("No idx")

        self.communicate()

        file = f"{self.idx}-protInfo.xml"
        scp(
            f"{self.args.username}@{self.ip}:~/election/{file}",
            file,
            self.args,
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

            scp(
                fname,
                f"{self.args.username}@{self.ip}:~/election/{fname}",
                self.args,
            )


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
        "--group",
        default="tcs",
        help="Azure resource group to use",
    )
    parser.add_argument(
        "--name",
        default="vmn",
        help="Naming pattern to use for Azure resources. Affects the resource tag and server names",
    )
    parser.add_argument(
        "--username",
        default="vmn",
        help="Username used to ssh / scp to servers",
    )
    parser.add_argument(
        "-i",
        "--identity-file",
        default=None,
        help="Selects the file from which the identity (private key) for public key authentication is read. This option is directly passed to ssh & scp",
        metavar="PATH",
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
        default="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDa/BpNH8q1BYlLFyYGZT0nZxAtHXMUwsjVYkpwKgyFMd7HWVsXw5hRAw/UyqP9OF4bwF+VwMG4uK8fyyI9EKoCjMfYqq1yU0Pcs9uK5sApcuWd2IeIZYZA/biScrG1WqLKpQjESII9Y7Lpu+7RLJT81t2ID2mtqlqCw/m/Ayazf7UxHWq/OqQW7I2W/7B1fQAMkcXE28S0ElrxqDIW8IJOFhhM3HJK4tASL74xkVUE/RIn3a7pxtfJqYQDDX2EN37jalQWEZpG+0MFIO/iX800PR2wl0PhPwU6BgyIKv2Rs6HHnSNF4eXudHqsOKk4YUX4BTxi1iF7/efEfwR2uTEy1r+siZkb/LxttdUN8ASx6F7cW1Wi99h//4vhIWIRj/iUgK2xL3nTOgIFAbBL5mdtVDtM5RornXHiALb7kbaIYEQljV0HaEHOVCdqOiD6zOgD2/doa0/1DFtWzArEpdYCMDADOkZdYTQWgRoAIRE0p2M7goZRUpmlzOkVF7lteec= aman@work",
        help="Public key to use for ssh login",
        metavar="KEY",
    )
    deploy_parser.add_argument(
        "--image",
        default="Canonical:0001-com-ubuntu-server-jammy:22_04-lts:latest",
        help="The name of the operating system image. See `az vm create --help` for more",
    )
    deploy_parser.add_argument(
        "--size",
        default="Standard_B2s",
        help="The VM size to be created. See `az vm create --help` for more",
    )
    deploy_parser.add_argument(
        "--webapp-plan-tier",
        default="F1",
        help="Which pricing tier to use for the webapp plan. See `az appservice plan create --help` for a list",
        metavar="CODE",
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
    g = tally_election_parser.add_mutually_exclusive_group()
    g.add_argument(
        "--bytetree-parser",
        action="store_true",
        help=f"Use bytetree.py to parse plaintexts. File must be located in directory '{BYTETREE_PATH}' relative to this script's location",
        dest="bytetree",
    )
    g.add_argument(
        "--vbt",
        action="store_true",
        dest="vbt",
        help="Use `vbt` to parse plaintexts. Must be available in $PATH",
    )
    g.add_argument(
        "--skip-plaintexts",
        action="store_true",
        help="Do not parse the plaintexts and do not upload them to the results page",
    )

    tally_election_parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the most recent session, allows to re-tally without starting a new election",
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

    virtual_network_name = azure_create_virtual_network(args)

    service_plan_name = azure_create_service_plan(args)
    azure_create_webapp(args, service_plan_name, virtual_network_name)
    azure_create_auth(args, service_plan_name, virtual_network_name)

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


def start_main(args):
    require_requests()

    vms = get_vms(args)
    n = len(vms)

    for idx, vm in enumerate(vms):
        setup_vm(idx, n, vm)
    for vm in vms:
        vm.send_prot_info(n)
    prots = " ".join(f"{idx}-protInfo.xml" for idx in range(n))
    for vm in vms:
        vm.ssh_call(["cd ~/election", f"vmni -merge {prots} merged.xml"])
    for vm in vms:
        vm.ssh_call(
            [
                "cd ~/election",
                'export _JAVA_OPTIONS="-Djava.net.preferIPv4Stack=true"',
                f"vmn -keygen privInfo.xml merged.xml publicKey",
            ]
        )
    for vm in vms:
        vm.communicate()

    scp(
        f"{args.username}@{vms[0].ip}:~/election/publicKey",
        "publicKey",
        args,
        override=True,
    )

    with open("publicKey", "rb") as f:
        requests.post(
            urljoin(args.server, "publicKey"), files={"publicKey": f}
        ).raise_for_status()
    info(
        f"Public key pushed to {args.server}. Proceed with voting and run this script `tally` command when ready."
    )


def retry_subprocess(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        for retries in count():
            try:
                return func(*args, **kwargs)
            except subprocess.CalledProcessError:
                if retries == 3:
                    raise
                info("retrying", func.__name__, retries)
                time.sleep(1)

    return wrapper


@retry_subprocess
def setup_vm(idx, n, vm):
    vm.idx = idx
    prot = f"vmni -prot -sid Session1 -name myElection -nopart {n} -thres {n} stub.xml"

    vm.ssh_call(
        [
            "killall java || true",
            "rm -rf ~/election",
            "mkdir -p ~/election",
            "cd ~/election",
            prot,
            vm.party(),
        ]
    )
    vm.get_prot_info()


def tally_main(args):
    require_requests()
    vbt_call = determine_vbt(args)

    with open("ciphertexts", "wb") as f:
        r = requests.get(urljoin(args.server, "ciphertexts"))
        r.raise_for_status()
        f.write(r.content)

    # Or, generate the ciphertexts with vmnd:
    # subprocess.run(["vmnd", "-ciphs", "publicKey", "130", "ciphertexts"], check=True)

    vms = get_vms(args, start=False)
    vmn_delete = ["vmn -delete -f privInfo.xml merged.xml"] if args.delete else []
    for vm in vms:
        scp("ciphertexts", f"{args.username}@{vm.ip}:~/election/ciphertexts", args)
        vm.ssh_call(
            [
                "cd ~/election",
                'export _JAVA_OPTIONS="-Djava.net.preferIPv4Stack=true"',
                *vmn_delete,
                "vmn -mix privInfo.xml merged.xml ciphertexts plaintexts",
            ]
        )
    for vm in vms:
        vm.communicate()
    scp(
        f"{args.username}@{vms[0].ip}:~/election/plaintexts",
        "plaintexts",
        args,
        override=True,
    )
    assert os.path.exists("plaintexts")

    if vbt_call is not None:
        vbt_json = vbt_count("plaintexts", vbt_call)
        print(vbt_json)
        r = requests.post(urljoin(args.server, "results"), json=vbt_json)
        r.raise_for_status()

    # Verify
    for vm in vms:
        vm.ssh_call(
            [
                "cd ~/election",
                'export _JAVA_OPTIONS="-Djava.net.preferIPv4Stack=true"',
                "rm -rf /tmp/proof",
                "mkdir /tmp/proof",
                "vmnv -sloppy -v -v -e -wd /tmp/proof -a file ~/election/merged.xml $HOME/election/dir/nizkp/default",
            ]
        )
    ret = 0
    for vm in vms:
        code, _, _ = vm.communicate()
        if code != 0:
            error(vm.ip, "proof failed")
            ret = code
    return ret


def require_requests():
    if not requests:
        error("This command is not supported because `requests` is not installed.")
        sys.exit(1)


def determine_vbt(args):
    if args.skip_plaintexts:
        return None

    if args.vbt:
        if not shutil.which("vbt"):
            raise RuntimeError(
                "`vbt` executable not found. Either install it locally (see verificatum.org for instructions) or use the --bytetree-parser or --skip-plaintexts flags."
            )
        return _check_output_vbt

    if args.bytetree:
        return import_bytetree()

    if shutil.which("vbt"):
        args.vbt = True
        return _check_output_vbt

    info("`vbt` executable not found. Falling back to bytetree.py.")
    return import_bytetree()


def import_bytetree():
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), BYTETREE_PATH)
    try:
        sys.path.append(path)
        from bytetree import byte_array_byte_tree_to_json

        def vbt_call(fname):
            with open(fname, "rb") as f:
                return json.loads(byte_array_byte_tree_to_json(bytearray(f.read())))

        return vbt_call
    except ImportError as e:
        error(f"Could not load bytetree.py that should have been located in {path}")
        raise e


def get_vms(args, start=True):
    vms = azure_vms_by_tag(args)
    if not vms:
        raise RuntimeError(
            f"No VMs found with tag `{args.tag}`, did you forget to deploy?"
        )
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


def ssh_call(ip, cmds, args, **kwargs):
    if isinstance(cmds, str):
        cmds = [cmds]
    # kwargs.setdefault("stdout", subprocess.PIPE)
    info("Running ssh commands", cmds)

    identity_file = ["-i", args.identity_file] if args.identity_file else []

    return subprocess.Popen(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking no",
            *identity_file,
            f"{args.username}@{ip}",
            " && ".join(cmds),
        ],
        **kwargs,
    )


def scp(src, dest, args, override=False):
    identity_file = ["-i", args.identity_file] if args.identity_file else []

    if override:
        try:
            os.unlink(dest)
        except FileNotFoundError:
            pass
    return subprocess.run(["scp", *identity_file, src, dest], check=True)


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

def azure_create_virtual_network(args):
    name = f'{args.name}-vn'
    azure_call(
        [
            "az",
            "network",
            "vnet",
            "create",
            "--name",
            name,
            "--resource-group",
            args.group,
            "--subnet-name",
            "default",
            "--tags",
            args.tag,
            "--location",
            "northeurope",
        ],
        args.container
    )

    # azure_call(["az", "network", "vnet", "wait", "-g", args.group, "--created"], args.container)

    return name

def azure_create_service_plan(args):
    service_plan_name = f'{args.name}-plan'
    azure_call(
        [
            "az",
            "appservice",
            "plan",
            "create",
            "--tags",
            args.tag,
            "--sku",
            "B1",
            "--location",
            "northeurope",
            "--is-linux",
            "-g",
            args.group,
            "--name",
            service_plan_name,
        ],
        args.container,
    )
    return service_plan_name


def azure_create_webapp(args, service_plan_name, virtual_network_name):
    name = args.name + "-webapp"

    return azure_call(
        [
            "az",
            "webapp",
            "create",
            "--name",
            name,
            "-g",
            args.group,
            "--tags",
            args.tag,
            "--deployment-source-url",
            "https://github.com/kth-tcs/trustfull-demonstrator/",
            "--runtime",
            "python|3.8",
            "--plan",
            service_plan_name,
            "--startup-file",
            "gunicorn webdemo.app:app > /tmp/gunicorn.mylogs",
            "--vnet",
            virtual_network_name,
            "--subnet",
            "default",
            "--verbose",
        ],
        args.container,
    )

def azure_create_auth(args, service_plan_name, virtual_network_name):
    name = f'aman-auth'

    azure_call(
        [
            "az",
            "webapp",
            "create",
            "--name",
            name,
            "-g",
            args.group,
            "--tags",
            args.tag,
            "--deployment-source-url",
            "https://github.com/kth-tcs/trustfull-demonstrator/",
            "--runtime",
            "python|3.8",
            "--plan",
            service_plan_name,
            "--startup-file",
            "gunicorn auth.frejaeid.app:app > /tmp/gunicorn.mylogs",
            "--verbose",
        ],
        args.container,
    )

    azure_call([
        "az",
        "webapp",
        "config",
        "access-restriction",
        "add",
        "--priority",
        "300",
        "--action",
        "Deny",
        "-g",
        args.group,
        "-n",
        name,
        "--ip-address",
        "0.0.0.0",
    ], args.container)

    azure_call([
        "az",
        "webapp",
        "config",
        "access-restriction",
        "add",
        "--priority",
        "200",
        "--action",
        "Allow",
        "-g",
        args.group,
        "-n",
        name,
        "--vnet-name",
        virtual_network_name,
        "--subnet",
        "default"
    ], args.container)

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

sudo apt update -q
sudo apt upgrade -y
sudo apt autoremove -y
sudo apt install -y \
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

# https://www.verificatum.org/html/install_vmn.html#ubuntu_22.04.1
# Fetch, build, and install VMN as a single demonstration package.
OPENSSL_CONF="$HOME/ssl.conf" wget https://www.verificatum.org/files/verificatum-vmn-3.1.0-full.tar.gz
tar xvfz verificatum-vmn-3.1.0-full.tar.gz
rm verificatum*.tar.gz
cd verificatum-vmn-3.1.0-full
make install

echo 'done!'
sudo reboot
"""


def azure_install_server(vm):
    p = vm.ssh_call("bash -s", stdin=subprocess.PIPE)
    return p.communicate(input=INSTALL_SCRIPT)


def vbt_count(fname, vbt_call):
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
            vbt_call(fname),
        )
    )


def _check_output_vbt(fname):
    # vbt converts the RAW plaintexts to JSON.
    return json.loads(
        # Read output from vbt but discard null bytes
        # See: https://github.com/verificatum/verificatum-vcr/pull/4
        bytes(
            filter(
                bool,
                subprocess.check_output(["vbt", fname]),
            )
        ).decode()
    )


if __name__ == "__main__":
    sys.exit(main(parse_args()))
