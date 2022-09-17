sudo tc qdisc del dev wlx742f6809a73b root
sudo tc qdisc add dev wlx742f6809a73b root handle 1: htb

sudo tc class add dev wlx742f6809a73b parent 1: classid 1:1 htb rate 13mbit
sudo tc filter add dev wlx742f6809a73b protocol ip parent 1:0 prio 1 u32 match ip src 192.168.3.0/24 match ip dst 192.168.2.1 match ip dport 6666 0xffff flowid 1:1
sudo tc filter add dev wlx742f6809a73b protocol ip parent 1:0 prio 1 u32 match ip src 192.168.2.0/24 match ip dst 192.168.3.1 match ip dport 6666 0xffff flowid 1:1
sudo tc qdisc add dev wlx742f6809a73b parent 1:1 handle 10: netem delay 119ms

sudo tc class add dev wlx742f6809a73b parent 1: classid 1:2 htb rate 100mbit
sudo tc filter add dev wlx742f6809a73b protocol ip parent 1:0 prio 1 u32 match ip src 192.168.3.0/24 match ip dst 192.168.3.1 match ip dport 6666 0xffff flowid 1:2
sudo tc filter add dev wlx742f6809a73b protocol ip parent 1:0 prio 1 u32 match ip src 192.168.2.0/24 match ip dst 192.168.2.1 match ip dport 6666 0xffff flowid 1:2
sudo tc qdisc add dev wlx742f6809a73b parent 1:2 handle 20: netem delay 15ms