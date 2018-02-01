import logging

import zmq

from config.sds_config import get_node_config
from node import Node


class DiseaseOutbreakAnalyzer(Node):

    def __init__(self, config):
        super(DiseaseOutbreakAnalyzer, self).__init__(config)
        self.disease = self.role_parameters['disease']
        self.daily_outbreak_threshold = self.role_parameters['daily_outbreak_threshold']
        self.disease_outbreak_alert_publisher_socket = None
        self.disease_count_subscription_sockets = set()
        self.current_daily_disease_counts = self.new_daily_disease_counts()
        self.previous_daily_disease_counts = []

    # disease_outbreak_analyzer nodes use PUB listeners to publish
    # disease outbreak alerts to health_district_systems
    def setup_listeners(self):
        # create listener zmq sockets and save IP address and ports in config
        my_ip_address = Node.get_ip_address()
        self.disease_outbreak_alert_publisher_socket = self.context.socket(zmq.PUB)
        disease_outbreak_alert_publisher_port = \
            self.disease_outbreak_alert_publisher_socket.bind_to_random_port("tcp://*")
        self.config['address_map'] = {
            'role': self.role,
            'health_district_system_address':
                "tcp://{}:{}".format(my_ip_address, str(disease_outbreak_alert_publisher_port))
        }

    # shutdown listeners that were created in setup_listeners
    def shutdown_listeners(self):
        self.disease_outbreak_alert_publisher_socket.close(linger=2)

    # each disease_outbreak_analyzer connects subscription sockets to each health_district_system node
    def connect_to_peers(self):
        # get the node_id's for connections to be made with health_district_system nodes
        connection_node_ids = self.config['connections']
        logging.debug("Connecting to node_id's: {}".format(connection_node_ids))
        for connection_node_id in connection_node_ids:
            # get the connection addresses
            connection_node_address = self.node_addresses[connection_node_id]['disease_outbreak_analyzer_address']
            disease_count_subscription_socket = self.context.socket(zmq.SUB)
            disease_count_subscription_socket.connect(connection_node_address)
            # empty string filter => receive all messages
            disease_count_subscription_socket.setsockopt_string(zmq.SUBSCRIBE, '')
            self.disease_count_subscription_sockets.add(disease_count_subscription_socket)

    # close connections to peer nodes
    def disconnect_from_peers(self):
        for socket in self.disease_count_subscription_sockets:
            socket.close(linger=2)

    def configure_poller(self):
        logging.info("Configuring main loop poller")
        self.poller = zmq.Poller()
        self.poller.register(self.overseer_subscribe_socket, zmq.POLLIN)
        for disease_count_subscription_socket in self.disease_count_subscription_sockets:
            self.poller.register(disease_count_subscription_socket)

    def new_daily_disease_counts(self):
        return {self.role + '_id': self.node_id,
                'disease': self.disease,
                'health_district_counts': {},
                'total': 0,
                'daily_outbreak_threshold': self.daily_outbreak_threshold,
                'notification_sent': False}

    def update_daily_disease_counts(self, health_district_system_id, disease_count):
        self.current_daily_disease_counts['health_district_counts'][health_district_system_id] = disease_count
        total = 0
        for health_district_system in self.current_daily_disease_counts['health_district_counts']:
            total = total + self.current_daily_disease_counts['health_district_counts'][health_district_system]
        self.current_daily_disease_counts['total'] = total

    def handle_daily_disease_count_message(self, message):
        self.vector_timestamp.increment_count(self.node_id)
        other_vector_timestamp = message['vector_timestamp']
        self.vector_timestamp.update_from_other(other_vector_timestamp)
        health_district_system_id = message['health_district_system_id']
        # filter for the disease of interest
        disease_count = message[self.disease]
        self.update_daily_disease_counts(health_district_system_id, disease_count)
        logging.info("{} daily total is now {}".format(self.disease, self.current_daily_disease_counts['total']))
        if self.current_daily_disease_counts['total'] >= self.daily_outbreak_threshold \
                and not self.current_daily_disease_counts['notification_sent']:
            logging.info("*** ALERT *** {} outbreak detected!  Notifying health_district_systems . . .")
            alert_message = {'message_type': "disease_outbreak_alert",
                             'disease': self.disease,
                             'vector_timestamp': self.vector_timestamp}
            logging.debug("Sending alert: {}".format(alert_message))
            self.disease_outbreak_alert_publisher_socket.send_pyobj(alert_message)
            self.current_daily_disease_counts['notification_sent'] = True

    def shutdown(self):
        logging.info("Shutting down . . .")
        self.disconnect_from_peers()
        self.shutdown_listeners()
        self.shutdown_zmq()

    def run_simulation(self):
        logging.info("Starting simulation main loop")
        run_simulation = True
        self.record_start_time()
        start_time = self.get_start_time()
        self.current_daily_disease_counts['start_timestamp'] = start_time
        while run_simulation:
            try:
                sockets = dict(self.poller.poll(700))  # poll timeout in milliseconds
            except KeyboardInterrupt:
                break

            for socket in sockets:
                if socket == self.overseer_subscribe_socket:
                    if self.is_stop_simulation():
                        logging.info("received stop_simulation")
                        run_simulation = False
                        break

                if socket in self.disease_count_subscription_sockets:
                    message = socket.recv_pyobj()
                    logging.debug("Received message: {}".format(message))
                    self.handle_daily_disease_count_message(message)

            # update simulation time
            sim_time = self.get_simulation_time()
            elapsed_days = self.get_elapsed_days(self.previous_daily_disease_counts)

            # if the day is over, archive the disease count
            if self.get_elapsed_time().days > elapsed_days:
                self.current_daily_disease_counts['end_timestamp'] = sim_time
                self.vector_timestamp.increment_count(self.node_id)
                self.archive_current_day(self.current_daily_disease_counts, self.previous_daily_disease_counts)
                # reset current_daily_disease_counts
                self.current_daily_disease_counts = self.new_daily_disease_counts()
                self.current_daily_disease_counts['start_timestamp'] = sim_time

        # shutdown procedures
        self.shutdown()


def main():
    # get configuration and setup overseer connection
    config = get_node_config("disease_outbreak_analyzer")
    logging.basicConfig(level=logging.DEBUG,
                        # filename="disease_outbreak_analyzer-{}.log".format(config['node_id']),
                        format='%(asctime)s [%(levelname)s] %(message)s')
    logging.debug(config)

    disease_outbreak_analyzer = DiseaseOutbreakAnalyzer(config)

    # setup listening sockets
    disease_outbreak_analyzer.setup_listeners()

    # register listener addresses with overseer
    disease_outbreak_analyzer.register()

    # get node_addresses from overseer and make peer connections
    disease_outbreak_analyzer.receive_node_addresses()

    # make peer connections
    disease_outbreak_analyzer.connect_to_peers()

    # configure main loop poller
    disease_outbreak_analyzer.configure_poller()

    # send "ready_to_start" message to overseer
    disease_outbreak_analyzer.send_ready_to_start()

    # await "start_simulation" message from overseer
    disease_outbreak_analyzer.await_start_simulation()

    # run the simulation
    disease_outbreak_analyzer.run_simulation()


if __name__ == "__main__":
    main()
