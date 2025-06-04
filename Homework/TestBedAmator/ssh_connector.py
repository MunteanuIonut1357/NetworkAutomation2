"""Modules that handles SSH connection and configuration on devices"""
from netmiko import ConnectHandler

class SSHConnector:
    """
    Class used to configure device using ssh and netmiko.
    """
    def __init__(self):
        self.username = None
        self.password = None
        self.connection = None
        self.ip = None
        self.port = None

    def connect(self, dev) -> None:
        """
        Establish ssh connection to the device using netmiko

        Parameters:
            dev (Device): dev contains data from testbed
        """
        self.device = dev
        self.conn = dev.connections['ssh']

        self.ip = self.conn.ip.compressed
        self.port = self.conn.port
        self.hostname = dev.custom['hostname']

        self.ssh_con = self.conn.credentials['login']
        self.username = self.ssh_con['username']
        self.password = self.ssh_con['password'].plaintext

        secret = None
        if hasattr(self.device.credentials, 'enable'):
            secret = self.device.credentials.enable.password.plaintext

        self.connection = ConnectHandler(
            device_type='cisco_ios',
            ip=self.ip,
            port=self.port,
            username=self.username,
            password=self.password,
            secret=secret
        )

    def config_interfaces(self) -> None:
        """
        Configures all the interfaces of the device with IP and sets them to up
        """

        item_dict = self.device.interfaces

        if self.device.os == 'iosv':
            self.connection.enable()


        for value in item_dict.values():
            ip_interface = str(value.ipv4).split('/')[0]
            interface = str(value).split(' ')[1]

            self.connection.send_config_set([
                f"interface {interface}",
                f"ip address {ip_interface} 255.255.255.0",
                "no shutdown",
                "exit"
            ])
