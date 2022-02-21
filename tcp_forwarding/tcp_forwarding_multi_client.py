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


class TcpForwardingMultiClient(threading.Thread):
    def __init__(self, server_addr_, target_addr_, server_target_addr_, unique_id_='0' * 16):
        super().__init__()
        self.daemon = True
        self._server_addr = server_addr_
        self._target_addr = target_addr_
        self._server_target_addr = server_target_addr_
        self._unique_id = unique_id_
        self.alive = True

    def _pack_verify_data(self):
        return struct.pack('<5s4si16s6s', b'<UVM>', socket.inet_aton(self._server_target_addr[0]),
                           self._server_target_addr[1], self._unique_id.encode('utf-8'), b'</UVM>')

    def run(self):
        logger.info('TcpForwardingMultiClient Start')        
        log_flag = True
        while self.alive:
            try:
                if log_flag:
                    log_flag = False
                    logger.info('Wait to connect tcp_forwarding_multi_server {}'.format(self._server_addr))
                sock_in = create_tcp_socket_client(self._server_addr, show_log=False)
                if not sock_in:
                    continue
                sock_in.settimeout(30)
                log_flag = True
                ret = sock_in.send(self._pack_verify_data())
                logger.info('send verify data, ret={}'.format(ret))
                try:
                    data = sock_in.recv(13)
                except socket.timeout:
                    sock_in.close()
                    continue
                logger.info('recv confirm data, data={}'.format(data))
                if not data:
                    sock_in.close()
                    continue
                if data != b'<UVM>OK</UVM>':
                    sock_in.close()
                    if data == b'<UVM>EX</UVM>':
                        logger.error('SERVER PORT {} IS USED, sleep 5 seconds'.format(self._server_target_addr[1]))
                        time.sleep(5)
                    continue
                logger.info('Wait to connect target {}'.format(self._target_addr))
                sock_out = create_tcp_socket_client(self._target_addr)
                if not sock_out:
                    sock_in.close()
                    continue
                forward = Forwarding(sock_in, sock_out)
                forward.join()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error('TcpForwardingMultiClient Exception, {}'.format(e))
        logger.info('TcpForwardingMultiClient over')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server_host', type=str, default='xxx.yyy.cn')
    parser.add_argument('--server_port', type=int, default=33333)
    parser.add_argument('--target_host', type=str, default='localhost')
    parser.add_argument('--target_port', type=int, default=3389)
    parser.add_argument('--server_target_port', type=int, default=10086)
    parser.add_argument('--unique_id', type=str, default='0' * 16)

    args = parser.parse_args()

    unique_id = args.unique_id
    if len(unique_id) > 16:
        print('UNIQUE_ID ERROR, only support string and the length of the UNIQUE_ID must less than 16')
        exit(0)
    if len(unique_id) < 16:
        unique_id = '{}{}'.format('0' * (16 - len(unique_id)), unique_id)

    server_addr = (args.server_host, args.server_port)
    target_addr = (args.target_host, args.target_port)
    server_target_addr = ('0.0.0.0', args.server_target_port)
    forwarding = TcpForwardingMultiClient(server_addr, target_addr, server_target_addr, unique_id)
    forwarding.start()

    while True:
        time.sleep(1)
