from opcua import Client

# Αντικατέστησε με το endpoint του PLC
url = "opc.tcp://192.168.53.230:4840"

client = Client(url)

def browse_node(node, depth=0):
    """Αναδρομική εκτύπωση των nodes"""
    print("  " * depth + f"{node} | {node.get_browse_name()}")
    try:
        children = node.get_children()
        for child in children:
            browse_node(child, depth + 1)
    except Exception as e:
        pass  # κάποια nodes μπορεί να μην έχουν παιδιά ή πρόσβαση

try:
    client.connect()
    print("Συνδεθήκαμε στον OPC UA server!")

    root = client.get_root_node()
    print("Browsing nodes:\n")
    browse_node(root)

finally:
    client.disconnect()
    print("Αποσυνδεθήκαμε.")
