#!/usr/bin/env python3
# Software License Agreement (BSD License)
#
# Copyright (c) 2022, Vm, Inc.
# All rights reserved.
#
# Author: Vinman <vinman.cub@gmail.com>

import time
import socket
import struct
import argparse
import threading
from forwarding import logger, create_tcp_socket_server, create_tcp_socket_client, Forwarding


class TcpForwardingUserServer(threading.Thread):
    def __init__(self, bind_addr):
        super().__init__()
        self.daemon = True
        self._bind_addr = bind_addr
        self.alive = True

    @staticmethod
    def _unpack_verify_data(data):
        try:
            if not data or len(data) < 35:
                return None, ''
            # '<UVM>{HOST}{PORT}{UNIQUE_ID}</UVM>'
            # TODO check data is legal
            uvm_begin, host, port, unique_id, uvm_end = struct.unpack('<5s4si16s6s', data)
            if uvm_begin != b'<UVM>' or uvm_end != b'</UVM>':
                return None, ''
            addr = (socket.inet_ntoa(host), port)
            return addr, unique_id.decode('utf-8')
        except Exception as e:
            return None, ''

    def _forwarding_thread(self, sock):
        sock.settimeout(10)
        sock.setblocking(True)
        try:
            data = sock.recv(35)
            addr, unique_id = self._unpack_verify_data(data)
            if not addr:
                logger.error('verify failed, {}'.format(data))
                sock.close()
                return
            logger.info('addr: {}, unique_id: {}'.format(addr, unique_id))
            sock_out = create_tcp_socket_client(addr)
            if not sock_out:
                sock.close()
                return

            sock.send(b'<UVM>OK</UVM>')
            forward = Forwarding(sock, sock_out)
            forward.join()
        except Exception as e:
            logger.error('forwarding_thread exception, {}'.format(e))

    def run(self):
        logger.info('TcpForwardingUserServer({}) Start'.format(self._bind_addr))
        sock_server = create_tcp_socket_server(self._bind_addr)
        if not sock_server:
            logger.info('TcpForwardingUserServer({}) over'.format(self._bind_addr))
            return
        while self.alive:
            logger.info('Wait for tcp_forwarding_user_client connect {}'.format(self._bind_addr))
            sock_in, addr_in = sock_server.accept()
            t = threading.Thread(target=self._forwarding_thread, args=(sock_in,), daemon=True)
            t.start()
        logger.info('TcpForwardingUserServer({}) over'.format(self._bind_addr))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bind_host', type=str, default='0.0.0.0')
    parser.add_argument('--bind_port', type=int, default=22222)
    args = parser.parse_args()

    forwarding = TcpForwardingUserServer((args.bind_host, args.bind_port))
    forwarding.start()

    while True:
        time.sleep(1)




