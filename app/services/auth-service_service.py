import socket

# Set a reasonable timeout for the socket connection
def create_connection(host, port, timeout=5.0):  # 5 seconds timeout
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        return s
    except socket.timeout:
        # Handle the timeout exception
        print(f"Timeout occurred while connecting to {host}:{port}")
        return None

# Usage
host = "10.255.255.1"
port = 80
s = create_connection(host, port)
if s:
    # Proceed with the connection
    pass
else:
    # Handle the connection failure
    pass