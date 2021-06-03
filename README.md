# The e-voting demonstrator of project Trustfull

TODO: one paragraph of context: what's the goal of the demonstrator? what is this?

Code for the demonstrator of the [Trustfull project](trustfull.proj.kth.se/).

This repository contains:
- Under [`webdemo/`](webdemo/) the code for the vote collecting server.
- Under [`scripts/`](scripts/) scripts to orchestrate a demo election from your terminal.

The current version of the web app for e-voting front-end is hosted at <https://vmn-webapp.azurewebsites.net/> (see instructions for updating this URL below).

## Instructions for running an election

### Deploying the server-side back-end machines

#### 1. Create a network security group

In order to allow all ports required by Verificatum, we can create a new "Network Security Group" that specifies the security rules we need.

From Azure's home go to `Create a resource` and search for `network security group`. Type a name and press create it.
![Network Security Group](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/1-1-network-security-group.png)

From the newly created Network Security Group's dashboard, go to `Inbound security rules` and add these rules:

1. The SSH service ![SSH service](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/1-2-ssh.png)
2. Add ports for TCP traffic. This script uses port `8042`. ![TCP
   rule](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/1-3-tcp.png)
3. Add ports for UDP traffic. This script uses port `4042`. ![UDP
   rule](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/1-4-udp.png)

#### 2. Create N virtual machines

TODO write and document a script for "Repeat `N` times."

From Azure's home go to `Create a resource` and select `Ubuntu Server` (preferably 18.04).

In the `Basics` tab, under `Administrator account` select `Use existing public key` and paste a public key created with
`ssh-keygen`. Re-use the same public key across all virtual machines.
![Configure public key](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/2-1-public-key.png)

**Important!** make sure that all servers' names start with a unique prefix, e.g. `vmn`.

In the `Networking` tab, make sure to select the network security group.
![Configure network security group](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/2-2-networking-select.png)

#### 3. Download and Compile Verificatum

TODO: explain what the script does, explain the requirements on the machine (apt-get/docker) to do that.

After the resource is created, connect via ssh, copy [`install_server.sh`](./scripts/install_server.sh) to the server
and execute it.

### Create the front-end web app for the vote collecting server

TODO: document language/libraries/architecture of the front end web-app.

From Azure's home go to `Create a resource` and select `Web App`.

Under the `Runtime stack` select a python 3.x version.

![Web app options](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/3-1-basics.png)

Once the resource is created, go to it's `Configuration` tab and modify the `Startup Command` field with
`gunicorn webdemo.app:app > /tmp/gunicorn.mylogs`.

![Startup command](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/3-2-startup-command.png)

Now the vote collecting server is up and running.

#### Deploying or Updating the frontend code running on Azure

Then, go to its `Deployment Center` tab and add this repository as the source via
the `Local Git` option in Azure.

![Deployment center](https://raw.githubusercontent.com/kth-tcs/trustfull-demonstrator/media/3-3-deployment-center.png)

When using the `Local Git` option, copy the given URL and add it as a remote to your local copy of the repo. Finally,
push your copy to that remote and the web app at <https://vmn-webapp.azurewebsites.net/> should be up / updated. You will be prompted for a password, there is a
username-password pair under the `Local Git credentials` tab. For more options, read
<https://docs.microsoft.com/en-us/azure/app-service/deploy-configure-credentials>.

### Deploying the mixnet, spawning the mixnet node JVMs

TODO: one paragraph of context/explanation

TODO explain that we have to call "azure-ssh.py --login" (or explicit error message)

TODO document Azure/SSO xxx@ug.kth.se

TODO document the requirements on the SSH private key, we push the gpg-encrypted private key to the repo, encrypted with all keys at once (only one required for de
<https://www.monperrus.net/martin/martin-monperrus.public.asc>

First, install all requirements with `pip install -r scripts/requirements.txt`.

The script [`scripts/azure-ssh.py`](scripts/azure-ssh.py) orchestrates the voting process across the created Azure servers. Its options are:

TODO split and rename script, see <https://github.com/kth-tcs/trustfull-demonstrator/issues/1>

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
  --server SERVER      The vote collecting server where to POST the public key and GET the ciphertexts
                       from (domain name or IP address)
```

Before running, make sure all servers that start with the `vmn*` (default) prefix, are running.

On the first execution, use the `--login` flag to initialize the docker container used to connect to the Azure services
through the cli.

Once the mix network has produced the public key, the script pushes it to the vote collecting server. Once prompted, go
to <https://vmn-webapp.azurewebsites.net/> and proceed with the election.

### Collecting the votes for the tallying

TODO merge scripts `tally-election-on-azure.py` and `scripts/vbt_tally.py` and update doc

The script `tally-election-on-azure.py` will first get the ciphertexts from the vote collecting servers and proceed to
upload them to the mix network which will finally jointly decode them.

The plaintexts can be decoded with the script [`scripts/vbt_tally.py`](script/vbt_tally.py) which will also upload the
results to <https://vmn-webapp.azurewebsites.net/results> (by default).

TODO: explain how to run the standalone verifier and understand the input/output

### Shutting down all servers

TODO

In order to avoid unnecessary charges on Azure, it is important to shut down all servers.

This can be done with script XXXXX which shuts down `vmn*` servers.

## Diversification of the election code

TODO explain diversification, and link to crow repo and paper

### Diversification of muladd

TODO what is mul_add, how to compile and run it

### Serving diversified muladd in an election

TODO explain and scripts
