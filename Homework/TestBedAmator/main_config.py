"""Modules that handles device configuration"""

import subprocess
import time

from pyats import aetest
from pyats.topology import loader

from telnet_connector import TelnetConnector
from ssh_connector import SSHConnector

#Loaded data from test_bedu file
tb=loader.load("test_bedu.yaml")

class TestClass(aetest.Testcase):
    """Testcase class that handles device configuration and ping functionality"""

    @aetest.test
    def run_menu(self) -> None:
        """
        Displays an interactive menu for the user
        with the following options:

        1. Full configuration for the routers (IOU1,CSR,Iosv)
        2. Full configuration for the Ubuntuserver24.10
        3. Ping test from Ubuntuserver to the rest of the devices
        0. Exit configuration
        """
        while True:
            print("1.Make telnet config and ssh")
            print("2.Make Ubuntuserver24.10 config")
            print("3.Test ping")
            print("0.Exit")

            choice=input("Enter your choice: ")

            match choice:
                case "1":
                    self.main_config()
                case "2":
                    self.set_ip_on_ubuntu()
                case "3":
                    self.check_ping()
                case "0":
                    break


    def main_config(self) -> None:

        """
        Loops through all the devices that are in testbed (almost)
        If a device supports telnet it will use TelnetConnector
        If a device supports ssh it will use SSHConnector
        """

        dev = tb.devices

        for item in dev.values():

            if 'telnet' in item.connections:

                connector = TelnetConnector()
                connector.connect(item)
                connector.initial_configuration()

            if 'ssh' in item.connections and item.os != 'ftd':
                connector = SSHConnector()
                connector.connect(item)
                connector.config_interfaces()

            time.sleep(2)

    def check_ping(self) -> None:

        """
        Runs a ping test from Ubuntuserver24.10 to the rest of the devices
        It checks if there is connectivity or not
        """

        #some ipv4 to test if the ping works
        dev = tb.devices
        ip_list = []

        for device in dev.values():
            for interface in device.interfaces.values():
                if interface.ipv4:
                    ip = str(interface.ipv4).split('/')[0]
                    if ip.endswith('.1'):
                        ip_list.append(ip)

        for ip in ip_list:
            try:
                output = subprocess.check_output(
                    ['ping', '-c', '1', ip],
                    stderr=subprocess.STDOUT,
                    text=True)

                if 'bytes from' in output:
                    print(f"Ping to {ip} is working")
                else:
                    print(f"Ping to {ip} failed")

            except subprocess.CalledProcessError:
                print(f"Ping to {ip} failed")

    def set_ip_on_ubuntu(self) -> None:
        """
        Configures a static IP address on Ubuntuserver24.10 and activates the interface
        Configures static routes for all the networks that exist
        Uses the 'subprocess' module to configure the device
        """
        interface = 'ens4'
        ubuntu_ip = '192.168.11.21/24'
        gateway_ip = '192.168.11.1'

        # Assign the IP address and bring the interface up
        with subprocess.Popen(['sudo', 'ip', 'address', "add", ubuntu_ip, "dev", interface],
                         stdout=subprocess.PIPE) as _:
            pass

        with subprocess.Popen(["sudo", "ip", "link", "set", interface, "up"],
                         stdout=subprocess.PIPE) as _:
            pass

        dev = tb.devices
        net_list = []

        for device in dev.values():
            for value in device.interfaces.values():
                if value.ipv4:
                    network = ('.'.join(str(value.ipv4).split('/')[0].split('.')[0:3]) + '.0/24')
                    if network not in net_list:
                        net_list.append(network)

        for net in net_list:
            with subprocess.Popen(['sudo', "ip", "route", "add", net, "via", gateway_ip],
                                  stdout=subprocess.PIPE) as _:
                pass



if __name__ == '__main__':
    #Starts the test
    aetest.main()
