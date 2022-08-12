import enum
import logging
import sys
import os
import time
import subprocess

logger = logging.getLogger("server")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class AccessPoint(enum.Enum):
    AP1 = "192.168.10.1"
    AP2 = "192.168.20.1"

    def __init__(self, gateway):
        self.gateway = gateway

    def choose_next_ap_for_handover(self):
        if self == AccessPoint.AP1:
            return AccessPoint.AP2
        elif self == AccessPoint.AP2:
            return AccessPoint.AP1
        return None


def get_current_access_point():
    cmd = "sudo iwgetid -r"
    cmd_output = subprocess.run(cmd, stdout=subprocess.PIPE,
                                shell=True).stdout.decode().strip()
    for ap in AccessPoint:
        if ap.name.lower() == cmd_output:
            return ap
    return None


def perform_handover(selected_access_point=None):
    if selected_access_point is None:
        current_access_point = get_current_access_point()
        if current_access_point is None:
            logger.error("Not connected to an access point. Exiting")
            return False

        new_access_point = current_access_point.choose_next_ap_for_handover()
        if new_access_point is None:
            logger.error(
                "Cannot choose the next access point for the handover. Exiting")
            return False
    else:
        new_access_point = selected_access_point

    # Perform handover. Try multiple times until the connection succeeds.
    attempts = 1
    max_attempts = 5

    logger.info("Performing WiFi handover towards access point {}"
                .format(new_access_point.name.lower()))
    cmd_handover = "sudo nmcli dev wifi connect {} password 1234567890" \
        .format(new_access_point.name.lower())

    while True:
        if attempts > max_attempts:
            logger.error("Impossible to perform the handover")
            return False

        logger.info("Running '{}'".format(cmd_handover))
        cmd_output = subprocess.run(cmd_handover, stdout=subprocess.PIPE,
                                    shell=True).stdout.decode().strip()
        if "error" in cmd_output.lower():
            logger.error("Failed handover attempt {}/5".format(attempts))
            attempts += 1
            time.sleep(1)
        else:
            break

    # Update routing table 100 to force traffic towards the servers via the
    # WiFi interface. This is mandatory considering the current testbed setup
    # (both WiFi and Ethernet interfaces in the same machine, together
    # with Docker taking care of the client application).
    # Routing table 100 is the routing table used to forward packets coming
    # from the docker_handover network (the one used by the client container).
    # Given that, during a handover, the following route is removed from
    # table 100, the forwarding will employ the default routing table
    # (table 254) if table 100 is empty. Then, table 100 must have another
    # default gateway entry (a dummy default gateway) with metric higher than 0,
    # such that the packets generated during handover and directed to the
    # application servers are dropped, at least until the handover is completed.
    # This entry must be set up outside these scripts, and before the beginning
    # of the experiment. Currently, this is done creating a virtual dummy
    # Ethernet interface, with address 192.168.200.1, and executing the
    # command "ip route add default via 192.168.200.1 metric 200 table 100".
    # Thus, here it is enough to add a default route towards the gateway of
    # the access point's subnet, after the handover is completed.
    logger.info("Updating routing table 100")
    cmd_routing = "sudo ip route add default via {} table 100" \
        .format(new_access_point.gateway)
    logger.info("Running '{}'".format(cmd_routing))
    os.system(cmd_routing)

    # Apply traffic control settings.
    logger.info("Applying traffic control settings")
    cmd_tc = "sudo bash ../tc/tc_setup_experiment_5.sh"
    logger.info("Running '{}'".format(cmd_tc))
    os.system(cmd_tc)

    return True
