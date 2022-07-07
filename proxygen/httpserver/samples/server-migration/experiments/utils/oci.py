import os
import subprocess
import sys
import json
import enum
import time
import psutil


class AppMode(enum.Enum):
    CLIENT = "client"
    SERVER = "server"


def remove_oci_image_in_working_dir():
    cmd = "sudo rm -rf ./mhq"
    print("Removing OCI image 'mhq' from the current working directory '{}'"
          .format(os.getcwd()))
    print("Running '{}'".format(cmd))
    ret = os.system(cmd)
    if ret != 0:
        print("OCI image not found. Skipping the step")


def remove_oci_bundle_in_runc_dir(runc_base, container_name):
    base_path = os.path.join(runc_base, container_name)
    cmd = "sudo rm -rf " + base_path
    print("Removing OCI bundle '{}' from the runC base directory '{}'"
          .format(container_name, runc_base))
    print("Running '{}'".format(cmd))
    ret = os.system(cmd)
    if ret != 0:
        print("OCI bundle not found. Skipping the step")


def remove_oci_bundle_in_working_dir(container_name):
    cmd = "sudo rm -rf ./" + container_name
    print("Removing OCI bundle '{}' from the current working directory '{}'"
          .format(container_name, os.getcwd()))
    print("Running '{}'".format(cmd))
    ret = os.system(cmd)
    if ret != 0:
        print("OCI bundle not found. Skipping the step")


def generate_oci_bundle(container_name):
    print("Generating the OCI bundle '{}'".format(container_name))

    cmd = "skopeo copy docker://diegocasu/mhq:latest oci:mhq:latest"
    print("Running '{}'".format(cmd))
    ret = os.system(cmd)
    if ret != 0:
        print("Impossible to retrieve the OCI image with skopeo. Exiting")
        sys.exit(1)

    cmd = "sudo umoci unpack --image mhq {} && sudo chmod +xrw {}" \
        .format(container_name, container_name)
    print("Running '{}'".format(cmd))
    ret = os.system(cmd)
    if ret != 0:
        print("Impossible to unpack the OCI image with umoci. Exiting")
        sys.exit(1)


def modify_oci_bundle_config(container_name, app_mode,
                             app_config_container_path,
                             vlog_level):
    print("Modifying the OCI bundle configuration")
    old_cwd = os.getcwd()
    os.chdir(container_name)

    with open("config.json", "r") as oci_bundle_config_file:
        oci_config = json.load(oci_bundle_config_file)

    # Let the container work in host networking mode.
    oci_config["linux"]["namespaces"].remove({"type": "network"})

    # Add command line arguments for the container.
    oci_config["process"]["args"].append("--mode={}".format(app_mode.value))
    oci_config["process"]["args"].append(
        "--config={}".format(app_config_container_path))
    if vlog_level > 0:
        oci_config["process"]["args"].append("--v={}".format(vlog_level))

    with open("config.json", "w") as oci_bundle_config_file:
        json.dump(oci_config, oci_bundle_config_file, indent=4)

    os.chdir(old_cwd)


def move_oci_bundle_to_runc_dir(runc_base, container_name):
    cmd = "sudo mkdir -p {} && sudo mv {} {}".format(runc_base, container_name,
                                                     runc_base)
    print("Moving OCI bundle '{}' to '{}'"
          .format(container_name, runc_base))
    print("Running '{}'".format(cmd))
    ret = os.system(cmd)
    if ret != 0:
        print("Impossible to move the OCI bundle to the runC base directory."
              " Exiting")
        sys.exit(1)


def copy_oci_bundle_to_runc_dir(runc_base, container_name):
    cmd = "sudo mkdir -p {} && sudo cp -r {} {}".format(runc_base,
                                                        container_name,
                                                        runc_base)
    print("Copying OCI bundle '{}' to '{}'"
          .format(container_name, runc_base))
    print("Running '{}'".format(cmd))
    ret = os.system(cmd)
    if ret != 0:
        print("Impossible to copy the OCI bundle to the runC base directory."
              " Exiting")
        sys.exit(1)


def start_container(runc_base, container_name, console_socket_file=None,
                    detached=False):
    bundle_path = os.path.join(runc_base, container_name)
    cmd = "sudo runc run -b {} ".format(bundle_path)

    if console_socket_file is not None:
        cmd += "--console-socket {} ".format(
            os.path.abspath(console_socket_file))
    if detached is True:
        cmd += "-d "

    cmd += container_name

    print("Starting the container '{}'".format(container_name))
    print("Running '{}'".format(cmd))
    ret = os.system(cmd)
    if ret != 0:
        print("Impossible to start the container '{}'. Exiting"
              .format(container_name))
        sys.exit(1)


def start_console_socket(console_socket_file, suppress_output):
    cmd = "sudo recvtty "
    if suppress_output is True:
        cmd += "-m null "
    cmd += console_socket_file

    print("Starting the console socket")
    print("Running '{}'".format(cmd))
    proc = subprocess.Popen(cmd, shell=True)

    # Wait until the console socket file has been created.
    while not os.path.exists(console_socket_file):
        time.sleep(0.1)
    return proc


def stop_console_socket(console_socket_proc, console_socket_file):
    print("Checking the status of the console socket", console_socket_file)

    try:
        console_socket_proc.wait(timeout=0)
        print("Console socket already stopped")
    except:
        print("Console socket is still running. Stopping it")
        process = psutil.Process(console_socket_proc.pid)
        for child in process.children(recursive=True):
            child.kill()
        process.kill()

    cmd = "sudo rm " + console_socket_file
    print("Removing", console_socket_file)
    print("Running '{}'".format(cmd))

    ret = os.system(cmd)
    if ret != 0:
        print("Console socket file not found. Skipping the step")
