"""LAN discovery without DNS lookups or external HTTP services."""
import ipaddress
import socket

PRIVATE_NETWORKS = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
VIRTUAL_NAMES = ('docker', 'veth', 'virtual', 'vmware', 'vbox', 'hyper-v', 'vethernet', 'vpn', 'tun', 'tap', 'tailscale', 'wireguard', 'wsl', 'zerotier')


def private_ipv4(address):
    try:
        ip = ipaddress.IPv4Address(address)
        return any(ip in network for network in PRIVATE_NETWORKS)
    except ipaddress.AddressValueError:
        return False


def lan_addresses():
    import psutil
    candidates = []
    try:
        stats = psutil.net_if_stats()
        for name, addresses in psutil.net_if_addrs().items():
            if any(part in name.lower() for part in VIRTUAL_NAMES): continue
            if name not in stats or not stats[name].isup: continue
            for address in addresses:
                if address.family == socket.AF_INET and private_ipv4(address.address):
                    candidates.append((name, address.address))
    except (OSError, psutil.Error):
        return []
    # Ask routing which of the already discovered LAN addresses it uses. No packet sent.
    preferred = None
    for _, address in candidates:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect((address, 9))
                preferred = probe.getsockname()[0]
            if preferred: break
        except OSError:
            continue
    unique = {ip: name for name, ip in candidates}
    return sorted(((name, ip) for ip, name in unique.items()), key=lambda item: (item[1] != preferred, item[0], item[1]))


def access_url(address, port):
    if address != 'localhost' and not private_ipv4(address):
        raise ValueError('Endereço LAN inválido.')
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('Porta inválida.')
    return f'http://{address}:{port}'
