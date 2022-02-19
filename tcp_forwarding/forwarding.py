#!/usr/bin/env python3
# Software License Agreement (BSD License)
#
# Copyright (c) 2022, Vm, Inc.
# All rights reserved.
#
# Author: Vinman <vinman.cub@gmail.com>

import sys
import time
import queue
import socket
import logging
import threading

logger = logging.getLogger('tcp_forwarding')
logger.setLevel(logging.INFO)
for handler in logger.handlers:
    if isinstance(handler, logging.StreamHandler):
        logger.removeHandler(handler)
stream_handler_fmt = '[%(levelname)s][%(asctime)s][%(filename)s:%(lineno)d] - - %(message)s'
stream_handler_date_fmt = '%Y-%m-%d %H:%M:%S'
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(logging.Formatter(stream_handler_fmt, stream_handler_date_fmt))
logger.addHandler(stream_handler)


def get_time():
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())


def time_print(msg):
    print('[{}] {}'.format(get_time(), msg))


def create_tcp_socket_server(addr, backlog=1, show_log=True):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(addr)
        sock.listen(backlog)
        logger.info('[TcpSocketServer-{}] listen({}) on {}'.format(id(addr), backlog, addr))
        return sock
    except Exception as e:
        if show_log:
            logger.error('Create TcpSocketServer Failed, {}'.format(e))
    return None


def create_tcp_socket_client(addr, show_log=True):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.connect(addr)
        logger.info('[TcpSocketClient-{}] Connect {} Success'.format(id(addr), addr))
        return sock
    except Exception as e:
        if show_log:
            logger.error('[TcpSocketClient-{}] Create Failed, {}'.format(id(addr), e))
    return None


class Forwarding(object):
    def __init__(self, sock_in, sock_out, timeout=5):
        super().__init__()
        self.alive = True
        sock_in.setblocking(True)
        sock_in.settimeout(timeout)
        sock_out.setblocking(True)
        sock_out.settimeout(timeout)
        in2out_que = queue.Queue()  # forwarding from sock_in to sock_out
        out2in_que = queue.Queue()  # forwarding from sock_out to sock_in
        in2out_cond = threading.Condition()
        out2in_cond = threading.Condition()
        # get data from out2in_que, then send with sock_in
        in_send_t = threading.Thread(target=self._send_loop, args=(sock_in, out2in_que, out2in_cond), daemon=True)
        # recv data with sock_in, then put to in2out_que
        in_recv_t = threading.Thread(target=self._recv_loop, args=(sock_in, in2out_que, in2out_cond), daemon=True)
        # get data from in2out_que, then send with sock_out
        out_send_t = threading.Thread(target=self._send_loop, args=(sock_out, in2out_que, in2out_cond), daemon=True)
        # recv data with sock_out, then put to out2in_que
        out_recv_t = threading.Thread(target=self._recv_loop, args=(sock_out, out2in_que, out2in_cond), daemon=True)
        self.threads = [in_send_t, in_recv_t, out_send_t, out_recv_t]
        for t in self.threads:
            t.start()

    def join(self):
        for t in self.threads:
            t.join()

    def _send_loop(self, sock, que, cond):
        addr = sock.getpeername()
        logger.info('[Forwarding] socket_send_loop start, {}'.format(addr))
        while self.alive:
            # avoid can not quit
            if que.qsize() == 0:
                # time.sleep(0.001)
                # continue
                with cond:
                    cond.wait()

            if que.qsize() == 0:
                continue
            try:
                data = que.get()
                sock.send(data)
            except Exception as e:
                # logger.error('[Forwarding] socket_send_exception, {}, {}'.format(e, addr))
                break
        self.alive = False
        logger.info('[Forwarding] socket_send_loop over, {}'.format(addr))
        sock.close()

    def _recv_loop(self, sock, que, cond):
        addr = sock.getpeername()
        logger.info('[Forwarding] socket_recv_loop start, {}'.format(addr))
        while self.alive:
            try:
                data = sock.recv(10240)
                if data:
                    que.put(data)
                    with cond:
                        cond.notify()
                else:
                    break
            except socket.timeout:
                # logger.error('[Forwarding] socket recv timeout, {}'.format(addr))
                continue
            except Exception as e:
                # logger.error('[Forwarding] socket_recv_exception, {}, {}'.format(e, addr))
                break
        self.alive = False
        logger.info('[Forwarding] socket_recv_loop over, {}'.format(addr))
        with cond:
            cond.notify()
        sock.close()


