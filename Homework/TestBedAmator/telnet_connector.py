"""Modules that handles telnet configuration on devices"""
import telnetlib
import time

# from pyats.topology import Device

class TelnetConnector:
    """
    TelnetConnector class provides automated configuration
    for devices.

    Functions:
    - Initial login
    - dhcp configuration
    - ssh configuration
    - ospf configuration
    - basic interface configuration
    - FTD first configuration
    """
    def __init__(self):

        self.connection=None
        self.conn=None
        self.hostname=None

        self.ssh_con=None
        self.password=None
        self.username=None
        self.dev_name=None


    def connect(self, dev) -> None:
        """
        Establish telnet connection to the device using data from testbed

        Parameters:
            dev (Device): dev contains data from testbed
        """

        self.device = dev
        self.conn=dev.connections['telnet']
        self.connection=telnetlib.Telnet(
            host=self.conn.ip.compressed,
            port=self.conn.port
        )
        self.hostname=dev.custom['hostname']
        self.ssh_con=dev.connections['ssh']['credentials']['login']
        self.password=self.ssh_con['password']
        self.username=self.ssh_con['username']
        self.dev_name=str(dev)


    def initial_configuration(self) -> None:
        """
        Performs the initial configuration on the device

        It has the following configuration:

        1. FTD configuration
        2. Sets enable for IOSv
        3. Configures a hostname
        4. Configures DHCP
        5. Enables RESTCONF and HTTPS
        6. Activates SSH
        7. Configures initial interface
        8. Sets up OSPF
        """

        if self.device.type == 'firewall':
            self.FTD_init()
            return 0

        self.connection.write(b'en\n')

        self.connection.write(b'conf t\n')

        if self.device.os == 'iosv':
            secret = self.device.credentials.enable.password.plaintext
            self.connection.write(f'enable secret {secret}\n'.encode())

        self.connection.write(f'hostname {self.hostname}\n'.encode()),
        self.connection.expect([f"{self.hostname}\(config\)#".encode()])

        if "dhcp" in self.device.custom:
            for pool in self.device.custom["dhcp"]:
                self.connection.write(
                    f"ip dhcp excluded-address {pool['excluded'][0]} {pool['excluded'][1]}\n".encode()
                )
                self.connection.expect([f"{self.hostname}\\(config\\)#".encode()])

                pool_name = f"{pool['network'].split('.')[2]}"
                self.connection.write(f"ip dhcp pool {pool_name}\n".encode())
                self.connection.expect([f"{self.hostname}\\(dhcp-config\\)#".encode()])

                self.connection.write(f"network {pool['network']} {pool['mask']}\n".encode())
                self.connection.write(f"default-router {pool['default_router']}\n".encode())
                self.connection.write(f"dns-server {pool['dns_server']}\n".encode())

                self.connection.expect([f"{self.hostname}\\(dhcp-config\\)#".encode()])


        self.connection.write(b'ip http secure-server\n')
        self.connection.expect([f"{self.hostname}\(config\)#".encode()])
        self.connection.write(b'restconf\n')
        self.connection.expect([f"{self.hostname}\(config\)#".encode()])
        self.ssh_function()
        self.config_one_interface()
        self.config_ospf()
        self.connection.write(b'do wr\n')
        self.connection.write(b'exit\n')

    def config_ospf(self) -> None:
        """
        Enables and configures OSPF on device using interface data
        """

        item_dict = self.device.interfaces

        self.connection.write(b'router ospf 1\n')
        self.connection.expect([f"{self.hostname}\\(config-router\\)#".encode()])

        for value in item_dict.values():
            network = ('.'.join(str(value.ipv4).split('/')[0].split('.')[0:3]) + '.0')
            self.connection.write(f"network {network} 0.0.0.255 area 0\n".encode())
            self.connection.expect([f"{self.hostname}\\(config-router\\)#".encode()])

        self.connection.write(b'exit\n')
        self.connection.expect([f"{self.hostname}\\(config\\)#".encode()])


    def ssh_function(self) -> None:
        """
        Enables SSH access:

        1. Sets domain name
        2. Creates user with secret
        3. Generates RSA key
        4. Enables SSH version 2
        5. Configures VTY lines for SSH login
        """

        self.connection.write(b'ip domain name local\n')
        self.connection.expect([f"{self.hostname}\(config\)#".encode()])
        self.connection.write(f'username {self.username} secret {self.password.plaintext}\n'.encode())
        self.connection.expect([f"{self.hostname}\(config\)#".encode()])
        self.connection.write(b'crypto key generate rsa\n')
        self.connection.expect([b'How many bits in the modulus'], timeout=5)
        self.connection.write(b'1024\n')
        self.connection.expect([f"{self.hostname}\(config\)#".encode()])
        self.connection.write(b'ip ssh version 2\n')
        self.connection.expect([f"{self.hostname}\(config\)#".encode()])
        self.connection.write(b'line vty 0 4\n')
        self.connection.expect([f"{self.hostname}\(config-line\)#".encode()])
        self.connection.write(b'login local\n')
        self.connection.expect([f"{self.hostname}\(config-line\)#".encode()])
        self.connection.write(b'transport input ssh\n')
        self.connection.expect([f"{self.hostname}\(config-line\)#".encode()])
        self.connection.write(b'exit\n')
        self.connection.expect([f"{self.hostname}\(config\)#".encode()])

    def config_one_interface(self) -> None:
        """
        Configures one interface on the device using data from testbed
        """

        item_dict = self.device.interfaces
        first_interface = list(item_dict.values())[0]
        interface_name = str(first_interface).split(' ')[1]
        ip_addr = str(first_interface.ipv4).split('/')[0]

        self.connection.write(f"interface {interface_name}\n".encode())
        self.connection.expect([f"{self.hostname}\\(config-if\\)#".encode()])

        self.connection.write(f"ip address {ip_addr} 255.255.255.0\n".encode())
        self.connection.expect([f"{self.hostname}\\(config-if\\)#".encode()])

        self.connection.write(b"no shutdown\n")
        self.connection.expect([f"{self.hostname}\\(config-if\\)#".encode()])

        self.connection.write(b"exit\n")
        self.connection.expect([f"{self.hostname}\\(config\\)#".encode()])

    def FTD_init(self) -> None:
        """
        Automates the initial config on FTD:

        1. Logs in with default credentials
        2. Accepts EULA
        3. Sets new password
        4. Configures management interface (manual IP)
        5. Sets hostname
        """
        self.connection.expect([b'firepower login:'], timeout=10)
        self.connection.write(b'admin\n')

        self.connection.expect([b'Password:'], timeout=5)
        self.connection.write(b'Admin123\n')

        self.connection.expect([b'Press <ENTER> to display the EULA:'], timeout=5)
        self.connection.write(b'\n')

        for _ in range(15):
            self.connection.write(b' ')
            time.sleep(0.5)

        self.connection.expect([b'AGREE to the EULA:'], timeout=5)
        self.connection.write(b'\n')

        self.connection.expect([b'Enter new password:'], timeout=5)
        self.connection.write(b'Cisco!23\n')

        self.connection.expect([b'Confirm new password:'], timeout=5)
        self.connection.write(b'Cisco!23\n')

        self.connection.expect([b'Do you want to configure IPv4? (y/n) [y]:'], timeout=5)
        self.connection.write(b'y\n')

        self.connection.expect([b'Do you want to configure IPv6? (y/n) [n]:'], timeout=5)
        self.connection.write(b'n\n')

        self.connection.expect([b'Configure IPv4 via DHCP or manually? (dhcp/manual) [manual]:'], timeout=5)
        self.connection.write(b'manual\n')

        self.connection.expect([b'Enter an IPv4 address for the management interface [192.168.45.45]:'], timeout=5)
        self.connection.write(b'192.168.104.2\n')

        self.connection.expect([b'Enter an IPv4 netmask for the management interface [255.255.255.0]'], timeout=5)
        self.connection.write(b'255.255.255.0\n')

        self.connection.expect([b'Enter the IPv4 default gateway for the management interface [192.168.104.1]:'],
                               timeout=5)
        self.connection.write(b'192.168.104.1\n')

        self.connection.expect([b'Enter a fully qualified hostname for this system \[firepower\]:'], timeout=5)
        self.connection.write(f'{self.hostname}\n'.encode())

        self.connection.expect([b"Enter a comma-separated list of DNS servers or 'none' \[\]"], timeout=5)
        self.connection.write(b'none\n')

        self.connection.expect([b"Enter a comma-separated list of search domains or 'none' \[\]"], timeout=10)
        self.connection.write(b'none\n')

        self.connection.expect([b'Manage the device locally? (yes/no) [yes]:'], timeout=5)
        self.connection.write(b'yes\n')

        self.connection.write(b'exit\n')

        return 0


