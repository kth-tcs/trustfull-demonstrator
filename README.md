# The e-voting demonstrator of project Trustfull

This is the source code for the demonstrator of the [Trustfull project](trustfull.proj.kth.se/). Its goal is to
showcase the research techniques developed by the members of Trustfull team.

The demonstrator deploys the [Verificatum](https://www.verificatum.org/) mix network on servers distributed on the
Azure cloud platform and includes a vote collecting server front-end where users can vote.

This repository contains:

- Under [`webdemo/`](webdemo/) the code for the vote collecting server.
- Under [`scripts/`](scripts/) scripts to orchestrate a demo election from your terminal.

The current version of the web app for e-voting front-end is hosted at <https://vmn-webapp.azurewebsites.net/> (see instructions for updating this URL below).

## Overview

The general overview of the voting process is as follows:

1. The mix network servers (nodes) are defined, each server runs one instance of verificatum and produces its protocol
   file.
2. The protocol files are shared between all nodes, the mix network jointly produces the public key.
3. The public key is shared with the vote collecting server.
4. Users vote on the vote collecting server, their votes are encrypted on the client side using the public key produced
   at step 3. The vote collecting server never sees a user's unencrypted vote.
5. Once the voting is done, the ciphertexts of the encrypted votes are shared to all nodes. The nodes jointly decrypt
   and shuffle the votes. Once all plaintexts are retrieved, it is impossible to trace a decrypted vote to its original
   voter.
6. The verifier confirms the overall correctness of the execution using the intermediate results.

Steps 1-3 and 5-6 are implemented using the orchestrator script, [`scripts/demo.py`](scripts/demo.py). See the
instructions for running this script below.

Step 4 is implemented by the vote collecting server under [`webdemo/`](webdemo/). This is a python web app which is
based on the [Flask](https://flask.palletsprojects.com/) web framework. The app serves the landing page which uses the
[Verificatum JavaScript Cryptography Library (VJSC)](https://github.com/verificatum/verificatum-vjsc). After a user
selects a candidate and presses the "Vote" button, the `encrypt` function is triggered which encrypts the vote using
VJSC before it is send to the server.

## Instructions for running an election

Script [`scripts/demo.py`](scripts/demo.py) is used to deploy Verificatum across `N` Azure machines. The script accepts
one positional argument that specifies the command to perform.

Before running, install all requirements with `pip install -r scripts/requirements.txt`.

General usage is:

```text
usage: demo.py [-h] [--container NAME] [--login] [--group GROUP] [--name NAME]
               [--username USERNAME] [-i PATH]
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
  --group GROUP         Azure resource group to use
  --name NAME           Naming pattern to use for Azure resources. Affects the
                        resource tag and server names
  --username USERNAME   Username used to ssh / scp to servers
  -i PATH, --identity-file PATH
                        Selects the file from which the identity (private key)
                        for public key authentication is read. This option is
                        directly passed to ssh & scp
```

The first time you call the script, you'll need to use the `--login` flag to set up the Azure cli docker container on
your machine. Follow the instructions to log in Azure through the KTH SSO. You will need to use `<username>@ug.kth.se`
as your username. The user has to be member of a billable resource group (eg the Trustfull resource group "tcs").

### Deploying the server-side back-end machines (~ 10 minutes)

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

The script will need to ssh to the created servers to install all dependencies. To do that, you need the corresponding
private key. There is a gpg-encrypted private key under [`scripts/azure_vmn.gpg`](scripts/azure_vmn.gpg). It can be
decrypted with `gpg --decrypt scripts/azure_vmn.gpg 1>~/.ssh/azure_vmn`. If `ssh-agent` is running it should
automatically authenticate your connection to the servers with the decrypted key. Alternatively, you can use the
`--identity-file` flag to specify the full path to the private key you can use.

You can also [create your own keypair](https://docs.microsoft.com/en-us/azure/virtual-machines/ssh-keys-portal) and
specify its public key with the `--ssh-key` flag.

Once the deployment is completed, you can monitor the mixnet servers (prefixed by `vmn-`) and `vmn-webapp` (GUI to cast vote)
at https://portal.azure.com/.

### Starting the election process

The subcommand `start` of [`scripts/demo.py`](scripts/demo.py) initializes the voting process across the created Azure
servers. This involves booting the servers, creating the verificatum protocol files, producing the public key and
uploading it to the vote collecting server front-end.

Its options are:

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

### Voting

Go to <https://vmn-webapp.azurewebsites.net/> and vote.

Under the hood, each post triggers a POST request to <https://vmn-webapp.azurewebsites.net/> with a payload in application/x-www-form-urlencoded, containing a `field` which is the output a Javascript based encryption:

     field: [[0,0,0,0,2,1,0,0,0,33,0,52,61,1,139,203,21,202,94,135,184,52,213,119,7,110,18,167,185,205,0,213,222,24,58,171,45,3,222,193,237,81,115,1,0,0,0,33,0,25,116,227,230,134,222,141,46,56,77,184,239,173,194,244,173,218,117,218,185,214,173,101,204,244,19,42,156,49,246,59,144],[0,0,0,0,2,1,0,0,0,33,0,220,196,241,58,97,135,3,13,81,131,166,153,143,170,60,171,63,106,225,6,89,187,65,153,31,69,145,171,117,227,103,222,1,0,0,0,33,0,202,156,123,171,138,190,104,52,185,195,121,185,24,42,32,158,27,121,123,94,62,68,170,134,38,159,43,120,215,40,33,252]]



### Collecting the votes for the tallying

The subcommand `tally` of [`scripts/demo.py`](scripts/demo.py) will first get the ciphertexts from the vote collecting
servers and proceed to upload them to the mix network which will finally jointly decode them. Finally, it will upload
the results to <https://vmn-webapp.azurewebsites.net/results> (by default). Usage:

```text
usage: demo.py tally [-h] [--vote-collecting-server SERVER]
                     [--bytetree-parser | --vbt | --skip-plaintexts]
                     [--delete]

optional arguments:
  -h, --help            show this help message and exit
  --vote-collecting-server SERVER
                        Address of vote collecting server where the script
                        POSTs the public key and GETs the ciphertexts
  --bytetree-parser     Use bytetree.py to parse plaintexts. File must be
                        located in directory '../webdemo/' relative to this
                        script's location
  --vbt                 Use `vbt` to parse plaintexts. Must be available in
                        $PATH
  --skip-plaintexts     Do not parse the plaintexts and do not upload them to
                        the results page
  --delete              Delete the most recent session, allows to re-tally
                        without starting a new election
```

`vbt` is needed to parse the plaintexts locally. Follow the installation instructions on <https://www.verificatum.org/>
to compile that program since it's included with [verificatum-vcr](https://github.com/verificatum/verificatum-vcr). The
program is used to parse verificatum's byte tree format and output a JSON representation. Alternatively, the
`--bytetree-parser` flag uses a python port of the needed functionality through the
[`webdemo/bytetree.py`](webdemo/bytetree.py) file.

Example run of `demo.py tally`: <https://gist.github.com/algomaster99/f7529b6dd2304d7ba26b2fafec51690c>

Then, the results can be browsed at <https://vmn-webapp.azurewebsites.net/results>.

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

Automatic software diversification is a moving target defense method in which different, equivalent variants of the
same program are distributed. In the context of the web, it means distributing a different variant at each HTTP
request.

A part of Trustfull's research output is the [SLUMPs](https://github.com/KTH/slumps) project that is concerned with
randomization, fuzzing and superoptimization for WebAssembly. Specifically, the [CROW](http://arxiv.org/pdf/2008.07185)
superdiversifier is responsible for producing diverse, functionally equivalent WebAssembly modules given some C/C++
source code.

### Diversification of muladd

The function `muladd_loop` is a core routine of the Verificatum JavaScript Cryptography Library. It implements a
multiply-add operation with two lists of integers and a scalar using a specific precision. Benchmarks have revealed
that it is one of the more computation-heavy parts of the library.

We have decided to port this function in C code (file [`webdemo/muladd/muladd.c`](webdemo/muladd/muladd.c)) and compile
it to WebAssembly. With the C code, we can use CROW to produce equivalent variants of the function.

#### Compile C version of muladd to WebAssembly

The easiest option is to build the provided docker image that installs [wasi-sdk](https://github.com/WebAssembly/wasi-sdk)
and then use `clang` to compile [`muladd.c`](webdemo/muladd/muladd.c).

```text
cd webdemo/muladd
docker build -t wasi .
docker run -it --rm -u $(id -u ${USER}):$(id -g ${USER}) -v "$PWD:/workdir" -w /workdir wasi muladd.c -c -o muladd.wasm
```

See [CROW's README](https://github.com/KTH/slumps/blob/master/crow/README.md) for instructions on running the
superdiversifier with a C file as input. The output bitcode files can be compiled with the same instruction to
WebAssembly in order to be served from the vote collecting server.

## Local setup

There is also a setup that deploys the entities - GUI, mixnet servers, unverified backend locally. Instead of deploying everything on Azure, we can also deploy all these entities locally.

We follow the steps written in [Verificatum manual page 21](https://www.verificatum.org/files/vmnum-3.1.0.pdf)
to conduct and election.

### Setup
1. Create folder `demoElection` at the root of the project.
2. We have two http servers - auth server and unverified backend. We need to start
  both of them with gunicorn. Run the following command in separate shells.
  1. ```sh
     gunicorn auth.frejaeid.app:app > /tmp/gunicorn.mylogs -b 127.0.0.1:8001
     ```
  2. ```sh
     export AUTH_SERVER_URL=http://127.0.0.1:8001 # URL to auth server
     gunicorn webdemo.app:app > /tmp/gunicorn.mylog
     ```
3. Since auth server needs client and server certificate to interact with FrejaEID,
   make sure there are three files inside `auth/frejaeid/static`.
   1. `freja.crt`: Server SSL certifcate of FrejaEID. Can be downloaded from [here](https://frejaeid.atlassian.net/wiki/spaces/DOC/pages/2162826/REST+API+Documentation).
   2. `kth_client.crt` and `kth_client.key`: Client SSL certificate. Extracted from `kth.pfx`. Contact @monperrus/@algomaster99 to obtain if cannot be found.

### Election process

1. Start the local election by running:
  ```sh
  python3 scripts/local_demo.py --post http://127.0.0.1:8000
  ```

2. Go to `http://127.0.0.1:8000` to cast your vote.
3. Press <kbd>Enter</kbd> to tally and output results to STDOUT. Example result: `Counter({'Yellow Candidate': 1})`
4. Make sure to delete `demoElection` and its contents entirely before restarting the election.

Each step to start the election as said in the manual is a bash command whose STDOUT and STDERR is logged
inside `demoElection` itself. It can be used in case of debugging.
