#!/usr/bin/env python3

import json
import os
import subprocess
import sys

CONTAINER = "intelligent_blackburn"
GROUP = "tcs"
PORT_HTTP_START = 25432
PORT_UDP_START = 24321


class VirtualMachine:
    def __init__(self, d):
        self.name = d["name"]
        # self.ip = azure_call(
        #     f"az vm show -d -g {GROUP} -n {self.name} --query publicIps -o tsv"
        # ).strip()
        self.ip = "vmn{idx}.northeurope.cloudapp.azure.com"
        self.idx = None
        self._last_p = None

    def index(self, idx):
        self.idx = idx
        self.ip = self.ip.format(idx=idx + 1)

    def party(self, idx):
        self.idx = idx
        # port_http = PORT_HTTP_START + idx
        port_http = 8042
        # port_udp = PORT_UDP_START + idx
        port_udp = 4042
        # hostname = "localhost"
        hostname = "0.0.0.0"
        # hostname = self.ip
        return f"vmni -party -name party{idx} -http http://{self.ip}:{port_http} -httpl http://{hostname}:{port_http} -hint {self.ip}:{port_udp} -hintl {hostname}:{port_udp} stub.xml -dir {idx}/dir {idx}/privInfo.xml {idx}/protInfo.xml"

    def ssh_call(self, cmds):
        self.communicate()
        self._last_p = p = ssh_call(self.ip, cmds)
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
            f"orestis@{self.ip}:~/election/{self.idx}/protInfo.xml", dest, override=True
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

            scp(fname, f"orestis@{self.ip}:~/election/{idx}/protInfo.xml")


def main():
    subprocess.call(["docker", "start", CONTAINER])
    vms = json.loads(azure_call(f"az vm list -g {GROUP}"))
    vms = [VirtualMachine(vm) for vm in vms if vm.get("name", "").startswith("vmn")]
    n = len(vms)

    for idx, vm in enumerate(vms):
        vm.index(idx)

    prot = f"vmni -prot -sid Session1 -name myElection -nopart {n} -thres {n} stub.xml"
    for idx, vm in enumerate(vms):
        vm.ssh_call(
            [
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

    scp(f"orestis@{vms[0].ip}:~/election/publicKey", "publicKey", override=True)

    input("Waiting for ciphertexts: ")
    # Or, genarate the ciphertexts with vmnd:
    # subprocess.run(["vmnd", "-ciphs", "publicKey", "130", "ciphertexts"], check=True)

    for vm in vms:
        scp("ciphertexts", f"orestis@{vm.ip}:~/election/ciphertexts")
        vm.ssh_call(
            [
                "cd ~/election",
                'export _JAVA_OPTIONS="-Djava.net.preferIPv4Stack=true"',
                f"vmn -mix {vm.idx}/privInfo.xml merged.xml ciphertexts plaintexts",
            ]
        )
    communicate_all(vms)
    scp(f"orestis@{vms[0].ip}:~/election/plaintexts", "plaintexts", override=True)

    return 0


def azure_call(cmd):
    return subprocess.check_output(
        ["docker", "exec", CONTAINER] + cmd.split(" ")
    ).decode()


def ssh_call(ip, cmds):
    if isinstance(cmds, str):
        cmds = [cmds]
    print(cmds)
    return subprocess.Popen(
        ["ssh", "-o", "StrictHostKeyChecking no", f"orestis@{ip}", " && ".join(cmds)],
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
    sys.exit(main())
