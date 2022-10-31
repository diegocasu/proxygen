## Overview

The repository contains the synthetic application, the experiment results, and 
the analysis scripts used to carry out the performance evaluation reported in
[_Extending mvfst to support enhanced server-side migration in QUIC: protocol
design and performance
evaluation_](https://etd.adm.unipi.it/theses/available/etd-09062022-144126), a
thesis for the Master of Science in Computer Engineering at the University of
Pisa.

The performance evaluation is focused on the experimental implementation of QUIC 
server migration available
[here](https://github.com/diegocasu/mvfst/tree/server-migration).

The experiments leverage containerized endpoints spawned
by [`runC`](https://github.com/opencontainers/runc), and implement container
migration exploiting [`CRIU`](https://github.com/checkpoint-restore/criu).
Extensive details about the software support, the testbed, the experiment layout
and the results are available in the thesis.

## Repository layout

All the material is inside `proxygen/httpserver/samples/servermigration/`,
where:

- `analysis` contains the experiment results in CSV format, together with the
  scripts to parse and plot them;
- `app` contains the synthetic application used to collect the data;
- `experiments` contains the scripts used to perform the experiments;
- `image` contains a Dockerfile to easily build an application image that can be
  converted to an OCI bundle.

## Build the application

To build the application fetching the `mvfst` version supporting server
migration, run:

```bash
./build.sh --with-quic
```

The resulting executable is called `mhq` and can be found in
`proxygen/_build/proxygen/httpserver`.

Alternatively, an image of the application can be retrieved from the
[Docker Hub](https://hub.docker.com/r/diegocasu/mhq)

```bash
docker pull diegocasu/mhq
```

or directly built using Docker:

```bash
cd proxygen/httpserver/samples/servermigration/image
docker build .
```

Starting from the Docker image, it is possible to obtain a corresponding OCI
bundle using [skopeo](https://github.com/containers/skopeo) and
[umoci](https://github.com/opencontainers/umoci). If you are trying to run the
experiment scripts, fetching and conversion are done automatically, so there is
no need to manually build the application (except for experiment 5 and 6).

## Launch the application

The application is launched passing two command line parameters:

- `--mode`, specifying if the endpoint is going to run as `client` or `server`;
- `--config`, specifying the path of the JSON file containing the configuration
(possible options are listed in 
`proxygen/httpserver/samples/servermigration/app/clientconfig.json` and 
`proxygen/httpserver/samples/servermigration/app/serverconfig.json`). 

For instance, run:

```bash
./mhq --mode=server --config=./serverconfig.json
```

## Reproduce the experiments

The scripts inside `experiments` automatically manage the container life cycle, 
run the required steps, and collect the results. They assume that `skopeo`, 
`umoci`, `runc`, and `criu` are installed and added to the PATH variable. In
particular, the first two are required to pull and convert the application image
from Docker Hub.

The testbed configuration is reported in the thesis and requires ```tc``` to
simulate RTT, bandwidth, and packet loss of paths. In the following commands, it
is supposed that the IP addresses of _client_, _server_source_, and
_server_destination_ are ```192.168.1.57```, ```192.168.1.104``` and
```192.168.1.105```, respectively.

### Experiment 0 (QUIC baseline)

Set up traffic control:

- to remove packet loss, run 
```experiments/tc/tc_setup_without_loss_experiments_0-3.sh``` on _client_;
- to add packet loss, run 
```experiments/tc/tc_setup_with_loss_experiments_0-2_client.sh``` on _client_ 
and ```experiments/tc/tc_setup_with_loss_experiments_0-2_server.sh``` on 
_server_destination_.

Inside ```experiments/quicbaseline```, run:

1. _server_destination_
   ```bash
   sudo python3 server.py --repetitions=100 --rebuild_image
   ```

2. _client_
   ```bash
   sudo python3 client.py --repetitions=100 --rebuild_image
   ```

### Experiment 1

Set up traffic control:

- to remove packet loss, run
```experiments/tc/tc_setup_without_loss_experiments_0-3.sh``` on _client_;
- to add packet loss, run
```experiments/tc/tc_setup_with_loss_experiments_0-2_client.sh``` on _client_ 
and ```experiments/tc/tc_setup_with_loss_experiments_0-2_server.sh``` on both 
_server_source_ and _server_destination_. 

- Inside ```experiments/experiment1-2```, run:

1. _server_source_
   ```bash
   sudo python3 server_source.py --experiment=1 --destination_ip=192.168.1.105 --disable_rsync_compression --repetitions=100 --rebuild_image
   ```

2. _server_destination_
   ```bash
   sudo python3 server_destination.py --experiment=1 --management_ip=192.168.1.105 --management_port=7777 --repetitions=100 --rebuild_image
   ```

3. _client_
   ```bash
   sudo python3 client.py --experiment=1 --repetitions=100 --rebuild_image
   ```

### Experiment 2

Set up traffic control:

- to remove packet loss, run
```experiments/tc/tc_setup_without_loss_experiments_0-3.sh``` on _client_;
- to add packet loss, run
```experiments/tc/tc_setup_with_loss_experiments_0-2_client.sh``` on _client_ 
and ```experiments/tc/tc_setup_with_loss_experiments_0-2_server.sh``` on both
_server_source_ and _server_destination_.

Inside ```experiments/experiment1-2```, run:

1. _server_source_
   ```bash
   sudo python3 server_source.py --experiment=2 --destination_ip=192.168.1.105 --disable_rsync_compression --repetitions=10 --rebuild_image
   ```

2. _server_destination_
   ```bash
   sudo python3 server_destination.py --experiment=2 --management_ip=192.168.1.105 --management_port=7777 --repetitions=10 --rebuild_image
   ```

3. _client_
   ```bash
   sudo python3 client.py --experiment=2 --repetitions=10 --rebuild_image
   ```

To obtain the results with compression enabled, just change the flag
```--disable_rsync_compression``` with ```--enable_rsync_compression```.

### Experiment 3

Set up traffic control running
```experiments/tc/tc_setup_without_loss_experiments_0-3.sh``` on _client_.
Inside ```experiments/experiment3```, run:

1. _server_source_ or _server_destination_
   ```bash
   sudo python3 server.py --repetitions=10 --rebuild_image
   ```

2. _client_
   ```bash
   sudo python3 client.py --repetitions=10 --rebuild_image
   ```

### Experiment 4

Set up traffic control:

- to remove packet loss, run
```experiments/tc/tc_setup_without_loss_experiment_4.sh``` on _client_;
- to add packet loss, run
```experiments/tc/tc_setup_with_loss_experiment_4_client.sh``` on _client_ and
```experiments/tc/tc_setup_with_loss_experiment_4_server.sh``` on both
_server_source_ and _server_destination_.

Inside ```experiments/experiment4```, run:

1. _server_source_
   ```bash
   sudo python3 server_source.py --destination_ip=192.168.1.105 --disable_rsync_compression --rebuild_image
   ```

2. _server_destination_
   ```bash
   sudo python3 server_destination.py --management_ip=192.168.1.105 --management_port=7777 --rebuild_image
   ```

3. _client_
   ```bash
   sudo python3 client.py --container_migration_script_ip=192.168.1.104 --destination_address=192.168.1.105:6666 --server_ip=192.168.1.104 --management_port=7777 --rebuild_image
   ```

### Experiment 5

This experiment employs a normal client, not a containerized one: as such, it 
expects to find a plain ```mhq``` executable in 
```experiments/experiment5/proxygen/proxygen/_build/proxygen/httpserver/``` on
the _client_ machine. Moreover, it uses ```nmcli``` for Wi-Fi handovers and 
assumes that access points are named/addressed in a certain way.
Thus, you should look at the code and possibly modify it for your system.

Set up traffic control running ```experiments/tc/tc_setup_experiment_5.sh```
on _client_. Inside ```experiments/experiment5```, run:

1. _server_source_
   ```bash
   sudo python3 server.py --disable_rsync_compression --first_role=source --management_port=7777 --other_server_ip=192.168.1.105 --repetitions=1 --rebuild_image
   ```

2. _server_destination_
   ```bash
   sudo python3 server.py --disable_rsync_compression --first_role=destination --management_port=7777 --other_server_ip=192.168.1.104--repetitions=1 --rebuild_image
   ```
   
3. _client_
   ```bash
   sudo python3 client.py --initial_access_point=ap1 --server_app_port=6666 --server_management_port=7777 --first_server_ip_eth=192.168.1.104 --second_server_ip_eth=192.168.1.105 --first_server_ip_wifi=192.168.2.1 --second_server_ip_wifi=192.168.3.1 --repetitions=1
   ```

### Experiment 6 (Client migration baseline)

This experiment employs a normal client too, this time requiring a plain 
```mhq``` executable in
```experiments/experiment6/proxygen/proxygen/_build/proxygen/httpserver/``` 
on the _client_ machine. The same considerations reported in experiment 5
regarding Wi-Fi handovers are valid for experiment 6.

Set up traffic control running ```experiments/tc/tc_setup_experiment_6.sh```
on _client_. Inside ```experiments/experiment6```, run:

1. _server_source_
   ```bash
   sudo python3 server.py --repetitions=1 --rebuild_image
   ```

2. _client_
   ```bash
   sudo python3 client.py --initial_access_point=ap1 --server_management_port=7777 --server_ip_eth=192.168.1.104 --repetitions=1
   ```

## Plot the results

Simply run the script corresponding to the experiment, for instance:

```
cd proxygen/httpserver/samples/servermigration/analysis
python3 experiment1.py
```

Required libraries are listed in `analysis/requirements.txt`, while data are
automatically parsed from the CSV files located in `analysis/data`. Note that
the results of experiment 4 are zipped due to their dimension, so they must be
unzipped before starting the relative script.