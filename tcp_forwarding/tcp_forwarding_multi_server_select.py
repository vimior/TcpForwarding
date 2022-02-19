import time
import queue
import struct
import socket
import argparse
import selectors
import threading
from forwarding import create_tcp_socket_server, logger


class TcpForwardingMultiServer(threading.Thread):
    def __init__(self, bind_addr):
        super().__init__()
        self.daemon = True
        self.alive = True
        self.sel = selectors.DefaultSelector()
        self.sock_pair_map = {}
        self._addr_sockserver_map = {}
        sock_server = create_tcp_socket_server(bind_addr)
        if not sock_server:
            exit(1)
        self._bind_addr = bind_addr
        self.register_accept(sock_server, False)
        self.forwarding_thread_size = 5
        self.forwarding_que = queue.Queue()
        self.forwarding_threads = []
        if self.forwarding_thread_size > 0:
            self._create_forwarding_thread()
    
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
    
    def _create_forwarding_thread(self):
        for i in range(self.forwarding_thread_size):
            self.forwarding_threads.append(
                threading.Thread(
                    target=self._forwarding_thread, 
                    args=(i+1,),
                    name='ForwardingThread-{}'.format(i+1), 
                    daemon=True
                )
            )
        for th in self.forwarding_threads:
            th.start()
    
    def _forwarding_thread(self, i):
        logger.info('ForwardingThread-{} start'.format(i))
        while self.alive:
            item = self.forwarding_que.get()
            self._socket_send(item['sock'], item['data'])
        logger.info('ForwardingThread-{} start'.format(i))

    def _socket_accept_registration_port(self, sock, mask):
        conn, addr = sock.accept()
        logger.info('[RegistrationPortServer] accepted {} from {}'.format(id(conn), addr))
        self.register_read(conn, False)

    def _socket_accept_forwarding(self, sock, mask):
        conn, addr = sock.accept()
        logger.info('[ForwardingServer-{}] accepted {} from {}'.format(id(sock), id(conn), addr))
        s_addr = None
        for k, v in self._addr_sockserver_map.items():
            if v == sock:
                s_addr = k
                break
        if s_addr is not None:
            self._addr_sockserver_map.pop(s_addr, None)
        conn2 = self.sock_pair_map.pop(sock)
        self.sel.unregister(conn2)
        self.sel.unregister(sock)
        self._bind_sock_pair(conn, conn2)
        self.register_read(conn, True)
        self.register_read(conn2, True)
        self._socket_send(conn2, b'<UVM>OK</UVM>')
        sock.close()
        logger.info('[ForwardingServer-{}] close'.format(id(sock)))

    def _socket_read_registration_port(self, conn, mask):
        data = conn.recv(35)
        addr, unique_id = self._unpack_verify_data(data)
        if not addr:
            logger.error('verify failed, {}'.format(data))
            self._socket_remove(conn)
            return
        logger.info('[Conn-{}] registration addr: {}, unique_id: {}'.format(id(conn), addr, unique_id))
        addr_str = '{}:{}'.format(addr[0], addr[1])
        if addr_str in self._addr_sockserver_map:
            try:
                self._addr_sockserver_map[addr_str].shutdown(socket.SHUT_RDWR)
                self._addr_sockserver_map[addr_str].close()
            except:
                pass
            self._addr_sockserver_map.pop(addr_str, None)
            time.sleep(1)
        sock_server = create_tcp_socket_server(addr)
        if sock_server:
            self._addr_sockserver_map[addr_str] = sock_server
            self._bind_sock_pair(conn, sock_server)
            self.register_accept(sock_server, True)
        else:
            self._socket_remove(conn)
    
    def _socket_read_forwarding(self, conn, mask):
        data = conn.recv(4096)
        if not data:
            self._socket_remove(conn)
            return
        if self.forwarding_thread_size > 0:
            self.forwarding_que.put({'sock': self.sock_pair_map[conn], 'data': data})
        else:
            self._socket_send(self.sock_pair_map[conn], data)
    
    def _socket_send(self, sock, data):
        try:
            sock.send(data)
            return 0
        except Exception as e:
            self._socket_remove(sock)
        return -1

    def _socket_remove(self, sock):
        try:
            logger.info('[Conn-{}] is removed'.format(id(sock)))
            if sock in self.sock_pair_map and self.sock_pair_map[sock]:
                conn2 = self.sock_pair_map.pop(sock)
                self.sel.unregister(conn2)
                try:
                    conn2.shutdown(socket.SHUT_RDWR)
                    conn2.close()
                except:
                    pass
                logger.info('[Conn-{}] is removed'.format(id(conn2)))
            self.sel.unregister(sock)
            try:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
            except:
                pass
            if sock in self.sock_pair_map:
                del self.sock_pair_map[sock]
        except:
            pass

    def _bind_sock_pair(self, sock1, sock2):
        self.sock_pair_map[sock1] = sock2
        self.sock_pair_map[sock2] = sock1

    def register_accept(self, sock, only_forwarding=True):
        if not sock:
            return -1
        sock.setblocking(False)
        self.sel.register(sock, selectors.EVENT_READ, 
            self._socket_accept_forwarding if only_forwarding else self._socket_accept_registration_port)
        return 0

    def register_read(self, sock, only_forwarding=True):
        if not sock:
            return -1
        sock.setblocking(False)
        self.sel.register(sock, selectors.EVENT_READ, 
            self._socket_read_forwarding if only_forwarding else self._socket_read_registration_port)
        return 0

    def run(self):
        logger.info('MultiForwardingServer Thread start')
        while self.alive:
            try:
                events = self.sel.select()
                for key, mask in events:
                    try:
                        callback = key.data
                        callback(key.fileobj, mask)
                    except Exception as e:
                        logger.error('callback exception, id={}, {}'.format(id(key.fileobj), e))
                        self._socket_remove(key.fileobj)
            except Exception as e:
                logger.error('MultiForwardingServer Exception: {}'.format(e))
                break
        logger.info('MultiForwardingServer Thread over')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bind_host', type=str, default='0.0.0.0')
    parser.add_argument('--bind_port', type=int, default=33333)
    args = parser.parse_args()

    forwarding = TcpForwardingMultiServer((args.bind_host, args.bind_port))
    forwarding.start()

    while True:
        time.sleep(1)
