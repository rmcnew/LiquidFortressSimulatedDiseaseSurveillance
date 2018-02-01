# helper functions for all node types:  electronic_medical_record, health_district_system, and disease_outbreak_analyzer
import json
import logging
import socket
from datetime import datetime

import zmq

from vector_timestamp import VectorTimestamp


class Node:

    def __init__(self, config):
        self.config = config
        self.node_id = config['node_id']
        self.time_scaling_factor = config['time_scaling_factor']
        self.role = config['role']
        self.role_parameters = config['role_parameters']
        self.diseases = config['diseases']
        self.simulation_start_time = None
        self.node_addresses = None
        self.vector_timestamp = VectorTimestamp()
        self.context = zmq.Context()
        self.poller = None
        self.overseer_request_socket = self.context.socket(zmq.REQ)
        overseer_host = config['overseer_host']
        overseer_reply_port = str(config['overseer_reply_port'])
        overseer_publish_port = str(config['overseer_publish_port'])
        self.overseer_request_socket.connect("tcp://{}:{}".format(overseer_host, overseer_reply_port))
        self.overseer_subscribe_socket = self.context.socket(zmq.SUB)
        self.overseer_subscribe_socket.connect("tcp://{}:{}".format(overseer_host, overseer_publish_port))
        # empty string filter => receive all messages
        self.overseer_subscribe_socket.setsockopt_string(zmq.SUBSCRIBE, '')

    def shutdown_zmq(self):
        self.overseer_request_socket.close(linger=2)
        self.overseer_subscribe_socket.close(linger=2)
        self.context.term()

    def send_to_overseer(self, message):
        logging.info("Sending message: \'" + message + "\' from: \'" + self.node_id + "\'")
        encoded_node_id = self.node_id.encode()
        encoded_message = message.encode()
        self.overseer_request_socket.send_multipart([encoded_node_id, encoded_message])

    def receive_from_overseer(self):
        while True:
            [encoded_destination_node_id, encoded_reply] = self.overseer_request_socket.recv_multipart()
            destination_node_id = encoded_destination_node_id.decode()
            reply = encoded_reply.decode()
            if self.node_id == destination_node_id:
                return reply

    def receive_subscription_message(self):
        message = self.overseer_subscribe_socket.recv_string()
        return message

    def register(self):
        logging.info(str(self.node_id) + " registering with overseer")
        address_map = self.config['address_map']
        address_map['type'] = 'address_map'
        serialized_address_map = json.dumps(address_map)
        self.send_to_overseer(serialized_address_map)
        reply = self.receive_from_overseer()
        logging.info(reply)

    def receive_node_addresses(self):
        json_node_addresses = self.receive_subscription_message()
        self.node_addresses = json.loads(json_node_addresses)
        logging.debug("node_addresses received from overseer: {}".format(self.node_addresses))

    def send_ready_to_start(self):
        message = "ready_to_start"  # the overseer checks this string for a match
        self.send_to_overseer(message)
        reply = self.receive_from_overseer()
        logging.info(reply)

    def await_start_simulation(self):
        continue_to_wait = True
        while continue_to_wait:
            message = self.receive_subscription_message()
            if message == "start_simulation":
                continue_to_wait = False
            else:
                logging.warning("received message: '" + message + "' while awaiting for simulation_start")
                pass

    def is_stop_simulation(self):
        message = self.receive_subscription_message()
        if message == "stop_simulation":
            return True
        else:
            logging.warning("received message: '" + message + "' but no logic defined to handle it")
            return False

    def record_start_time(self):
        self.simulation_start_time = datetime.now()

    def get_start_time(self):
        return self.simulation_start_time

    def get_elapsed_time(self):
        return (datetime.now() - self.simulation_start_time) * self.time_scaling_factor

    def get_simulation_time(self):
        elapsed_time = self.get_elapsed_time()
        sim_time = self.simulation_start_time + elapsed_time
        # logging.debug("Time elapsed: {}  Simulation datetime: {}".format(elapsed_time, sim_time))
        return sim_time

    @staticmethod
    def get_ip_address():
        temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            temp_socket.connect(('192.0.0.8', 1027))
        except socket.error:
            return None
        return temp_socket.getsockname()[0]

    @staticmethod
    def archive_current_day(current_daily_disease_counts, previous_daily_disease_counts):
        logging.debug("Archiving current daily disease counts: {}".format(current_daily_disease_counts))
        previous_daily_disease_counts.append(current_daily_disease_counts)
        logging.debug("previous_daily_disease_counts is now: {}".format(previous_daily_disease_counts))

    @staticmethod
    def get_elapsed_days(previous_daily_disease_counts):
        return len(previous_daily_disease_counts)
