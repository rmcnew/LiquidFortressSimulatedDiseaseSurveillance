# functions to configure and parse script command line arguments
import argparse

from shared.constants import *


def parse_overseer_cmd_line():
    parser = argparse.ArgumentParser()
    parser.add_argument(CONFIG_FILE, help="the simulation configuration file in JSON format")
    parser.add_argument(LOG_POST_URL_ARG, help="log POST URL")
    args = parser.parse_args()
    return args


def parse_node_cmd_line():
    parser = argparse.ArgumentParser()
    parser.add_argument(NODE_ID, help="the node_id to specify the role and parameters of "
                                      "this program as found in the config_file")
    parser.add_argument(CONFIG_FILE, help="the simulation configuration file in JSON format")
    parser.add_argument(LOG_POST_URL_ARG, help="log POST URL")
    parser.add_argument(PUBLIC_IP_ADDRESS_ARG, help="the public IP address to use for AWS EC2 instances")
    args = parser.parse_args()
    return args


def parse_runner_cmd_line():
    parser = argparse.ArgumentParser()
    parser.add_argument(CONFIG_FILE, help="the simulation configuration file in JSON format")
    args = parser.parse_args()
    return args
