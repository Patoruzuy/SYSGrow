""" Module to configure and manage a wireless hotspot on a Raspberry Pi. This hotspot can be used to connect devices (e.g., ESP32-CAM) to the Raspberry
Pi when the Wi-Fi signal is weak.
"""
import os
import subprocess

class NetworkHotspotManager:
    """
    A class to configure and manage a wireless hotspot on a Raspberry Pi. 
    This hotspot can be used to connect devices (e.g., ESP32-CAM) to the Raspberry Pi when the Wi-Fi signal is weak.

    Attributes:
    -----------
    ssid : str
        The SSID (network name) of the hotspot.
    passphrase : str
        The password for the hotspot.
    dnsmasq_conf : str
        The path to the DNSMasq configuration file.
    hostapd_conf : str
        The path to the Hostapd configuration file.
    dhcpcd_conf : str
        The path to the DHCPCD configuration file.
    rc_local : str
        The path to the rc.local file for enabling NAT after reboot.
    ipv4_nat : str
        The path to save iptables NAT rules.

    Methods:
    --------
    _write_file(filepath, content):
        Writes content to a specified file path.
    
    _run_command(command):
        Executes a shell command and handles errors.
    
    configure_dnsmasq():
        Configures the DNSMasq service for the hotspot.
    
    configure_hostapd():
        Configures the Hostapd service for the hotspot with pre-defined SSID and passphrase.
    
    configure_dhcpcd():
        Configures the DHCPCD service to assign a static IP address to the wlan0 interface.
    
    configure_nat():
        Configures NAT (Network Address Translation) for sharing internet access with connected devices.
    
    enable_ip_forwarding():
        Enables IP forwarding for the Raspberry Pi to route traffic between networks.
    
    start_hotspot():
        Starts the hotspot by configuring all necessary services (dnsmasq, hostapd, NAT).
    
    stop_hotspot():
        Stops the hotspot by disabling services and restoring network settings.
    """

    def __init__(self, ssid='NetworkName', passphrase='Passphrase'):
        """
        Initializes the RaspberryPiHotspot with the provided SSID and passphrase for the wireless network.

        Parameters:
        -----------
        ssid : str, optional
            The SSID (network name) of the hotspot (default is 'NetworkName').
        passphrase : str, optional
            The password for the hotspot (default is 'Passphrase').
        """
        self.ssid = ssid
        self.passphrase = passphrase
        self.dnsmasq_conf = "/etc/dnsmasq.conf"
        self.hostapd_conf = "/etc/hostapd/hostapd.conf"
        self.dhcpcd_conf = "/etc/dhcpcd.conf"
        self.rc_local = "/etc/rc.local"
        self.ipv4_nat = "/etc/iptables.ipv4.nat"

    def _write_file(self, filepath, content):
        """
        Writes the specified content to a file at the provided file path.

        Parameters:
        -----------
        filepath : str
            The path of the file to write.
        content : str
            The content to write into the file.
        """
        try:
            with open(filepath, 'w') as file:
                file.write(content)
            print(f"Successfully wrote to {filepath}")
        except Exception as e:
            raise Exception(f"Failed to write to {filepath}: {e}")

    def _run_command(self, command):
        """
        Executes the specified shell command and checks for errors.

        Parameters:
        -----------
        command : str
            The shell command to execute.
        """
        result = subprocess.run(command, shell=True, capture_output=True)
        if result.returncode != 0:
            raise Exception(f"Command failed: {command}\n{result.stderr.decode()}")
        print(f"Successfully ran command: {command}")

    def configure_dnsmasq(self):
        """
        Configures the DNSMasq service to assign IP addresses to devices connected to the hotspot via DHCP.
        """
        dnsmasq_content = f"""
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
"""
        self._write_file(self.dnsmasq_conf, dnsmasq_content)

    def configure_hostapd(self):
        """
        Configures the Hostapd service to create the hotspot with a specified SSID and passphrase.
        """
        hostapd_content = f"""
                interface=wlan0
                driver=nl80211
                ssid={self.ssid}
                hw_mode=g
                channel=7
                wmm_enabled=0
                macaddr_acl=0
                auth_algs=1
                ignore_broadcast_ssid=0
                wpa=2
                wpa_passphrase={self.passphrase}
                wpa_key_mgmt=WPA-PSK
                wpa_pairwise=TKIP
                rsn_pairwise=CCMP
                """
        self._write_file(self.hostapd_conf, hostapd_content)

    def configure_dhcpcd(self):
        """
        Configures the DHCPCD service to assign a static IP address to the Raspberry Pi’s wlan0 interface for the hotspot.
        """
        dhcpcd_content = """
                interface wlan0
                static ip_address=192.168.4.1/24
                nohook wpa_supplicant
                """
        # Append instead of overwriting
        with open(self.dhcpcd_conf, 'a') as file:
            file.write(dhcpcd_content)
        print(f"Appended dhcpcd configuration to {self.dhcpcd_conf}")

    def configure_nat(self):
        """
        Configures Network Address Translation (NAT) to allow devices connected to the hotspot to access the internet.
        """
        # Enable NAT between wlan0 and eth0
        self._run_command("sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE")
        self._run_command(f"sudo sh -c 'iptables-save > {self.ipv4_nat}'")

        # Add iptables restore to rc.local if not already present
        with open(self.rc_local, 'r') as file:
            rc_local_content = file.read()
        
        if "iptables-restore < /etc/iptables.ipv4.nat" not in rc_local_content:
            with open(self.rc_local, 'a') as file:
                file.write("iptables-restore < /etc/iptables.ipv4.nat\n")
            print(f"Added iptables-restore to {self.rc_local}")

    def enable_ip_forwarding(self):
        """
        Enables IP forwarding to allow routing between the Raspberry Pi’s ethernet and Wi-Fi networks.
        """
        self._run_command("sudo sh -c 'echo 1 > /proc/sys/net/ipv4/ip_forward'")
        self._run_command("sudo sed -i 's/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' /etc/sysctl.conf")
        print("Enabled IPv4 forwarding")

    def start_hotspot(self):
        """
        Starts the hotspot by configuring all necessary services and applying NAT and IP forwarding settings.
        """
        try:
            self.configure_dnsmasq()
            self.configure_hostapd()
            self.configure_dhcpcd()
            self.configure_nat()
            self.enable_ip_forwarding()
            
            # Start services once configurations are done
            self._run_command("sudo systemctl restart dnsmasq")
            self._run_command("sudo systemctl restart hostapd")
            print("Hotspot started successfully")
        except Exception as e:
            print(f"Failed to start hotspot: {e}")

    def stop_hotspot(self):
        """
        Stops the hotspot by disabling services, clearing NAT rules, and restoring default network settings.
        """
        try:
            self._run_command("sudo systemctl stop dnsmasq")
            self._run_command("sudo systemctl stop hostapd")
            self._run_command("sudo iptables -t nat -F")
            self._run_command(f"sudo sh -c 'iptables-save > {self.ipv4_nat}'")
            self._run_command("sudo sh -c 'echo 0 > /proc/sys/net/ipv4/ip_forward'")
            self._run_command("sudo sed -i 's/net.ipv4.ip_forward=1/#net.ipv4.ip_forward=1/' /etc/sysctl.conf")
            self._run_command("sudo systemctl restart dhcpcd")
            print("Hotspot stopped successfully")
        except Exception as e:
            print(f"Failed to stop hotspot: {e}")
