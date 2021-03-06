# given a simulation configuration file and some AWS credentials via the command line, run a simulation using AWS EC2
import logging
import time
from aws.aws_helper import *
from config.sds_config import get_runner_config
from shared.run import Run


class RunAws(Run):

    def __init__(self, config):
        super(RunAws, self).__init__(config)


def main():
    config = get_runner_config(RUN_AWS)
    logging.basicConfig(format='%(message)s',
                        # filename="{}.log".format(config[ROLE]),
                        level=logging.DEBUG)
    logging.debug(config)

    run_aws = RunAws(config)

    # create EC2 instances for all the nodes needed plus the overseer
    #ec2_instances = create_ec2_instances(len(config[NODES]) + 1)

    # start overseer EC2 instance
    #overseer_instance = ec2_instances[0]
    #overseer_instance.start()

    # start simulation node EC2 instances
    #simulation_node_instances = ec2_instances[1:]
    #start_instances(simulation_node_instances)

    # generate simulation folder name based on simulation config filename, hostname, PID, and start timestamp
    simulation_folder_name = generate_simulation_folder_name(config)

    # the simulation "folder" is just a prefix that is added on the S3 keys
    simulation_folder_prefix = "{}/".format(simulation_folder_name)
    logging.info("Using simulation prefix: {} in S3 bucket: {}".format(simulation_folder_prefix, LFSDS_S3_BUCKET))

    # generate signed POST URLs for log files
    log_post_urls = {}
    for node_id, role in config[NODES].items():
        log_key = "{}{}-{}.log".format(simulation_folder_prefix, role, node_id) 
        logging.debug("Generating log POST URL for key: {}".format(log_key))
        # log_post_url = generate_log_post_url(LFSDS_S3_BUCKET, log_key)
        # log_post_urls[node_id] = log_post_url

    # get overseer EC2 instance IP address
    overseer_ip_address = '100.115.92.2'

    # read in config file and update overseer IP address for in-memory config file
    logging.debug("updating overseering ip address in config file . . .")
    temp_config_filename = update_overseer_ip_address_in_config_file(config, overseer_ip_address, simulation_folder_name)

    # upload updated temp config file to S3 simulation folder
    config_file_key = "{}{}".format(simulation_folder_prefix, SIMULATION_CONFIG_JSON)
    logging.debug("config_file_key is: {}.  Uploading config file to S3".format(config_file_key))
    upload_and_rename_file_to_s3_bucket(LFSDS_S3_BUCKET, temp_config_filename, config_file_key)

    # generate signed URL for config file
    config_url = generate_config_url(LFSDS_S3_BUCKET, config_file_key)
    logging.debug("config url is: {}".format(config_url))

    # start overseer
    overseer_command_line = run_aws.build_overseer_command_line(config_url)
    logging.debug("overseer command line is: {}".format(overseer_command_line))
    
    logging.info("Starting the Overseer . . .")
    run_aws.run_in_own_process(OVERSEER, overseer_command_line)

    # wait until all child processes are started before creating zmq context
    run_aws.connect_to_overseer()

    logging.info("Simulation is starting.  Press Ctrl-C to stop the simulation.")
    # listen for Ctrl-C
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break

    # upon Ctrl-C, send "stop_simulation" message to overseer
    logging.info("\nSending stop_simulation to Overseer . . .")
    run_aws.send_to_overseer(STOP_SIMULATION)
    reply = run_aws.receive_from_overseer()
    logging.debug("Overseer reply: {}".format(reply))

if __name__ == "__main__":
    main()
