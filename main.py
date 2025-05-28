#!/usr/bin/env python3
import sys, time
from bluetooth import discover_devices, find_service, BluetoothError
import os
from PyOBEX.client import Client, BrowserClient
import xml.etree.ElementTree as ET

def list_devices(timeout=8):
    """Scanează Bluetooth și afișează o listă numerotată cu dispozitivele găsite."""
    print(f"[+] Scanning for devices ({timeout}s)...")
    devices = discover_devices(duration=timeout, lookup_names=True)
    if not devices:
        print("[!] Nu am găsit niciun dispozitiv Bluetooth.")
        sys.exit(1)
    for idx, (addr, name) in enumerate(devices, start=1):
        print(f"  {idx}) {name or 'Unknown'} [{addr}]")
    return devices

def choose_device(devices):
    """Întreabă utilizatorul să aleagă un index și returnează adresa aleasă."""
    while True:
        choice = input("Selectează numărul dispozitivului țintă: ")
        if not choice.isdigit():
            print("Introduce un număr valid.")
            continue
        idx = int(choice)
        if 1 <= idx <= len(devices):
            addr, name = devices[idx-1]
            print(f"[+] Ai ales: {name or 'Unknown'} [{addr}]")
            return addr
        else:
            print(f"Selectează un număr între 1 și {len(devices)}.")

def find_obex_channel(addr):
    """Caută serviciul OBEX File Transfer sau Object Push și returnează portul RFCOMM."""
    print(f"[+] Searching OBEX services on {addr} …")
    services = find_service(address=addr)
    for svc in services:
        # ne interesează profilul OBEX FTP sau PUSH
        print(f"  Găsit serviciu: {svc['name']} ({svc['protocol']})")
        if svc["protocol"] == "RFCOMM" and svc["name"] in (
            "OBEX File Transfer", b"OBEX FTP"
        ):
            port = svc["port"]
            print(f"[+] Găsit serviciu {svc['name']} pe canal {port}")
            return port
    return None

def browse_and_download(client, start_path=""):
    cwd = start_path  # începe la root ""
    while True:
        try:
            entries = client.listdir(cwd)
            entriesXML = entries[1]  # al doilea element e XML-ul

            # Decode XML din bytes și parsează în array
            xml_str = entriesXML.decode("utf-8")
            root = ET.fromstring(xml_str)
            arrayXML = []
            for elem in root:
                arrayXML.append({
                    "type": elem.tag,
                    "name": elem.attrib.get("name"),
                    "size": int(elem.attrib.get("size", 0)),
                    "modified": elem.attrib.get("modified"),
                    "user_perm": elem.attrib.get("user-perm")
                })

        except Exception as e:
            print(f"[!] Nu pot lista '{cwd}': {e}")
            return

        print(f"\n=== Listing: /{cwd} ===")
        for idx, entry in enumerate(arrayXML, 1):
            name = entry["name"]
            is_dir = entry["type"] == "folder"
            mark = '/' if is_dir else ''
            size = entry["size"] / (1024 * 1024)  # convertește în MB

            print(f"  {idx}) {name}{mark} (f{size:.02f} mb)")
        print("  ..) Up one")
        print("  exit) Quit")

        choice = input("Your choice: ").strip()
        if choice == 'exit':
            return
        if choice == '..':
            cwd = os.path.dirname(cwd.rstrip('/'))
            continue
        if not choice.isdigit() or not (1 <= int(choice) <= len(arrayXML)):
            print("Invalid choice")
            continue

        sel = arrayXML[int(choice) - 1]
        sel_name = sel["name"]
        sel_type = sel["type"]
        import posixpath
        newpath = posixpath.join(cwd, sel_name)


        if sel_type == 'folder':
            cwd = newpath
        else:
            # Descarcă fișierul și ieșire
            local_dir = 'downloaded'
            os.makedirs(local_dir, exist_ok=True)
            local_file = local_dir + "/" + sel_name
            print(f"[+] Downloading '/{newpath}' → '{local_file}' …")
            try:
                op = client.get(newpath)
                content = op[1]
            except Exception as e:
                print(f"[!] Eroare la descărcare: {e}")
                return
            with open(local_file, 'wb') as f:
                f.write(content)
            print(f"[✓] Saved to {local_file}")


def send_file_via_obex(addr, filename):
    """Inițiază sesiune OBEX și trimite fișierul."""
    port = find_obex_channel(addr)
    if port is None:
        print("[!] Nu am găsit niciun serviciu OBEX pe dispozitiv.")
        return

    print(f"[+] Connecting OBEX to {addr}:{port} …")
    client = BrowserClient(addr, port)
    try:
        client.connect()
        print("[+] OBEX FTP connected")
        browse_and_download(client, "")
        # data = open(filepath, 'rb').read()
        # name = "fisier.txt"  # Numele fișierului pe care îl trimitem
        # resp = client.put(name, data)
        # if resp.code == 0x20:
        #     print("[✓] Fișier trimis cu succes.")
        # else:
        #     print(f"[!] Eroare la trimitere, cod răspuns OBEX: {resp.code}")
    except BluetoothError as e:
        print(f"[!] Bluetooth error: {e}")
    except OSError as e:
        print(f"[!] Eroare socket: {e}")
    except Exception as e:
        print(f"[!] Excepție neașteptată: {e}")
    finally:
        # Deconectăm doar dacă s-a putut crea socket-ul
        try:
            client.disconnect()
            print("[+] Deconectat OBEX.")
        except Exception:
            pass

if __name__ == "__main__":

    filepath = "C:\\Users\\flori\\Downloads\\salut.txt"

    # 1. Listăm dispozitive
    devices = list_devices(timeout=8)
    # 2. Alegem ținta
    target_addr = choose_device(devices)
    # 3. Trimitem fișierul
    send_file_via_obex(target_addr, filepath)
