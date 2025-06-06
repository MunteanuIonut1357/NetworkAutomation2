import subprocess
import telnetlib
import time

def set_ip_on_ubuntu():
    interface='ens4'
    ubuntu_ip='192.168.11.21/24'
    destination_ip='192.168.12.0/24'
    gateway_ip='192.168.11.1'
    client_network='192.168.101.0/24'
    subprocess.Popen(['sudo','ip','address',"add",ubuntu_ip,"dev",interface],stdout=subprocess.PIPE)
    set_up=subprocess.Popen(["sudo","ip","link","set",interface,"up"],stdout=subprocess.PIPE)
    subprocess.Popen(['sudo',"ip","route","add",destination_ip,"via",gateway_ip],stdout=subprocess.PIPE)
    subprocess.Popen(['sudo', "ip", "route", "add", client_network, "via", gateway_ip], stdout=subprocess.PIPE)

def set_ip_on_guest():
    interface = 'eth0'
    guest_ip = '192.168.101.100/24' #nu ia cu dhcp ip :(
    destination_ip = '192.168.101.1/24'

    new_te = telnetlib.Telnet("92.83.42.103", 5045)
    new_te.write(f"ip addr add {guest_ip} dev {interface}".encode())
    new_te.write(f"ip link set dev {interface} up".encode())
    new_te.write(f"ip route add default via {destination_ip}".encode())

def ip_setting_function(te,i):
    te.write(f'int eth0/{str(i)}\n'.encode())
    te.expect([b"IOU1\(config-if\)#"])
    te.write(f'ip add 192.168.10{str(i)}.1 255.255.255.0\n'.encode())
    te.expect([b"IOU1\(config-if\)#"])
    te.write(b'no shutdown\n')
    te.expect([b"IOU1\(config-if\)#"])
    te.write(b'exit\n')
    te.expect([b"IOU1\(config\)#"])

def dhcp_exclude_interval(te,start,finish):
    te.write(f'ip dhcp excluded-address 192.168.101.{start} 192.168.101.{finish}\n'.encode())
    te.expect([b"IOU1\(config\)#"])

def dhcp_function(te):
    te.write(b'ip dhcp pool UbuntuDocker\n')
    te.expect([b"IOU1\(dhcp-config\)#"])
    te.write(b'network 192.168.101.0 255.255.255.0\n')
    te.expect([b"IOU1\(dhcp-config\)#"])
    te.write(b'default-router 192.168.101.1\n')
    te.expect([b"IOU1\(dhcp-config\)#"])
    te.write(b'dns-server 192.168.102.1\n')
    te.expect([b"IOU1\(dhcp-config\)#"])

def ssh_function(te):
    te.write(b'ip domain name local\n')
    te.expect([b"IOU1\(config\)#"])
    te.write(b'username admin password cisco\n')
    te.expect([b"IOU1\(config\)#"])
    te.write(b'crypto key generate rsa\n')
    time.sleep(3)
    te.write(b' \n')
    time.sleep(3)
    te.write(b'yes\n')
    time.sleep(3)
    te.write(b'\n')
    te.expect([b"IOU1\(config\)#"])
    te.write(b'ip ssh version 2\n')
    te.expect([b"IOU1\(config\)#"])
    te.write(b'line vty 0 4\n')
    te.expect([b"IOU1\(config-line\)#"])
    te.write(b'login local\n')
    te.expect([b"IOU1\(config-line\)#"])
    te.write(b'transport input ssh\n')
    te.expect([b"IOU1\(config-line\)#"])
    te.write(b'exit\n')
    te.expect([b"IOU1\(config\)#"])
    te.write(b'exit\n')

def router():
    host='92.83.42.103'
    port=5044
    interface_number=4

    te=telnetlib.Telnet(host,port)

    print("m-am conectat")
    te.write(b'')

    te.write(b'conf t\n')
    te.expect([b"IOU1\(config\)#"])
    for i in range(1,interface_number):
       ip_setting_function(te,i)

    te.write(b'int eth1/0\n')
    te.expect([b"IOU1\(config-if\)#"])
    te.write(b'ip add 192.168.104.1 255.255.255.0\n')
    te.expect([b"IOU1\(config-if\)#"])
    te.write(b'no shutdown\n')
    te.expect([b"IOU1\(config-if\)#"])
    te.write(b'exit\n')
    te.expect([b"IOU1\(config\)#"])
    te.write(b'ip route 0.0.0.0 0.0.0.0 192.168.11.21\n')
    te.expect([b"IOU1\(config\)#"])

    dhcp_exclude_interval(te,1,99)
    dhcp_exclude_interval(te,200,254)

    dhcp_function(te)

    te.write(b'exit\n')
    te.expect([b"IOU1\(config\)#"])
    ssh_function(te)
    te.write(b'exit\n')


def test_ping():

    try:
        output=subprocess.check_output(
                ['ping', '-c', '1', '192.168.101.100'],
                stderr=subprocess.STDOUT,
                text=True)

        if 'bytes from' in output:
            print("Ping is working")
        else:
            print("Ping failed")

    except subprocess.CalledProcessError as e:
        print("Ping failed")


while True:
    print("1.Set IP on Ubuntu Server and Configure")
    print("2.Set IP on Guest and Configure")
    print("3.Configure Router")
    print("4.Check IP from Ubuntu Server to Guest")
    print("5.Exit")
    option=input("Choose an option:")

    match option:
        case "1":
            set_ip_on_ubuntu()
            print("Command executed successfully!")
        case "2":
            set_ip_on_guest()
            print("Command executed successfully!")
        case "3":
            router()
            print("Command executed successfully!")
        case "4":
            test_ping()
            print("Command executed successfully!")
        case "5":
            break

    time.sleep(2)




