import socket
import sys
import select
import time
import os
import subprocess
import logging
import enum

logger = logging.getLogger("migrate_server_source")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class MigrationTechnique(enum.Enum):
    def __new__(cls, *args, **kwds):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, pre, lazy):
        self.pre = pre
        self.lazy = lazy

    def to_camel_case_string(self):
        tokens = str(self.name).lower().split("_")
        if len(tokens) == 1:
            return tokens[0]
        else:
            return "".join([tokens[0], tokens[1].capitalize()])

    COLD = False, False
    PRE_COPY = True, False
    POST_COPY = False, True
    HYBRID = True, True


def _error():
    logger.error("Something did not work. Exiting")
    sys.exit(1)


def _pre_dump(base_path, container_name):
    # Create the pre-dump, which is done in case of pre-copy and hybrid
    # migrations. The pre-dump contains the entire content of the container
    # virtual memory and is stored in /the parent directory.
    old_cwd = os.getcwd()
    os.chdir(base_path)

    cmd = "time -p runc checkpoint --pre-dump --image-path parent {}" \
        .format(container_name)
    logger.info("Running '{}'".format(cmd))

    start = time.time()
    ret = os.system(cmd)
    end = time.time()
    pre_dump_time = end - start
    logger.info("PRE-DUMP finished after {:.4f} second(s) with return code {:d}"
                .format(pre_dump_time, ret))

    os.chdir(old_cwd)
    if ret != 0:
        _error()
    return pre_dump_time


def _xfer_pre_dump(parent_path, destination_ip, base_path, rsync_opts,
                   rsync_pre_dump_output_file):
    # Transfer the previously created pre-dump using rsync.
    cmd = "du -hs {}".format(parent_path)
    cmd_output = subprocess.run(cmd, stdout=subprocess.PIPE,
                                shell=True).stdout.decode()
    pre_dump_size, _ = cmd_output.split("\t")
    logger.info("PRE-DUMP size: {}".format(pre_dump_size))

    logger.info("Transferring PRE-DUMP to {}".format(destination_ip))
    cmd = "(time -p rsync {} --stats {} {}:{}/) 2>&1 | sudo tee {}" \
        .format(rsync_opts, parent_path, destination_ip, base_path,
                rsync_pre_dump_output_file)
    start = time.time()
    ret = os.system(cmd)
    end = time.time()
    pre_dump_transfer_time = end - start
    logger.info("PRE-DUMP transfer time: {:.4f} seconds"
                .format(pre_dump_transfer_time))

    if ret != 0:
        _error()
    return pre_dump_transfer_time, pre_dump_size


def _real_dump(base_path, container_name, precopy, postcopy):
    # Create the dump and store it in the /image directory. This is done for any
    # migration technique (dump content varies depending on the technique).
    old_cwd = os.getcwd()
    os.chdir(base_path)

    # cmd = 'time -p runc checkpoint --image-path image --leave-running'
    cmd = "time -p runc checkpoint --image-path image"

    if precopy:
        # Pre-dump is present and can be found in the /parent directory.
        cmd += " --parent-path ../parent"
    if postcopy:
        # In this case, the dump procedure does not write memory pages in
        # /image, but starts a page server for later transfer of faulted pages.
        # The page server will read the local memory dump and send memory pages
        # upon request of the lazy-pages daemon running on the destination.
        cmd += " --lazy-pages"
        cmd += " --page-server localhost:27"

        # With the --status-fd option, CRIU writes '\0' to the specified pipe
        # when it has finished with the checkpoint and start of the page server.
        # References: https://criu.org/CLI/opt/--lazy-pages and
        # https://criu.org/CLI/opt/--status-fd
        try:
            os.unlink("/tmp/postcopy-pipe")
        except:
            pass
        os.mkfifo("/tmp/postcopy-pipe")
        cmd += " --status-fd /tmp/postcopy-pipe"

    cmd += " " + container_name
    logger.info("Running '{}'".format(cmd))

    start = time.time()
    proc = subprocess.Popen(cmd, shell=True)
    if postcopy:
        p_pipe = os.open("/tmp/postcopy-pipe", os.O_RDONLY)
        ret = os.read(p_pipe, 1)
        if ret == '\0':
            logger.info("Ready for lazy page transfer")
        ret = 0
    else:
        # When the post-copy phase is not present, wait until the dump ends.
        ret = proc.wait()
    end = time.time()
    dump_time = end - start
    logger.info("DUMP finished after {:.4f} second(s) with return code {:d}"
                .format(dump_time, ret))

    os.chdir(old_cwd)
    if ret != 0:
        _error()
    return dump_time


def _xfer_final(image_path, destination_ip, base_path, rsync_opts,
                rsync_dump_output_file):
    # Transfer the previously created dump using rsync.
    cmd = "du -hs {}".format(image_path)
    cmd_output = subprocess.run(cmd, stdout=subprocess.PIPE,
                                shell=True).stdout.decode()
    dump_size, _ = cmd_output.split("\t")
    logger.info("DUMP size: {}".format(dump_size))

    logger.info("Transferring DUMP to {}".format(destination_ip))
    cmd = "(time -p rsync {} --stats {} {}:{}/) 2>&1 | sudo tee {}" \
        .format(rsync_opts, image_path, destination_ip, base_path,
                rsync_dump_output_file)
    start = time.time()
    ret = os.system(cmd)
    end = time.time()
    dump_transfer_time = end - start
    logger.info("DUMP transfer time: {:.4f} seconds".format(dump_transfer_time))

    if ret != 0:
        _error()
    return dump_transfer_time, dump_size


def parse_rsync_output_files(rsync_pre_dump_output_file, rsync_dump_output_file,
                             migration_times, pre):
    def parse_file(file):
        total_file_size = None
        total_bytes_sent = None
        transfer_rate = None
        compression_speedup = None

        for line in file:
            if "Total transferred file size:" in line:
                total_file_size = line.split(": ")[1].split(" ")[0].rstrip("\n")
            elif "Total bytes sent:" in line:
                total_bytes_sent = line.split(": ")[1].split(" ")[0] \
                    .rstrip("\n")
            elif "bytes/sec" in line:
                transfer_rate = line.split("  ")[2].rstrip("\n")
            elif "speedup" in line:
                compression_speedup = line.split("  ")[1].split(" ")[2] \
                    .rstrip("\n")

        return total_file_size, total_bytes_sent, transfer_rate, \
               compression_speedup

    if pre:
        try:
            with open(rsync_pre_dump_output_file, "r") as pre_dump_output_file:
                migration_times["rsyncPreDumpTotalFileSize"], \
                migration_times["rsyncPreDumpTotalBytesSent"], \
                migration_times["rsyncPreDumpTransferRate"], \
                migration_times["rsyncPreDumpCompressionSpeedup"] = \
                    parse_file(pre_dump_output_file)
        except:
            logger.error("Cannot parse the rsync pre-dump output file")
            migration_times["rsyncPreDumpTotalFileSize"], \
            migration_times["rsyncPreDumpTotalBytesSent"], \
            migration_times["rsyncPreDumpTransferRate"], \
            migration_times["rsyncPreDumpCompressionSpeedup"] = \
                None, None, None, None
    try:
        with open(rsync_dump_output_file, "r") as dump_output_file:
            migration_times["rsyncDumpTotalFileSize"], \
            migration_times["rsyncDumpTotalBytesSent"], \
            migration_times["rsyncDumpTransferRate"], \
            migration_times["rsyncDumpCompressionSpeedup"] = \
                parse_file(dump_output_file)
    except:
        logger.error("Cannot parse the rsync dump output file")
        migration_times["rsyncDumpTotalFileSize"], \
        migration_times["rsyncDumpTotalBytesSent"], \
        migration_times["rsyncDumpTransferRate"], \
        migration_times["rsyncDumpCompressionSpeedup"] = None, None, None, None


def _migrate(container_name, destination_ip, pre, lazy, base_path, rsync_opts):
    image_path = base_path + "/image"
    parent_path = base_path + "/parent"
    rsync_pre_dump_output_file = "rsync_pre_dump_output.txt"
    rsync_dump_output_file = "rsync_dump_output.txt"

    migration_times = {"preDumpTime": None, "preDumpTxTime": None,
                       "dumpTime": None, "dumpTxTime": None,
                       "dumpSize": None, "preDumpSize": None,
                       "rsyncPreDumpTotalFileSize": None,
                       "rsyncPreDumpTotalBytesSent": None,
                       "rsyncPreDumpTransferRate": None,
                       "rsyncPreDumpCompressionSpeedup": None,
                       "rsyncDumpTotalFileSize": None,
                       "rsyncDumpTotalBytesSent": None,
                       "rsyncDumpTransferRate": None,
                       "rsyncDumpCompressionSpeedup": None}

    if pre:
        migration_times["preDumpTime"] = _pre_dump(base_path, container_name)
        migration_times["preDumpTxTime"], migration_times["preDumpSize"] = \
            _xfer_pre_dump(parent_path, destination_ip, base_path, rsync_opts,
                           rsync_pre_dump_output_file)

    migration_times["dumpTime"] = _real_dump(base_path, container_name,
                                             pre, lazy)
    migration_times["dumpTxTime"], migration_times["dumpSize"] = \
        _xfer_final(image_path, destination_ip, base_path, rsync_opts,
                    rsync_dump_output_file)

    # Connect to the migration server running on
    # the destination to send the restore command.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((destination_ip, 18863))

    restore_cmd = '{{ "restore" : {{ "path" : "{}", "name" : "{}", ' \
                  '"image_path" : "{}" , "lazy" : "{}" }} }}' \
        .format(base_path, container_name, image_path, str(lazy))
    sock.send(restore_cmd.encode())

    read_list = [sock, sys.stdin]

    while True:
        input_ready, output_ready, except_ready = select.select(read_list, [],
                                                                [], 10)
        # If after 10 seconds there is nothing to read, then exit.
        if not input_ready:
            return None

        for s in input_ready:
            answer = s.recv(1024)
            decoded_answer = answer.decode()
            logger.info(decoded_answer)
            if "failed" in decoded_answer:
                _error()

        parse_rsync_output_files(rsync_pre_dump_output_file,
                                 rsync_dump_output_file, migration_times, pre)
        if pre:
            os.remove(rsync_pre_dump_output_file)
        os.remove(rsync_dump_output_file)

        return migration_times


def start_migration(runc_base, container_name, destination_ip, pre, lazy,
                    enable_compression):
    """
    Start container migration towards a destination machine.
    Use of pre/lazy flag to choose the migration technique:
    1) Cold = False False
    2) Pre-copy = True False
    3) Post-copy = False True
    4) Hybrid = True True
    :param runc_base:           the path to the runC base directory.
    :param container_name:      the name of the container to migrate, which
                                must also coincide with the name of the
                                associated OCI bundle.
    :param destination_ip:      the IP address of the destination machine.
    :param pre:                 flag used to determine the migration technique
    :param lazy:                flag used to determine the migration technique
    :param enable_compression:  True if rsync compression must be enabled,
                                False otherwise.
    :return:                    a dictionary of 14 elements, containing the
                                pre-dump time, the pre-dump transfer time, the
                                dump time, the dump transfer time, the dump size,
                                the pre-dump size and statistics associated to
                                the rsync transfer.
                                Depending on the chosen technique, the pre-dump
                                elements could be equal to None.
    """
    logger.info("Starting server migration")
    base_path = runc_base + container_name

    # "-h" outputs numbers in human readable format.
    # "-a" enables archive mode, which preserves permissions, ownership, and
    # modification times, among other things.
    # "-z" enables compression during transfer.
    rsync_opts = "-ha"
    if enable_compression:
        rsync_opts += "z"

    return _migrate(container_name, destination_ip, pre, lazy, base_path,
                    rsync_opts)
