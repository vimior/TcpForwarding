#!/usr/bin/env python3
# Software License Agreement (BSD License)
#
# Copyright (c) 2022, Vm, Inc.
# All rights reserved.
#
# Author: Vinman <vinman.cub@gmail.com>

import time
import socket
import argparse
import threading
from forwarding import logger, create_tcp_socket_server, create_tcp_socket_client, Forwarding


class TcpForwarding(threading.Thread):
    def __init__(self, from_addr, to_addr):
        super().__init__()
        self.daemon = True
        self._from_addr = from_addr
        self._to_addr = to_addr
        self.alive = True

    def run(self):
        logger.info('TcpForwarding Start, from {} to {}'.format(self._from_addr, self._to_addr))
        sock_server = create_tcp_socket_server(self._from_addr)
        if not sock_server:
            logger.info('TcpForwarding over, from {} to {}'.format(self._from_addr, self._to_addr))
            return
        forwards = []
        while self.alive:
            try:
                logger.info('Wait for in_client')
                sock_in, addr = sock_server.accept()

                logger.info('Wait to connect {}'.format(self._to_addr))
                sock_out = create_tcp_socket_client(self._to_addr)
                if not sock_out:
                    continue
                forwards = list(filter(lambda forward: forward.alive, forwards))
                forwards.append(Forwarding(sock_in, sock_out))
            except Exception as e:
                logger.error('Forwarding Server Client Exception, {}'.format(e))

        logger.info('TcpForwarding over, from {} to {}'.format(self._from_addr, self._to_addr))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bind_host', type=str, default='0.0.0.0')
    parser.add_argument('--bind_port', type=int, default=11111)
    parser.add_argument('--target_host', type=str, default='localhost')
    parser.add_argument('--target_port', type=int, default=3389)
    args = parser.parse_args()

    bind_addr = (args.bind_host, args.bind_port)
    to_addr = (args.target_host, args.target_host)
    forwarding = TcpForwarding(bind_addr, to_addr)
    forwarding.start()

    while True:
        time.sleep(1)

