import telnetlib
from typing import Optional

from pyats.datastructures import AttrDict
from pyats.topology import Device


class TelnetConnector:

    def __init__(self, device: Device, **kwargs):
        self._conn: Optional[telnetlib.Telnet] = None
        self.device = device
        self.connection: Optional[AttrDict] = None

    def connect(self, **kwargs):
        self.connection = kwargs['connection']
        self._conn = telnetlib.Telnet(
            host=self.connection.ip.compressed,
            port=self.connection.port
        )

    def enable_rest(self):
        self.execute('conf t', prompt=[r'\(config\)#'])
        self.execute("ip http secure-server", prompt=[r'\(config\)#'])
        self.execute('#restconf', prompt=[r'\(config\)#'])

    def do_initial_configuration(self):
        # configure IOU and IOSv
        if self.device.os == 'ios':
            self._initial_conf_ios()

        # configure CSR Router
        elif self.device.os == 'iosxe':
            self._initial_conf_csr()

    def _initial_conf_ios(self):
        self.execute('conf t', prompt=[r'\(config\)#'])

        # configure interface
        interface = self.device.interfaces['initial']
        self.execute(f"int {interface.name}", prompt=[r'\(config-if\)#'])
        ip = interface.ipv4.ip.compressed
        mask = interface.ipv4.network.netmask.exploded
        self.execute(f"ip add {ip} {mask}", prompt=[r'\(config-if\)#'])
        self.execute('no shut', prompt=[r'\(config-if\)#'])
        self.execute('exit', prompt=[r'\(config\)#'])

        # configure ssh
        hostname = self.device.custom.hostname
        self.execute(f'hostname {hostname}', prompt=[r'\(config\)#'])
        out = self.execute('crypto key generate rsa modulus 1024', prompt=[r'\(config\)#', r'replace them\?'])
        if 'replace them' in out:
            self.execute('yes', prompt=[r'\(config\)#'])
        username = self.device.connections.ssh.credentials.login.username
        password = self.device.connections.ssh.credentials.login.password.plaintext

        self.execute(f'username {username} privilege 15 secret {password}', prompt=[r'\(config\)#'])
        self.execute('line vty 0 4', prompt=[r'\(config-line\)#'])
        self.execute("transport input ssh", prompt=[r'\(config-line\)#'])
        self.execute("login local", prompt=[r'\(config-line\)#'])
        self.execute('exit', prompt=[r'\(config\)#'])
        self.execute('ip ssh version 2', prompt=[r'\(config\)#'])

        # configure SCP server for napalm
        self.execute('ip scp server enable', prompt=[r'\(config\)#'])
        enable_password = self.device.credentials.enable.password.plaintextif
        if self.device.platform == 'iosv':
            self.execute(f'enable secret {enable_password}', prompt=[r'\(config\)#'])
        # save configuration
        self.execute('end', prompt=[rf'{hostname}#'])
        self.execute('write', prompt=[rf'\[confirm\]|{hostname}#'])
        self.execute('', prompt=[rf'{hostname}#'])

    def _initial_conf_csr(self):
        self.execute('conf t', prompt=[r'\(config\)#'])

        # configure interface
        interface = self.device.interfaces['initial']
        self.execute(f"interface {interface.name}", prompt=[r'\(config-if\)#'])
        ip = interface.ipv4.ip.compressed
        mask = interface.ipv4.network.netmask.exploded
        self.execute(f"ip address {ip} {mask}", prompt=[r'\(config-if\)#'])
        self.execute('no shutdown', prompt=[r'\(config-if\)#'])
        self.execute('exit', prompt=[r'\(config\)#'])

        # configure ssh server
        hostname = self.device.custom.hostname
        self.execute(f'hostname {hostname}', prompt=[r'\(config\)#'])
        self.execute('ip domain-name localdomain', prompt=[r'\(config\)#'])  # required for key gen
        self.execute('crypto key generate rsa modulus 1024', prompt=[r'\(config\)#'])

        # configure user
        username = self.device.connections.ssh.credentials.login.username
        password = self.device.connections.ssh.credentials.login.password.plaintext
        self.execute(f'username {username} privilege 15 secret {password}', prompt=[r'\(config\)#'])

        # configure vty lines for ssh
        self.execute('line vty 0 4', prompt=[r'\(config-line\)#'])
        self.execute('transport input ssh', prompt=[r'\(config-line\)#'])
        self.execute('login local', prompt=[r'\(config-line\)#'])
        self.execute('exit', prompt=[r'\(config\)#'])

        self.execute('ip ssh version 2', prompt=[r'\(config\)#'])

        # configure SCP server for napalm
        self.execute('ip scp server enable', prompt=[r'\(config\)#'])

        # save config
        self.execute('end', prompt=[rf'{hostname}#'])
        self.execute('write memory', prompt=[rf'\[OK\]|{hostname}#'])
        self.execute('', prompt=[rf'{hostname}#'])

    def disconnect(self):
        self._conn.close()

    def execute(self, command, **kwargs):
        prompt: list[bytes] = list(map(lambda _: _.encode(), kwargs['prompt']))
        self._conn.write(f'{command}\n'.encode())
        response = self._conn.expect(prompt)
        return response

    def configure(self, command, **kwargs):
        # Send configuration commands
        return "config output"

    def is_connected(self):
        return not self._conn.eof
