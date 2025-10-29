from opcua import Client, ua
import time

# Λίστα με όλα τα PLC endpoints
PLC_LIST = [
    "opc.tcp://192.168.53.230:4840",
    "opc.tcp://192.168.49.230:4840",
    "opc.tcp://192.168.48.230:4840",
    # Μπορείς να προσθέσεις όσα θέλεις εδώ
]

ROOT_NODE_ID = "ns=3;s=ServerInterfaces"

def get_readable_nodes(node):
    """Αναδρομική συλλογή nodes που μπορούν να διαβαστούν"""
    nodes_dict = {}
    try:
        value = node.get_value()
        browse_name = node.get_browse_name().Name
        nodes_dict[browse_name] = node
    except ua.UaStatusCodeError:
        pass
    except Exception:
        pass

    try:
        children = node.get_children()
        for child in children:
            nodes_dict.update(get_readable_nodes(child))
    except Exception:
        pass

    return nodes_dict

def setup_plc_client(name, url):
    """Σύνδεση με PLC και συλλογή nodes"""
    client = Client(url)
    try:
        client.connect()
        root_node = client.get_node(ROOT_NODE_ID)
        nodes = get_readable_nodes(root_node)
        print(f"{name}: Βρέθηκαν {len(nodes)} αναγνώσιμα nodes.")
        return client, nodes
    except Exception as e:
        print(f"{name}: Σφάλμα σύνδεσης ή ανάγνωσης ({e})")
        return None, {}

def print_live_values(plc_name, nodes_dict):
    print(f"=== {plc_name} ===")
    for name, node in nodes_dict.items():
        try:
            value = node.get_value()
            print(f"{name}: {value}")
        except Exception as e:
            print(f"{name}: Error ({e})")
    print("==================\n")

# Σύνδεση σε όλα τα PLC
plc_clients = []
for idx, plc_url in enumerate(PLC_LIST, start=1):
    name = f"PLC {idx}"
    client, nodes = setup_plc_client(name, plc_url)
    plc_clients.append({"name": name, "client": client, "nodes": nodes})

try:
    while True:
        print("\n=== Live Monitoring ===")
        for plc in plc_clients:
            if plc["client"]:
                print_live_values(plc["name"], plc["nodes"])
        time.sleep(1)
except KeyboardInterrupt:
    print("Διακοπή από χρήστη.")
finally:
    # Αποσύνδεση όλων
    for plc in plc_clients:
        if plc["client"]:
            plc["client"].disconnect()
    print("Αποσυνδεθήκαμε από όλα τα PLC.")
