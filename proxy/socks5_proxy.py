import socket
import threading
import struct
import os
import psycopg2
import logging
import time
import uuid

# --- Configuration ---
HOST = '127.0.0.1'
PORT = 1080
BUFFER_SIZE = 4096
SOCKS_VERSION = 5

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)s] (%(threadName)-10s) %(message)s')

# --- Database Connection ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database using environment variables."""
    try:
        conn = psycopg2.connect(
            dbname=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            host=os.environ.get('DB_HOST', 'localhost'),
            port=os.environ.get('DB_PORT', '5432')
        )
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"Could not connect to database: {e}")
        return None

def db_log_start(session_id, client_addr, dest_addr, dest_port):
    """Logs the start of a new connection to the database."""
    sql = """
        INSERT INTO proxy_logs (session_id, client_address, destination_address, destination_port, start_time, status)
        VALUES (%s, %s, %s, %s, NOW(), 'active');
    """
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (session_id, f"{client_addr[0]}:{client_addr[1]}", dest_addr, dest_port))
            conn.commit()
        except Exception as e:
            logging.error(f"DB log_start failed: {e}")
        finally:
            conn.close()

def db_log_end(session_id, bytes_sent, bytes_received, status, error_message=None):
    """Updates the log entry when a connection is closed."""
    sql_fetch_start = "SELECT start_time FROM proxy_logs WHERE session_id = %s;"
    sql_update = """
        UPDATE proxy_logs
        SET end_time = NOW(),
            bytes_sent = %s,
            bytes_received = %s,
            status = %s,
            error_message = %s,
            connection_duration_ms = EXTRACT(EPOCH FROM (NOW() - start_time)) * 1000,
            throughput_kbps = CASE
                WHEN EXTRACT(EPOCH FROM (NOW() - start_time)) > 0 THEN
                    ((%s + %s) / 1024) / EXTRACT(EPOCH FROM (NOW() - start_time))
                ELSE 0
            END
        WHERE session_id = %s;
    """
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(sql_update, (bytes_sent, bytes_received, status, error_message, bytes_sent, bytes_received, session_id))
            conn.commit()
        except Exception as e:
            logging.error(f"DB log_end failed: {e}")
        finally:
            conn.close()


class ProxyThread(threading.Thread):
    """Handles a single client connection."""

    def __init__(self, client_socket, client_address):
        super().__init__()
        self.client_socket = client_socket
        self.client_address = client_address
        self.session_id = str(uuid.uuid4())

    def run(self):
        """Main thread execution logic."""
        logging.info(f"Accepted connection from {self.client_address}")

        try:
            # 1. SOCKS5 Greeting
            if not self.handle_greeting():
                return

            # 2. SOCKS5 Request
            dest_socket, dest_addr, dest_port = self.handle_request()
            if not dest_socket:
                return

            # 3. Log connection start to DB
            db_log_start(self.session_id, self.client_address, dest_addr, dest_port)
            
            # 4. Relay data
            bytes_sent, bytes_received = self.relay_data(dest_socket)

            # 5. Log connection end to DB
            db_log_end(self.session_id, bytes_sent, bytes_received, 'closed')
            logging.info(f"Connection to {dest_addr}:{dest_port} closed. Sent: {bytes_sent}, Received: {bytes_received}")

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            db_log_end(self.session_id, 0, 0, 'error', str(e))
        finally:
            self.client_socket.close()

    def handle_greeting(self):
        """Handles the initial SOCKS5 greeting and authentication method negotiation."""
        # Read the greeting message: | VER | NMETHODS | METHODS |
        greeting = self.client_socket.recv(2)
        version, nmethods = struct.unpack("!BB", greeting)

        if version != SOCKS_VERSION:
            logging.error("Unsupported SOCKS version.")
            return False

        # Read available methods
        self.client_socket.recv(nmethods)

        # We only support NO AUTHENTICATION REQUIRED (0x00)
        # Send response: | VER | METHOD |
        response = struct.pack("!BB", SOCKS_VERSION, 0)
        self.client_socket.sendall(response)
        return True

    def handle_request(self):
        """Handles the client's request to connect to a destination."""
        # Read the request: | VER | CMD | RSV | ATYP | DST.ADDR | DST.PORT |
        try:
            header = self.client_socket.recv(4)
            version, cmd, _, atyp = struct.unpack("!BBBB", header)

            if version != SOCKS_VERSION or cmd != 1:  # 1 = CONNECT
                logging.error("Unsupported SOCKS version or command.")
                self.send_reply(5) # Command not supported
                return None, None, None

            if atyp == 1:  # IPv4
                addr_bytes = self.client_socket.recv(4)
                dest_addr = socket.inet_ntoa(addr_bytes)
            elif atyp == 3:  # Domain name
                addr_len = self.client_socket.recv(1)[0]
                addr_bytes = self.client_socket.recv(addr_len)
                dest_addr = addr_bytes.decode('utf-8')
            else: # IPv6 not supported for simplicity
                logging.error(f"Unsupported address type: {atyp}")
                self.send_reply(8) # Address type not supported
                return None, None, None

            port_bytes = self.client_socket.recv(2)
            dest_port = struct.unpack('!H', port_bytes)[0]

            # Connect to the destination
            dest_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # The OS will automatically use MPTCP if enabled
            dest_socket.connect((dest_addr, dest_port))
            
            self.send_reply(0) # Success
            return dest_socket, dest_addr, dest_port

        except Exception as e:
            logging.error(f"Failed to handle request: {e}")
            self.send_reply(1) # General SOCKS server failure
            return None, None, None

    def send_reply(self, rep_code):
        """Sends a SOCKS5 reply to the client."""
        # | VER | REP | RSV | ATYP | BND.ADDR | BND.PORT |
        # REP: 0=success, 1=general failure, 5=command not supported, 8=address type not supported
        reply = struct.pack("!BBBBIH", SOCKS_VERSION, rep_code, 0, 1, 0, 0)
        self.client_socket.sendall(reply)

    def relay_data(self, dest_socket):
        """Relays data between the client and destination sockets."""
        bytes_sent = 0
        bytes_received = 0
        
        try:
            while True:
                # Use select to wait for data on either socket
                readable_sockets, _, _ = select.select([self.client_socket, dest_socket], [], [])
                
                for sock in readable_sockets:
                    data = sock.recv(BUFFER_SIZE)
                    if not data:
                        return bytes_sent, bytes_received

                    if sock is self.client_socket:
                        dest_socket.sendall(data)
                        bytes_sent += len(data)
                    else:
                        self.client_socket.sendall(data)
                        bytes_received += len(data)
        except ConnectionResetError:
            logging.warning("Connection reset by peer.")
        except Exception as e:
            logging.error(f"Error during data relay: {e}")
            raise # Re-raise to be caught in the main run loop
        finally:
            dest_socket.close()
        
        return bytes_sent, bytes_received


def main():
    """Main function to start the SOCKS5 proxy server."""
    # Check for DB environment variables
    if not all([os.environ.get(k) for k in ['DB_NAME', 'DB_USER', 'DB_PASSWORD']]):
        logging.error("Database environment variables (DB_NAME, DB_USER, DB_PASSWORD) are not set. Exiting.")
        return

    # This module is needed for the relay_data function
    global select
    import select

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(10) # Listen for up to 10 connections

    logging.info(f"SOCKS5 proxy listening on {HOST}:{PORT}")

    while True:
        try:
            client_socket, client_address = server_socket.accept()
            proxy_thread = ProxyThread(client_socket, client_address)
            proxy_thread.start()
        except KeyboardInterrupt:
            logging.info("Shutting down proxy server.")
            break
        except Exception as e:
            logging.error(f"Error accepting connections: {e}")

    server_socket.close()

if __name__ == '__main__':
    main()
