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
    AP1 = "oem-default-string-1", "192.168.2.1", "192.168.2.0/24"
    AP2 = "oem-default-string-2", "192.168.3.1", "192.168.3.0/24"

    def __init__(self, ssid, gateway, subnet):
        self.ssid = ssid
        self.gateway = gateway
        self.subnet = subnet

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
        if ap.ssid == cmd_output:
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
                .format(new_access_point.ssid))
    cmd_handover = "sudo nmcli dev wifi connect {}"\
        .format(new_access_point.ssid)

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

    other_ap = new_access_point.choose_next_ap_for_handover()
    cmd_route_other_ap = "sudo ip route add {} via {}".format(
        other_ap.subnet, new_access_point.gateway)
    logger.info("Running '{}'".format(cmd_route_other_ap))
    os.system(cmd_route_other_ap)

    # Apply traffic control settings.
    logger.info("Applying traffic control settings")
    cmd_tc = "sudo bash ../tc/tc_setup_experiment_5.sh"
    logger.info("Running '{}'".format(cmd_tc))
    os.system(cmd_tc)

    return True
