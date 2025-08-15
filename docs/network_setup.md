MPTCP Network Environment Setup
This guide details how to configure a Linux Virtual Machine (VM) to simulate a multi-path network, which is essential for testing and demonstrating the capabilities of MPTCP. We will use Ubuntu 22.04 as the reference.

Part 1: Configure Multiple Network Interfaces
Your VM needs at least two network adapters to simulate multiple paths.

In your VM software (VirtualBox, VMWare):

Shut down your VM.

Go to the VM's settings -> "Network".

Adapter 1: Should already be enabled, likely set to "NAT" or "Bridged". This will be your primary path.

Adapter 2: Enable a second adapter. Set it to a different network type if possible (e.g., if Adapter 1 is NAT, set Adapter 2 to "Host-Only"). This ensures they get IPs on different subnets. If using Bridged mode for both, ensure they connect to different physical networks if possible, or just let them get two different IPs from your router.

Start your VM.

Verify Interfaces:
Once the VM boots, check that the kernel sees both interfaces.

ip addr

You should see enp0s3 (or similar) and enp0s8 (or similar). Note down their names.

Configure IP Addresses:
We need to ensure both interfaces have an IP address. Ubuntu 22.04 uses netplan.

Find your netplan config file: ls /etc/netplan/. It will be a .yaml file.

Edit the file (e.g., sudo nano /etc/netplan/01-network-manager-all.yaml).

Configure it to manage both interfaces. DHCP is the easiest method.

Example netplan configuration:

# This file describes the network interfaces available on your system
# For more information, see netplan(5).
network:
  version: 2
  renderer: networkd
  ethernets:
    # Your first interface name
    enp0s3:
      dhcp4: true
      mptcp: true # Enable mptcp on this interface
    # Your second interface name
    enp0s8:
      dhcp4: true
      mptcp: true # Enable mptcp on this interface

Apply the configuration:

sudo netplan apply

Verify again with ip addr that both interfaces have an IP address.

Part 2: Enable MPTCP in the Kernel
Modern Linux kernels (5.6+) have MPTCP built-in. We just need to enable it.

Check Kernel Version:

uname -r

If the version is 5.6 or higher, you are good to go. Ubuntu 22.04 ships with a compatible kernel.

Enable MPTCP via sysctl:
This command tells the kernel's networking stack to use MPTCP when available.

sudo sysctl -w net.mptcp.enabled=1

Make the Setting Permanent:
To ensure MPTCP is enabled on every boot, add the setting to the sysctl configuration file.

echo "net.mptcp.enabled=1" | sudo tee /etc/sysctl.d/90-mptcp.conf

Part 3: Verify MPTCP is Working
Install mptcpd and tools:
The mptcpd daemon helps manage and monitor MPTCP connections.

sudo apt install mptcpd

Use mptcpize to test:
The mptcpize command can run any program within an MPTCP-aware context. We can use it with curl to connect to an MPTCP-enabled server.

# mptcp.io is a test server
mptcpize run curl -sS https://mptcp.io

The output should confirm that an MPTCP connection was made.

Monitor MPTCP connections:
While a connection is active (e.g., downloading a large file through your proxy), you can monitor the subflows.

mptcpize monitor

This command will show you the active MPTCP sessions and which network interfaces (subflows) are being used for each one. If you see both of your interface IPs listed for a single connection, congratulations, MPTCP is working!

You are now ready to run the SOCKS5 proxy, which will automatically benefit from this multi-path setup.