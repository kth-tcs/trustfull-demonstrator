# The e-voting demonstrator of project Trustfull

TODO: one paragraph of context: what's the goal of the demonstrator? what is this?

Code for the demonstrator of the [Trustfull project](trustfull.proj.kth.se/).

This repository contains:

- Under [`webdemo/`](webdemo/) the code for the vote collecting server.
- Under [`scripts/`](scripts/) scripts to orchestrate a demo election from your terminal.

The current version of the web app for e-voting front-end is hosted at <https://vmn-webapp.azurewebsites.net/> (see instructions for updating this URL below).

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

The script will need to ssh to the created servers to install all dependencies. To do that, you need the corresponding
private key. There is a gpg-encrypted private key under [`scripts/azure_vmn.gpg`](scripts/azure_vmn.gpg). It can be
decrypted with `gpg --decrypt scripts/azure_vmn.gpg 1>~/.ssh/azure_vmn`. If `ssh-agent` is running it should
automatically authenticate your connection to the servers with the decrypted key. Alternatively, you can use the
`--identity-file` flag to specify the full path to the private key you can use.

You can also [create your own keypair](https://docs.microsoft.com/en-us/azure/virtual-machines/ssh-keys-portal) and
specify its public key with the `--ssh-key` flag.

### Starting the election process

TODO: document language/libraries/architecture of the front end web-app.
TODO: one paragraph of context/explanation

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
usage: demo.py tally [-h] [--vote-collecting-server SERVER]
                     [--bytetree-parser | --vbt | --skip-plaintexts]

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
```

`vbt` is needed to parse the plaintexts locally. Follow the installation instructions on <https://www.verificatum.org/>
to compile that program since it's included with [verificatum-vcr](https://github.com/verificatum/verificatum-vcr). The
program is used to parse verificatum's byte tree format and output a JSON representation. Alternatively, the
`--bytetree-parser` flag uses a python port of the needed functionality through the
[`webdemo/bytetree.py`](webdemo/bytetree.py) file.

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
