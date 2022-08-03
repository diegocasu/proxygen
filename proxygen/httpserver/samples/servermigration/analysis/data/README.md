# Commands to reproduce the experiments

## Topology:

Three machines, called _client_, _server_source_ and _server_destination_, 
connected by a switch. Suppose that the IP addresses are ```192.168.1.57```,
```192.168.1.104``` and ```192.168.1.105```, respectively.  
The RTT, bandwidth and packet loss of the paths 
connecting the client to the servers are set up using either the script 
```tc_setup_no_loss.sh``` or ```tc_setup_loss.sh```, so that:
- _client_ can reach _server_source_ with an RTT of 122 ms;
- _client_ can reach _server_destination_ with an RTT of 18 ms.

The ```.sh``` scripts must be executed on _client_ only.

## Experiment 0 (QUIC baseline)

Inside ```servermigration/experiments/quicbaseline```, run:
1. _server_destination_
   ```bash
   sudo python3 server.py --repetitions=100 --rebuild_image
   ```

2. _client_
   ```bash
   sudo python3 client.py --repetitions=100 --rebuild_image
   ```

## Experiment 1

Inside ```servermigration/experiments/experiment1-2```, run:
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

## Experiment 2

Inside ```servermigration/experiments/experiment1-2```, run:
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

## Experiment 3

Inside ```servermigration/experiments/experiment3```, run:
1. _server_source_ or _server_destination_
   ```bash
   sudo python3 server.py --repetitions=10 --rebuild_image
   ```

2. _client_
   ```bash
   sudo python3 client.py --repetitions=10 --rebuild_image
   ```