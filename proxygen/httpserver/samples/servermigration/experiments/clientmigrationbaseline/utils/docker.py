import logging
import sys
import os
import enum
import subprocess

logger = logging.getLogger("docker")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s.%(msecs)06d %(name)s "
                              "%(levelname)s %(message)s",
                              "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class AppMode(enum.Enum):
    CLIENT = "client"
    SERVER = "server"


class DockerContainerState(enum.Enum):
    CREATED = "created"
    RUNNING = "running"
    RESTARTING = "restarting"
    EXITED = "exited"
    PAUSED = "paused"


def pull_latest_docker_image():
    logger.info("Pulling the latest docker image of diegocasu/mhq")
    cmd = "sudo docker pull diegocasu/mhq"
    logger.info("Running '{}'".format(cmd))

    ret = os.system(cmd)
    if ret != 0:
        logger.error("Impossible to retrieve the docker image. Exiting")
        sys.exit(1)


def create_docker_container(container_name, network, app_mode,
                            config_file, vlog_level):
    logger.info("Creating docker container")
    cmd = "sudo docker container create --name {} --network={} diegocasu/mhq " \
          "--mode={} --config={} ".format(container_name, network,
                                          app_mode.value, config_file)
    if vlog_level > 0:
        cmd += "--v={}".format(vlog_level)
    logger.info("Running '{}'".format(cmd))

    ret = os.system(cmd)
    if ret != 0:
        logger.error("Impossible to create the docker container. Exiting")
        sys.exit(1)


def copy_to_docker_container(container_name, local_path, container_path):
    logger.info("Copying file to docker container")
    cmd = "sudo docker cp {} {}:{}" \
        .format(local_path, container_name, container_path)
    logger.info("Running '{}'".format(cmd))

    ret = os.system(cmd)
    if ret != 0:
        logger.error("Impossible to copy the file. Exiting")
        sys.exit(1)


def copy_from_docker_container(container_name, local_path, container_path):
    logger.info("Copying file from docker container")
    cmd = "sudo docker cp {}:{} {}" \
        .format(container_name, container_path, local_path)
    logger.info("Running '{}'".format(cmd))

    ret = os.system(cmd)
    if ret != 0:
        logger.error("Impossible to copy the file. Exiting")
        sys.exit(1)


def start_docker_container(container_name):
    logger.info("Starting docker container")
    cmd = "sudo docker start {}".format(container_name)
    logger.info("Running '{}'".format(cmd))

    ret = os.system(cmd)
    if ret != 0:
        logger.error("Impossible to start the container. Exiting")
        sys.exit(1)


def kill_docker_container(container_name):
    logger.info("Killing docker container")
    cmd = "sudo docker kill {}".format(container_name)
    logger.info("Running '{}'".format(cmd))

    ret = os.system(cmd)
    if ret != 0:
        logger.error("Impossible to kill the container")


def remove_docker_container(container_name):
    logger.info("Removing docker container")
    cmd = "sudo docker rm {}".format(container_name)
    logger.info("Running '{}'".format(cmd))
    os.system(cmd)

    ret = os.system(cmd)
    if ret != 0:
        logger.error("Impossible to remove the container")


def append_docker_container_logs(container_name, destination_path):
    logger.info("Copying docker output logs")

    # Find the log file.
    cmd = "sudo docker inspect --format='{{.LogPath}}' " + container_name
    cmd_output = subprocess.run(cmd, stdout=subprocess.PIPE,
                                shell=True).stdout.decode()

    # Append the log file to the destination file.
    if not cmd_output.isspace():
        cmd = "sudo cat {} >> {}".format(cmd_output.strip(), destination_path)
        ret = os.system(cmd)
        if ret != 0:
            logger.error("Impossible to copy the logs")


def get_docker_container_state(container_name):
    cmd = "sudo docker inspect -f '{{.State.Status}}' " + container_name
    cmd_output = subprocess.run(cmd, stdout=subprocess.PIPE,
                                shell=True).stdout.decode()
    return DockerContainerState(cmd_output.strip())
