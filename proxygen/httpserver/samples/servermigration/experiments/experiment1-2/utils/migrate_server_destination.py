import re
import sys
import json
import os
import subprocess
import logging
from distutils.util import strtobool

logger = logging.getLogger("migrate_server_destination")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def _error():
    logger.error("Something did not work. Exiting")
    sys.exit(1)


def _parse_restore_time(output_file):
    # Get the restore times displayed by the "time" command (real, user, sys)
    # by inspecting the output of the restore command.
    restore_time = []
    try:
        with open(output_file, "r") as restore_output:
            for line in restore_output:
                if "real" in line or "user" in line or "sys" in line:
                    restore_time.append(line.rstrip("\n"))
    except:
        logger.error("Cannot parse the restore time output file")
    return restore_time


def _parse_lazy_pages_measurements(output_file):
    # Get the number of transferred pages by inspecting
    # the output of the lazy pages server command.
    regex_transferred_pages = "\([0-9]+\/[0-9]+\)"  # Matches "(NUMBER/NUMBER)"
    regex_time = "\([0-9]+\.[0-9]+\)"  # Matches "(NUMBER.NUMBER)"

    transfer_start_time = None
    transfer_end_time = None
    n_pages = None
    try:
        with open(output_file, "r") as lazy_pages_output:
            for line in lazy_pages_output:
                if "uffd: Received PID:" in line:
                    result_time = re.search(regex_time, line).group(0)
                    transfer_start_time = float(result_time[1:-1])
                elif "UFFD transferred pages" in line:
                    result_pages = re.search(regex_transferred_pages, line) \
                        .group(0)
                    n_pages = int(result_pages.split("/")[0][1:])

                    result_time = re.search(regex_time, line).group(0)
                    transfer_end_time = float(result_time[1:-1])

        if transfer_start_time is not None and transfer_end_time is not None:
            lazy_pages_transfer_time = transfer_end_time - transfer_start_time
            return n_pages, lazy_pages_transfer_time, transfer_end_time
    except:
        logger.error("Cannot parse the lazy pages output file")
    return None, None, None


def _handle_server_migration(conn, addr, command_socket, management_ip,
                             management_port):
    data = conn.recv(1024)
    if not data:
        logger.error("Received no data")
        _error()

    try:
        msg = json.loads(data)
        if msg.get("action", None) == "shutdown":
            return {}
        if "restore" not in msg:
            logger.error("Unknown request: '{}'".format(msg))
            _error()

        os.system("criu -V")
        try:
            lazy = bool(strtobool(msg["restore"]["lazy"]))
        except:
            lazy = False

        old_cwd = os.getcwd()
        os.chdir(msg["restore"]["path"])

        # The following command is the restore command, which restores
        # the execution of the container at destination.
        restore_output_file = "restore_output.txt"
        cmd = "(time -p runc restore --console-socket {}/console.sock -d " \
              "--image-path {} --work-path {}" \
            .format(msg["restore"]["path"], msg["restore"]["image_path"],
                    msg["restore"]["image_path"], restore_output_file)

        # In case of a post-copy phase in the migration technique, the restore
        # command restores the process without filling out the entire memory
        # contents. When the --lazy-pages option is used, restore rather
        # registers the lazy virtual memory areas (VMAs) with the userfaultfd
        # mechanism. The lazy pages are completely handled by a dedicated
        # lazy-pages daemon. The daemon receives userfault file descriptors
        # from restore via UNIX socket.
        if lazy:
            cmd += " --lazy-pages"

        cmd += " " + msg["restore"]["name"]
        # Use the "tee" command to redirect the output to file.
        # The regular ">" operator does not redirect the output when working
        # with runC base directories in the root folder, due to missing write
        # privileges. Note that the "time" command writes to stderr, so a
        # redirection to stdout is needed.
        cmd += ") 2>&1 | sudo tee {}".format(restore_output_file)

        logger.info("Running '{}'".format(cmd))
        restore_proc = subprocess.Popen(cmd, shell=True)

        # This new command starts the lazy-pages daemon. The daemon monitors the
        # UFFD events and repopulates the tasks address space by requesting lazy
        # pages to the page server running on the source.
        # The daemon tracks and prints the flow of time, and clearly prints when
        # it starts requesting faulted pages and when it finishes, along with an
        # indication of the number of transferred faulted pages.
        # Note that each page is 4KB.
        # Please, read https://criu.org/CLI/opt/--lazy-pages and
        # https://criu.org/Userfaultfd for more information.
        lazy_pages_proc = None
        lazy_pages_output_file = "lazy_pages_output.txt"
        if lazy:
            cmd = "criu lazy-pages --page-server --address {} --port 27 -vv " \
                  "-D {} -W {} 2>&1 | sudo tee {}" \
                .format(addr[0], msg["restore"]["image_path"],
                        msg["restore"]["image_path"], lazy_pages_output_file)
            logger.info("Running lazy-pages server: '{}'".format(cmd))
            lazy_pages_proc = subprocess.Popen(cmd, shell=True)

        ret = restore_proc.wait()
        restore_time = _parse_restore_time(restore_output_file)
        os.remove(restore_output_file)

        if ret == 0:
            reply = "runc restored {} successfully" \
                .format(msg["restore"]["name"])

            # Notify the server about the network switch.
            # Since the server and the script are running on the same
            # machine, there is no need to account for retransmissions.
            switch_command = {"action": "onNetworkSwitch"}
            command_socket.sendto(json.dumps(switch_command).encode(),
                                  (management_ip, management_port))
            logger.info("Sent {} command to {}:{}"
                        .format(json.dumps(switch_command), management_ip,
                                management_port))
        else:
            reply = "runc failed({:d})".format(ret)

        logger.info(reply)
        conn.sendall(reply.encode())
        if ret != 0:
            _error()

        lazy_pages_tx_time = None
        lazy_pages_tx_end_time = None
        n_lazy_pages = None
        if lazy_pages_proc is not None:
            ret = lazy_pages_proc.wait()
            if ret == 0:
                logger.info("Lazy-pages server terminated correctly")
                n_lazy_pages, lazy_pages_tx_time, lazy_pages_tx_end_time = \
                    _parse_lazy_pages_measurements(lazy_pages_output_file)
                os.remove(lazy_pages_output_file)
            else:
                logger.error("Lazy-pages server failed")
                _error()

        os.chdir(old_cwd)
        restore_times = {"restoreTime": restore_time,
                         "lazyPagesTxTime": lazy_pages_tx_time,
                         "lazyPagesTxEndTime": lazy_pages_tx_end_time,
                         "numberOfLazyPages": n_lazy_pages}
        return restore_times
    except Exception as e:
        logger.error("An error occurred: {}".format(e))
        _error()


def wait_for_server_migration(migration_socket, command_socket,
                              management_ip, management_port):
    """
    Wait for and handle a server migration.
    :param migration_socket:  the socket dedicated to server migration.
    :param command_socket     the socket dedicated to send commands to the
                              server management interface.
    :param management_ip      the ip address of the server management interface.
    :param management_port    the listening port of the server management
                              interface.
    :return:                  a dictionary of 4 elements, containing the restore
                              time, the lazy pages transfer time, the lazy pages
                              transfer end time and the number of lazy pages
                              that were transferred. Depending on the chosen
                              technique, the lazy pages quantities could be
                              equal to None.
    """
    logger.info("Waiting for server migration")
    conn, addr = migration_socket.accept()
    with conn:
        logger.info("Connected with {}:{}".format(*addr))
        return _handle_server_migration(conn, addr, command_socket,
                                        management_ip, management_port)
