from config.sds_config import get_node_config
from node_admin import setup_zmq, setup_health_district_system_zmq_listeners, register, receive_node_addresses
import logging

# get configuration and setup overseer connection
config = get_node_config("health_district_system")
node_id = config['node_id']
logging.basicConfig(level=logging.DEBUG,
                    # filename='health_district_system-' + node_id + '.log',
                    format='%(asctime)s [%(levelname)s] %(message)s')
logging.debug(config)
(context, overseer_request_socket, overseer_subscribe_socket) = setup_zmq(config)

# setup listening sockets
(electronic_medical_record_socket, disease_outbreak_analyzer_socket) = \
    setup_health_district_system_zmq_listeners(context, config)

# register listener addresses with overseer
register(overseer_request_socket, node_id, config)

# get node_addresses from overseer and make peer connections
node_addresses = receive_node_addresses(overseer_subscribe_socket)
logging.debug("node_addresses received from overseer: {}".format(node_addresses))
