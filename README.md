Optimized MPTCP Proxy with Performance Analytics
This project demonstrates the power of Multi-Path TCP (MPTCP) by implementing a high-performance SOCKS5 proxy that leverages multiple network paths for enhanced connection resilience. The system includes a PostgreSQL backend for logging performance metrics and a Python-based analytics suite to visualize the results.

Project Goal: To build and validate a system that can maintain a stable, long-running data transfer even when a primary network path fails, proving the tangible benefits of MPTCP for robust networking.

Final Conclusion & Results
The MPTCP-aware proxy successfully handled a simulated network path failure during a large data transfer. While a standard TCP connection would have terminated, the proxy seamlessly rerouted traffic over the remaining active path, demonstrating a significant improvement in connection resilience.

The performance logs confirm a single, uninterrupted connection lasting over 78 seconds that successfully transferred 100MB of data, even after a network interface was disabled mid-transfer.

Key Performance Plots
1. A Single, Long-Duration Resilient Connection:
The plot below shows the distribution of connection durations. The bar on the far right represents the successful 100MB download, clearly distinct from other short-lived test connections. This proves the connection did not drop during the network failure.

2. High-Volume Data Transfer:
This plot confirms that the long-duration connection was also a high-volume data transfer, with the vast majority of data being transferred to a single destination during the resilience test.

Project Architecture
Prerequisites
OS: A Linux distribution (Ubuntu 20.04+ recommended) running in a VM (VirtualBox, VMWare).

Python: Python 3.8+

Database: PostgreSQL server (version 12+)

Tools: git, python3-venv, curl

Step 1: Setup the Multi-Path Network Environment
This is the most critical step. We will configure a Linux VM with two network interfaces and enable MPTCP.

Configure VM Network Adapters:

In your VM software (VirtualBox/VMWare), shut down the VM.

In Settings -> Network:

Adapter 1: Enable, set to "Bridged" or "NAT".

Adapter 2: Enable, set to a different type (e.g., "Host-Only") or also "Bridged".

Start the VM.

Configure netplan:

Find your netplan file (e.g., /etc/netplan/01-network-manager-all.yaml).

Edit it with sudo nano <your-file-path.yaml>.

Replace the entire content with the following, making sure to use your correct interface names (find them with ip addr):

network:
  version: 2
  renderer: networkd
  ethernets:
    enp0s3: # <-- Your first interface name
      dhcp4: true
    enp0s8: # <-- Your second interface name
      dhcp4: true
      dhcp4-overrides:
        use-routes: false

Switch to networkd:
Desktop versions of Ubuntu often default to NetworkManager. We need to switch to systemd-networkd which works correctly with our netplan file.

sudo systemctl enable systemd-networkd
sudo systemctl start systemd-networkd
sudo systemctl stop NetworkManager
sudo systemctl disable NetworkManager

Apply Network Configuration:

sudo netplan apply

Enable MPTCP in the Kernel:

sudo sysctl -w net.mptcp.enabled=1
echo "net.mptcp.enabled=1" | sudo tee /etc/sysctl.d/90-mptcp.conf

Your network is now ready.

Step 2: Setup the PostgreSQL Database
Install PostgreSQL:

sudo apt update
sudo apt install postgresql postgresql-contrib

Create Database and User:

sudo -u postgres psql

Inside the psql shell, run these commands:

CREATE DATABASE mptcp_analytics;
CREATE USER proxy_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE mptcp_analytics TO proxy_user;
\q

Create and Configure the Logs Table:

Run the schema script:

sudo -u postgres psql -d mptcp_analytics < database/schema.sql

Log back in to grant permissions:

sudo -u postgres psql -d mptcp_analytics

Run these grant commands inside the psql shell:

GRANT ALL PRIVILEGES ON TABLE proxy_logs TO proxy_user;
GRANT USAGE ON SEQUENCE proxy_logs_log_id_seq TO proxy_user;
\q

Step 3: Setup and Run the Proxy
Clone the Repository and Install Dependencies:

git clone <your-repo-url>
cd <your-repo-name>
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

Set Environment Variables:
These are required for the Python scripts to connect to the database.

export DB_NAME="mptcp_analytics"
export DB_USER="proxy_user"
export DB_PASSWORD="your_secure_password"

Run the Proxy Server:

python proxy/socks5_proxy.py

The proxy is now running and listening on 127.0.0.1:1080.

Step 4: The Resilience Test (How to Generate Meaningful Data)
This test will prove the value of the proxy. You will need three separate terminals.

Terminal 1: Start the proxy server (follow Step 3 above). Leave it running.

Terminal 2: This terminal will run the download.

Navigate to the project directory and activate the virtual environment.

You are now ready to start the download.

Terminal 3: This terminal will simulate the network failure.

Add a network delay: This slows the download so you have time to perform the test.

# Use 'replace' in case a default rule exists
sudo tc qdisc replace dev enp0s3 root netem delay 200ms

Execute the Test:

In Terminal 2, start the large file download through the proxy:

curl --socks5-hostname 127.0.0.1:1080 http://az764295.vo.msecnd.net/stable/b3e4e68a0bc097f0ae7907b217c1119af9e03435/vscode-server-linux-x64.tar.gz -o /dev/null

While it's downloading, go to Terminal 3 and disable the other network interface:

sudo ip link set enp0s8 down

Observe in Terminal 2 as the download pauses briefly and then resumes.

Cleanup:

Wait for the download to finish.

Stop the proxy in Terminal 1 (Ctrl + C).

Remove the network delay in Terminal 3:

sudo tc qdisc del dev enp0s3 root netem

Step 5: Analyze the Performance Data
In Terminal 2, ensure your environment variables are set (see Step 3.2).

Run the analytics script:

python analytics/performance_analyzer.py

The script will print a summary to the console and save the final plots (like those at the top of this README) as .png files in the analytics/ directory.