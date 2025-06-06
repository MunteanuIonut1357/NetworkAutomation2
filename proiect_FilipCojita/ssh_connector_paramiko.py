"""
ssh_connector_paramiko is the ssh connector file used by devices
in topology in order for ip interfaces and route configurations
to be done via ssh
"""

import re
import time
from typing import Optional, List, Union
import paramiko
from pyats.datastructures import AttrDict
from pyats.topology import Device


class SSHConnectorParamiko:
    DEFAULT_PROMPT: str = r'[>#]'

    def __init__(self, device: Device, **kwargs) -> None:
        """
        Initialize the SSH connector with a pyATS Device.

        Args:
            device (Device): pyATS device object to connect to.
            **kwargs: Optional parameters like timeout and buffer_size.
        """
        self.device: Device = device
        self.client: Optional[paramiko.SSHClient] = None
        self.shell: Optional[paramiko.Channel] = None
        self._connected: bool = False
        self.timeout: int = kwargs.get('timeout', 10)  # seconds for read/wait
        self._buffer_size: int = kwargs.get('buffer_size', 4096)

    def connect(self, **kwargs) -> None:
        """
        Establish an SSH connection and open an interactive shell.

        Raises:
            ValueError: If connection info is missing.
            RuntimeError: If connection or shell invocation fails.
        """
        connection: Optional[AttrDict] = kwargs.get('connection') or self.device.connections.ssh
        if not connection:
            raise ValueError("Missing connection information.")

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ip: str = connection.ip.compressed
        port: int = connection.port or 22
        username: str = self.device.credentials.default.username
        password: str = self.device.credentials.default.password.plaintext

        try:
            self.client.connect(
                hostname=ip,
                port=port,
                username=username,
                password=password,
                look_for_keys=False,
                allow_agent=False,
                timeout=10,
            )
            self.shell = self.client.invoke_shell()
            self.shell.settimeout(2)
            self._connected = True
            self._clear_buffer()
        except Exception as e:
            raise RuntimeError(f"Failed to connect to {ip}:{port} - {e}")

    def _clear_buffer(self) -> None:
        """Flush any initial data in the shell buffer."""
        time.sleep(0.5)
        while self.shell and self.shell.recv_ready():
            self.shell.recv(self._buffer_size)
            time.sleep(0.1)

    def is_connected(self) -> bool:
        """
        Check if the SSH connection is active.

        Returns:
            bool: True if connected, False otherwise.
        """
        if self.client is None:
            return False
        transport = self.client.get_transport()
        return transport is not None and transport.is_active()

    def disconnect(self) -> None:
        """Close the SSH shell and client connections."""
        if self.shell:
            self.shell.close()
        if self.client:
            self.client.close()
        self._connected = False

    def _read_until_prompt(self, prompt_patterns: Union[str, List[str]], timeout: Optional[int] = None) -> str:
        """
        Read from shell until a prompt pattern is matched or timeout occurs.

        Args:
            prompt_patterns (Union[str, List[str]]): Prompt regex or list of regex strings.
            timeout (Optional[int]): Timeout in seconds.

        Returns:
            str: The output read from the shell.

        Raises:
            TimeoutError: If prompt is not detected within timeout.
            RuntimeError: On read errors.
        """
        if isinstance(prompt_patterns, str):
            prompt_patterns = [prompt_patterns]

        prompt_regexes = [re.compile(p.encode()) for p in prompt_patterns]
        buffer = b''
        timeout = timeout or self.timeout
        end_time = time.time() + timeout

        while time.time() < end_time:
            try:
                if self.shell and self.shell.recv_ready():
                    chunk = self.shell.recv(self._buffer_size)
                    buffer += chunk

                    for regex in prompt_regexes:
                        if regex.search(buffer):
                            return buffer.decode(errors='ignore')
                else:
                    time.sleep(0.2)
            except Exception as e:
                raise RuntimeError(f"Error reading from shell: {e}")

        raise TimeoutError(f"Timeout waiting for prompt(s) {prompt_patterns}. Output so far:\n{buffer.decode(errors='ignore')}")

    def execute(self, command: str, prompt: Optional[Union[str, List[str]]] = None, timeout: Optional[int] = None) -> str:
        """
        Execute a command on the remote device and wait for prompt.

        Args:
            command (str): Command string to send.
            prompt (Optional[Union[str, List[str]]]): Expected prompt(s) regex.
            timeout (Optional[int]): Timeout for waiting prompt.

        Returns:
            str: Command output.

        Raises:
            RuntimeError: If connection not established or on command errors.
        """
        if not self._connected or not self.shell:
            raise RuntimeError("SSH connection is not established. Call connect() first.")

        prompt = prompt or self.DEFAULT_PROMPT
        try:
            self.shell.send(f"{command}\n".encode())
            output = self._read_until_prompt(prompt, timeout)
            return output
        except TimeoutError as e:
            raise RuntimeError(f"Timeout executing command '{command}': {e}")
        except Exception as e:
            raise RuntimeError(f"Error executing command '{command}': {e}")

    def configure_interfaces(self) -> None:
        """
        Configure interfaces on the device based on the device's interface attributes.

        This example assumes each interface has 'name' and IPv4 info.
        """
        self.execute('configure terminal', prompt=r'\(config\)#')
        for iface in self.device.interfaces.values():
            self.execute(f"interface {iface.name}", prompt=r'\(config-if\)#')
            ip = iface.ipv4.ip.compressed
            mask = iface.ipv4.network.netmask.exploded
            self.execute(f"ip address {ip} {mask}", prompt=r'\(config-if\)#')
            self.execute('no shutdown', prompt=r'\(config-if\)#')
            self.execute('exit', prompt=r'\(config\)#')
        self.execute('end', prompt=r'#')

    def configure_static_routes(self) -> None:
        """
        Configure static routes on the device using custom attributes.

        Also configures ip-helper-address based on hostname in device.custom.hostname.
        """
        self.execute('configure terminal', prompt=r'\(config\)#')
        for route in getattr(self.device.custom, 'static_routes', []):
            dest = route['dest']
            mask = '255.255.255.0'  # Adjust mask logic if needed
            next_hop = route['next_hop']
            self.execute(f"ip route {dest} {mask} {next_hop}", prompt=r'\(config\)#')

        hostname = getattr(self.device.custom, 'hostname', '').lower()
        if hostname == 'em-r1':
            self.execute('interface eth0/2', prompt=r'\(config-if\)#')
            self.execute('ip helper-address 192.168.105.1', prompt=r'\(config-if\)#')
            self.execute('exit', prompt=r'\(config\)#')
        elif hostname == 'iosv':
            self.execute('interface g0/2', prompt=r'\(config-if\)#')
            self.execute('ip helper-address 192.168.105.1', prompt=r'\(config-if\)#')
            self.execute('exit', prompt=r'\(config\)#')

        self.execute('end', prompt=r'#')
        self.execute('write', prompt=r'#')
