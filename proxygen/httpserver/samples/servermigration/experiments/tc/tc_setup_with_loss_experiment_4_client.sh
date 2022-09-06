sudo tc qdisc del dev enp4s0 root
sudo tc qdisc add dev enp4s0 root handle 1: htb

sudo tc class add dev enp4s0 parent 1: classid 1:1 htb rate 100mbit
sudo tc filter add dev enp4s0 protocol ip parent 1:0 prio 1 u32 match ip dst 192.168.1.104 match ip dport 6666 0xffff flowid 1:1
sudo tc qdisc add dev enp4s0 parent 1:1 handle 10: netem delay 122ms loss 1.5%

sudo tc class add dev enp4s0 parent 1: classid 1:2 htb rate 100mbit
sudo tc filter add dev enp4s0 protocol ip parent 1:0 prio 1 u32 match ip dst 192.168.1.105 match ip dport 6666 0xffff flowid 1:2
sudo tc qdisc add dev enp4s0 parent 1:2 handle 20: netem delay 122ms loss 1.5%
