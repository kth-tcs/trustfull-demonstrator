# The e-voting demonstrator of project Trustfull

TODO: one paragraph of context: what's the goal of the demonstrator? what is this?

Code for the demonstrator of the [Trustfull project](trustfull.proj.kth.se/).

This repository contains:

- Under [`webdemo/`](webdemo/) the code for the vote collecting server.
- Under [`scripts/`](scripts/) scripts to orchestrate a demo election from your terminal.

The current version of the web app for e-voting front-end is hosted at <https://vmn-webapp.azurewebsites.net/> (see instructions for updating this URL below).

## Instructions for running an election

Script [`scripts/demo.py`](scripts/demo.py) is used to deploy Verificatum across `N` Azure machines. The script accepts
one positional argument that specifies the command to perform. Full usage is:

```text
usage: demo.py [-h] [--container NAME] [--login] [--username USERNAME]
               [--group GROUP] [--name NAME]
               {deploy,start,tally,stop} ...

positional arguments:
  {deploy,start,tally,stop}
    deploy              Deploy Azure servers and install verificatum
    start               Start election
    tally               Collect and tally election results
    stop                Deallocate Azure servers

optional arguments:
  -h, --help            show this help message and exit
  --container NAME      Logged-in azure-cli docker container. Setup using
                        --login
  --login               Initialize azure-cli container and login
  --username USERNAME   User used to ssh to servers
  --group GROUP         Azure resource group to use
  --name NAME           Naming pattern to use for Azure resources. Affects the
                        resource tag and server names
```

The first time you call the script, you'll need to use the `--login` flag to set up the Azure cli docker container on
your machine. Follow the instructions to log in Azure through the KTH SSO. You will need to use `<username>@ug.kth.se`
as your username.

### Deploying the server-side back-end machines

Use the `deploy` subcommand of [`scripts/demo.py`](scripts/demo.py). Complete usage is:

```text
usage: demo.py deploy [-h] [--count N] [--delete] [--ssh-key KEY]
                      [--image IMAGE] [--size SIZE] [--port_http PORT]
                      [--port_udp PORT]

optional arguments:
  -h, --help        show this help message and exit
  --count N, -n N   Amount of virtual machines to create
  --delete          Delete existing resources with given tag before creating
                    new ones
  --ssh-key KEY     Public key to use for ssh login
  --image IMAGE     The name of the operating system image. See `az vm create
                    --help` for more
  --size SIZE       The VM size to be created. See `az vm create --help` for
                    more
  --port_http PORT  VMN http port
  --port_udp PORT   VMN udp port
```

### Create the front-end web app for the vote collecting server

TODO: document language/libraries/architecture of the front end web-app.
TODO: Do this through `demo.py deploy`

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

TODO document the requirements on the SSH private key, we push the gpg-encrypted private key to the repo, encrypted with all keys at once (only one required for de
<https://www.monperrus.net/martin/martin-monperrus.public.asc>

First, install all requirements with `pip install -r scripts/requirements.txt`.

The subcommand `start` of [`scripts/demo.py`](scripts/demo.py) initializes the voting process across the created Azure servers. Its options are:

```text
usage: demo.py start [-h] [--port_http PORT] [--port_udp PORT]
                     [--vote-collecting-server SERVER]

optional arguments:
  -h, --help            show this help message and exit
  --port_http PORT      VMN http port
  --port_udp PORT       VMN udp port
  --vote-collecting-server SERVER
                        Address of vote collecting server where the script
                        POSTs the public key and GETs the ciphertexts
```

Once the mix network has produced the public key, the script pushes it to the vote collecting server. Once prompted, go
to <https://vmn-webapp.azurewebsites.net/> and proceed with the election.

### Collecting the votes for the tallying

The subcommand `tally` of [`scripts/demo.py`](scripts/demo.py) will first get the ciphertexts from the vote collecting
servers and proceed to upload them to the mix network which will finally jointly decode them. Finally, it will upload
the results to <https://vmn-webapp.azurewebsites.net/results> (by default). Usage:

```text
usage: demo.py tally [-h] [--vote-collecting-server SERVER] [--file FILE]

optional arguments:
  -h, --help            show this help message and exit
  --vote-collecting-server SERVER
                        Address of vote collecting server where the script
                        POSTs the public key and GETs the ciphertexts
  --file FILE           Plaintexts file as produced by vmn
```

TODO: explain how to run the standalone verifier and understand the input/output

### Shutting down all servers

In order to avoid unnecessary charges on Azure, it is important to shut down all servers.

This can be done with the `stop` subcommand of [`scripts/demo.py`](scripts/demo.py). Optionally, the `--delete` flag
can be used to completely delete the resources, including disks and IPs. Usage:

```text
usage: demo.py stop [-h] [--delete]

optional arguments:
  -h, --help  show this help message and exit
  --delete    Delete resources with given tag instead of just stopping them
```

## Diversification of the election code

TODO explain diversification, and link to crow repo and paper

### Diversification of muladd

TODO what is mul_add, how to compile and run it

### Serving diversified muladd in an election

TODO explain and scripts
