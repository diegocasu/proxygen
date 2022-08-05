# Commands to reproduce the experiments

## Topology

Three machines, called _client_, _server_source_ and _server_destination_, 
connected by a switch. Suppose that the IP addresses are ```192.168.1.57```,
```192.168.1.104``` and ```192.168.1.105```, respectively. The RTT, bandwidth 
and packet loss of the paths connecting the client to the servers are set up 
using the scripts in ```tc```.

## Experiment 0 (QUIC baseline)

Set up the traffic control running 
```tc/tc_setup_without_loss_experiments_0-3.sh``` or 
```tc/tc_setup_with_loss_experiments_0-2.sh``` on _client_.  
Inside ```quicbaseline```, run:
1. _server_destination_
   ```bash
   sudo python3 server.py --repetitions=100 --rebuild_image
   ```

2. _client_
   ```bash
   sudo python3 client.py --repetitions=100 --rebuild_image
   ```

## Experiment 1

Set up the traffic control running
```tc/tc_setup_without_loss_experiments_0-3.sh``` or
```tc/tc_setup_with_loss_experiments_0-2.sh``` on _client_.  
Inside ```experiment1-2```, run:
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

Set up the traffic control running
```tc/tc_setup_without_loss_experiments_0-3.sh``` or
```tc/tc_setup_with_loss_experiments_0-2.sh``` on _client_.  
Inside ```experiment1-2```, run:
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

Set up the traffic control running 
```tc/tc_setup_without_loss_experiments_0-3.sh``` on _client_.  
Inside ```experiment3```, run:
1. _server_source_ or _server_destination_
   ```bash
   sudo python3 server.py --repetitions=10 --rebuild_image
   ```

2. _client_
   ```bash
   sudo python3 client.py --repetitions=10 --rebuild_image
   ```
   
## Experiment 4

Set up the traffic control running ```tc/tc_setup_without_loss_experiment_4.sh```
or ```tc/tc_setup_with_loss_experiment_4.sh``` on _client_.  
Inside ```experiment4```, run:
1. _server_source_
   ```bash
   sudo python3 server_source.py --destination_ip=192.168.1.105 --disable_rsync_compression --rebuild_image
   ```

2. _server_destination_
   ```bash
   sudo python3 server_destination.py --management_ip=192.168.1.105 --management_port=7777 --rebuild_image
   ```

4. _client_
   ```bash
   sudo python3 client.py --container_migration_script_ip=192.168.1.104 --destination_address=192.168.1.105:6666 --server_ip=192.168.1.104 --management_port=7777 --rebuild_image
   ```