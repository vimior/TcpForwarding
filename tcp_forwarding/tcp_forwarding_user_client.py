#!/usr/bin/env python3
# Software License Agreement (BSD License)
#
# Copyright (c) 2022, Vm, Inc.
# All rights reserved.
#
# Author: Vinman <vinman.cub@gmail.com>

import time
import struct
import socket
import argparse
import threading
from forwarding import logger, create_tcp_socket_server, create_tcp_socket_client, Forwarding


class TcpForwardingUserClient(threading.Thread):
    def __init__(self, server_addr_, bind_addr_, server_target_addr_, unique_id_='0' * 16):
        super().__init__()
        self.daemon = True
        self._server_addr = server_addr_
        self._bind_addr = bind_addr_
        self._server_target_addr = server_target_addr_
        self._unique_id = unique_id_
        self.alive = True

    def _pack_verify_data(self):
        return struct.pack('<5s4si16s6s', b'<UVM>', socket.inet_aton(self._server_target_addr[0]),
                           self._server_target_addr[1], self._unique_id.encode('utf-8'), b'</UVM>')

    def run(self):
        logger.info('TcpForwardingUserClient({}) Start'.format(self._bind_addr))
        sock_server = create_tcp_socket_server(self._bind_addr)
        if not sock_server:
            logger.info('TcpForwardingUserClient({}) over'.format(self._bind_addr))
            return
        while self.alive:
            try:
                logger.info('Wait for client connect {}'.format(self._bind_addr))
                sock_in, addr_in = sock_server.accept()
                logger.info('Wait to connect tcp_forwarding_user_server {}'.format(self._server_addr))
                sock_out = create_tcp_socket_client(self._server_addr, show_log=False)
                if not sock_out:
                    sock_in.close()
                    continue
                sock_out.send(self._pack_verify_data())
                data = sock_out.recv(13)
                if not data:
                    sock_out.close()
                    sock_in.close()
                    continue
                if data != b'<UVM>OK</UVM>':
                    sock_out.close()
                    sock_in.close()
                    continue
                forward = Forwarding(sock_in, sock_out)
                forward.join()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error('TcpForwardingUserClient Exception, {}'.format(e))
        logger.info('TcpForwardingUserClient({}) over'.format(self._bind_addr))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server_host', type=str, default='xxx.yyy.cn')
    parser.add_argument('--server_port', type=int, default=22222)
    parser.add_argument('--bind_host', type=str, default='0.0.0.0')
    parser.add_argument('--bind_port', type=int, default=10086)
    parser.add_argument('--server_target_host', type=str, default='192.168.1.200')
    parser.add_argument('--server_target_port', type=int, default=3389)
    parser.add_argument('--unique_id', type=str, default='0' * 16)
    args = parser.parse_args()

    unique_id = args.unique_id
    if len(unique_id) > 16:
        print('UNIQUE_ID ERROR, only support string and the length of the UNIQUE_ID must less than 16')
        exit(0)
    if len(unique_id) < 16:
        unique_id = '{}{}'.format('0' * (16 - len(unique_id)), unique_id)

    server_addr = (args.server_host, args.server_port)
    bind_addr = (args.bind_host, args.bind_port)
    server_target_addr = (args.server_target_host, args.server_target_port)
    forwarding = TcpForwardingUserClient(server_addr, bind_addr, server_target_addr, unique_id)
    forwarding.start()

    while True:
        time.sleep(1)
