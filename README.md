# trustfull-demonstrator

Code for the demonstrator of the Trustfull project

## Instructions

### 1. Create a network security group

In order to allow all ports required by Verificatum, we can create a new "Network Security Group" that specifies the security rules we need.

From Azure's home go to `Create a resource` and search for `network security group`. Type a name and press create it.
![Network Security Group](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/1-1-network-security-group.png)

From the newly created Network Security Group's dashboard, go to `Inbound security rules` and add these rules:

1. The SSH service ![SSH service](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/1-2-ssh.png)
2. Add ports for TCP traffic. This script uses port `8042`. ![TCP
   rule](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/1-3-tcp.png)
3. Add ports for UDP traffic. This script uses port `4042`. ![UDP
   rule](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/1-4-udp.png)

### 2. Create `N` virtual machines

From Azure's home go to `Create a resource` and select `Ubuntu Server` (preferably 18.04).

In the `Basics` tab, under `Administrator account` select `Use existing public key` and paste a public key created with
`ssh-keygen`. Re-use the same public key across all virtual machines.
![Configure public key](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/2-1-public-key.png)

**Important!** make sure that all servers' names start with a unique prefix, e.g. `vmn`.

In the `Networking` tab, make sure to select the network security group.
![Configure network security group](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/2-2-networking-select.png)

After the resource is created, connect via ssh, copy [`install_server.sh`](./scripts/install_server.sh) to the server
and execute it.

Repeat `N` times.

### 3. Create the web app for the vote collecting server

From Azure's home go to `Create a resource` and select `Web App`.

Under the `Runtime stack` select a python 3.x version.

![Web app options](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/3-1-basics.png)

Once the resource is created, go to it's `Configuration` tab and modify the `Startup Command` field with
`gunicorn webdemo.app:app > /tmp/gunicorn.mylogs`.

![Startup command](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/3-2-startup-command.png)

Then, go to it's `Deployment Center` tab and add this repository as the source either via
GitHub or through the `Local Git` option.

![Deployment center](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/3-3-deployment-center.png)

If using the `Local Git` option, copy the given URL and add it as a remote to your local copy of the repo. Finally,
push your copy to that remote and the web app should be up and running. You will be prompted for a password, there is a
username-password pair under the `Local Git credentials` tab. For more options, read
<https://docs.microsoft.com/en-us/azure/app-service/deploy-configure-credentials>.

You should now be able to access the web demo with the `Browse` button from `Overview`.

### 4. Running an election

First, install all requirements with `pip install -r scripts/requirements.txt`.

The script [`scripts/azure-ssh.py`](scripts/azure-ssh.py) orchestrates the voting process across the created Azure servers. Its options are:

```text
usage: azure-ssh.py [-h] [--container NAME] [--login] [--prefix PREFIX]
                    [--username USERNAME] [--group GROUP] [--port_http PORT]
                    [--port_udp PORT] [--server SERVER]

optional arguments:
  -h, --help           show this help message and exit
  --container NAME     Logged-in azure-cli docker container. Setup using
                       --login
  --login              Initialize azure-cli container and login
  --prefix PREFIX      Azure server names start with this prefix string
  --username USERNAME  User used to ssh to servers
  --group GROUP        Azure resource group to use
  --port_http PORT     VMN http port
  --port_udp PORT      VMN udp port
  --server SERVER      Where to POST the public key and GET the ciphertexts
                       from
```

Before running, make sure all servers that start with the `vmn*` (default) prefix, are running.

On the first execution, use the `--login` flag to initialize the docker container used to connect to the Azure services
through the cli.

Once the mix network has produced the public key, the script pushes it to the vote collecting server. Once prompted, go
to <https://vmn-webapp.azurewebsites.net/> and proceed with the election.

Press Enter to continue. The script will first get the ciphertexts from the vote collecting servers and proceed to
upload them to the mix network which will finally jointly decode them.

The plaintexts can be decoded with the script [`scripts/vbt_tally.py`](script/vbt_tally.py) which will also upload the
results to <https://vmn-webapp.azurewebsites.net/results> (by default).

Finally, make sure to shut down `vmn*` servers to avoid unnecessary charges.
