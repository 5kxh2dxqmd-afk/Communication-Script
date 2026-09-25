import socket
import threading
import base64
import time
from collections import defaultdict
from tkinter import *
from cryptography.fernet import Fernet

# ---------- IP Viewer ----------
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "Unknown"

# ---------- Chat Encryption ----------
KEY = base64.urlsafe_b64encode(b"binArynUmberSARethebestyay^&$%*&")
f = Fernet(KEY)

def caesar_shift(text, shift=3):
    out = []
    for ch in text:
        if ch.isalpha():
            base = ord('A') if ch.isupper() else ord('a')
            out.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            out.append(ch)
    return "".join(out)

def to_binary(text):
    return " ".join(format(ord(c), "08b") for c in text)

def from_binary(binary_text):
    parts = binary_text.split()
    return "".join(chr(int(b, 2)) for b in parts)

def encrypt_message(msg: str) -> bytes:
    shifted = caesar_shift(msg, 3)
    binary = to_binary(shifted)
    return f.encrypt(binary.encode())

def decrypt_message(token: bytes) -> str:
    binary = f.decrypt(token).decode()
    ascii_text = from_binary(binary)
    return caesar_shift(ascii_text, -3)

PORT = 7879

def run_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", PORT))
    server.listen()

    clients = {}  # sock -> {"username": str, "ip": str, "room": str}
    rooms = defaultdict(set)
    rooms["Lobby"] = set()

    bans_user = set()
    bans_ip = set()
    latencies = {}  # sock -> ms

    root = Tk()
    root.title("Admin Control Panel – Admin")
    root.geometry("900x650")

    # Show server IP
    Label(root, text=f"Server IP (connect to this): {get_local_ip()}").pack(anchor="w")

    Label(root, text="Admin inbox (@admin or /admin):").pack(anchor="w")
    inbox_box = Listbox(root, height=6)
    inbox_box.pack(fill=X)

    # ---------- Users list ----------
    user_frame = Frame(root)
    user_frame.pack(fill=X, pady=5)

    Label(user_frame, text="Users:").pack(side=LEFT)
    user_list = Listbox(user_frame, height=10)
    user_list.pack(side=LEFT, fill=X, expand=True)
    user_scroll = Scrollbar(user_frame, command=user_list.yview)
    user_scroll.pack(side=LEFT, fill=Y)
    user_list.config(yscrollcommand=user_scroll.set)

    def refresh_users():
        user_list.delete(0, END)
        for sock, info in clients.items():
            ping = latencies.get(sock, "N/A")
            user_list.insert(END, f'{info["username"]} ({info["room"]}) - {ping} ms')

    def broadcast_user_list():
        usernames = [info["username"] for info in clients.values()]
        if "Admin" not in usernames:
            usernames.append("Admin")
        payload = "SYS|USERS|" + ",".join(usernames)
        encrypted = encrypt_message(payload)
        for sock in list(clients.keys()):
            try:
                sock.send(encrypted)
            except:
                pass

    # ---------- Ping ----------
    def ping_all_clients():
        now = time.time()
        payload = f"SYS|PING|{now}"
        encrypted = encrypt_message(payload)
        for sock in list(clients.keys()):
            try:
                sock.send(encrypted)
            except:
                pass
        inbox_box.insert(END, "Ping sent to all clients")

    Button(root, text="Ping All Clients", command=ping_all_clients).pack(pady=5)

    # ---------- Latency panel ----------
    latency_win = None
    latency_list = None

    def open_latency_panel():
        nonlocal latency_win, latency_list
        if latency_win is not None:
            return
        latency_win = Toplevel(root)
        latency_win.title("Client Latency Panel")
        latency_win.geometry("300x300")
        latency_win.attributes("-topmost", True)

        Label(latency_win, text="Client Latencies (ms):").pack(anchor="w")
        latency_list = Listbox(latency_win, height=12)
        latency_list.pack(fill=BOTH, expand=True)

        def refresh_latency_panel():
            if latency_list is None:
                return
            latency_list.delete(0, END)
            for sock, info in clients.items():
                ping = latencies.get(sock, "N/A")
                latency_list.insert(END, f'{info["username"]}: {ping} ms')
            latency_win.after(1000, refresh_latency_panel)

        latency_win.after(1000, refresh_latency_panel)

        def on_close():
            nonlocal latency_win
            latency_win.destroy()
            latency_win = None

        latency_win.protocol("WM_DELETE_WINDOW", on_close)

    Button(root, text="Open Latency Panel", command=open_latency_panel).pack(pady=5)
    # ---------- Rooms ----------
    room_frame = Frame(root)
    room_frame.pack(fill=X, pady=5)

    Label(room_frame, text="Rooms:").pack(side=LEFT)
    room_list = Listbox(room_frame, height=5)
    room_list.pack(side=LEFT, fill=X, expand=True)
    room_scroll = Scrollbar(room_frame, command=room_list.yview)
    room_scroll.pack(side=LEFT, fill=Y)
    room_list.config(yscrollcommand=room_scroll.set)

    def refresh_rooms():
        room_list.delete(0, END)
        for r in rooms.keys():
            room_list.insert(END, r)

    refresh_rooms()

    room_ctrl = Frame(root)
    room_ctrl.pack(fill=X)

    new_room_entry = Entry(room_ctrl)
    new_room_entry.pack(side=LEFT)

    def add_room():
        name = new_room_entry.get().strip()
        if name and name not in rooms:
            rooms[name] = set()
            refresh_rooms()
        new_room_entry.delete(0, END)

    def del_room():
        sel = room_list.curselection()
        if not sel:
            return
        room_name = room_list.get(sel[0])
        if room_name == "Lobby":
            return
        for sock in list(rooms[room_name]):
            rooms[room_name].remove(sock)
            rooms["Lobby"].add(sock)
            clients[sock]["room"] = "Lobby"
        del rooms[room_name]
        refresh_rooms()
        refresh_users()
        broadcast_user_list()

    Button(room_ctrl, text="Add room", command=add_room).pack(side=LEFT)
    Button(room_ctrl, text="Delete room", command=del_room).pack(side=LEFT)

    # ---------- User controls ----------
    user_ctrl = Frame(root)
    user_ctrl.pack(fill=X, pady=5)

    def move_user_to_room():
        sel_user = user_list.curselection()
        sel_room = room_list.curselection()
        if not sel_user or not sel_room:
            return
        sock = list(clients.keys())[sel_user[0]]
        target_room = room_list.get(sel_room[0])
        old_room = clients[sock]["room"]
        rooms[old_room].discard(sock)
        rooms[target_room].add(sock)
        clients[sock]["room"] = target_room
        refresh_users()
        broadcast_user_list()

    def kick_user():
        sel_user = user_list.curselection()
        if not sel_user:
            return
        sock = list(clients.keys())[sel_user[0]]
        info = clients[sock]
        try:
            sock.close()
        except:
            pass
        rooms[info["room"]].discard(sock)
        del clients[sock]
        refresh_users()
        broadcast_user_list()

    def ban_user():
        sel_user = user_list.curselection()
        if not sel_user:
            return
        sock = list(clients.keys())[sel_user[0]]
        info = clients[sock]
        bans_user.add(info["username"])
        bans_ip.add(info["ip"])
        try:
            sock.close()
        except:
            pass
        rooms[info["room"]].discard(sock)
        del clients[sock]
        refresh_users()
        broadcast_user_list()

    def unban_user():
        win = Toplevel(root)
        win.title("Unban user")
        Label(win, text="Username to unban:").pack()
        e = Entry(win)
        e.pack()

        def do_unban():
            name = e.get().strip()
            bans_user.discard(name)
            win.destroy()

        Button(win, text="Unban", command=do_unban).pack()

    Button(user_ctrl, text="Move to room", command=move_user_to_room).pack(side=LEFT)
    Button(user_ctrl, text="Kick", command=kick_user).pack(side=LEFT)
    Button(user_ctrl, text="Ban", command=ban_user).pack(side=LEFT)
    Button(user_ctrl, text="Unban", command=unban_user).pack(side=LEFT)

    # ---------- Admin chat ----------
    admin_chat_win = None
    admin_msg_labels = [None, None, None]
    admin_all_entry = None
    admin_pm_entry = None
    admin_target_var = StringVar(root)
    admin_target_var.set("Select user")
    admin_target_menu = None

    def refresh_target_menu():
        if admin_target_menu is None:
            return
        menu = admin_target_menu["menu"]
        menu.delete(0, "end")
        menu.add_command(label="Select user", command=lambda: admin_target_var.set("Select user"))
        for info in clients.values():
            name = info["username"]
            menu.add_command(label=name, command=lambda v=name: admin_target_var.set(v))

    def update_admin_chat_display(text):
        if admin_chat_win is None:
            return
        old2 = admin_msg_labels[1].cget("text")
        old1 = admin_msg_labels[0].cget("text")
        admin_msg_labels[2].config(text=old2)
        admin_msg_labels[1].config(text=old1)
        admin_msg_labels[0].config(text=text)

    def open_admin_chat():
        nonlocal admin_chat_win, admin_msg_labels, admin_all_entry, admin_pm_entry, admin_target_menu
        if admin_chat_win is not None:
            return

        admin_chat_win = Toplevel(root)
        admin_chat_win.title("Admin Chat – Admin")
        admin_chat_win.geometry("500x350")
        admin_chat_win.attributes("-topmost", True)

        l1 = Label(admin_chat_win, text="Msg 1:", anchor="w")
        l2 = Label(admin_chat_win, text="Msg 2:", anchor="w")
        l3 = Label(admin_chat_win, text="Msg 3:", anchor="w")
        l1.pack(fill=X)
        l2.pack(fill=X)
        l3.pack(fill=X)
        admin_msg_labels = [l1, l2, l3]

        Label(admin_chat_win, text="To everyone:").pack(anchor="w")
        admin_all_entry = Entry(admin_chat_win)
        admin_all_entry.pack(fill=X)

        Label(admin_chat_win, text="To specific user:").pack(anchor="w")
        admin_pm_entry = Entry(admin_chat_win)
        admin_pm_entry.pack(fill=X)

        admin_target_menu = OptionMenu(admin_chat_win, admin_target_var, "Select user")
        admin_target_menu.pack()

        def send_admin_all(event=None):
            msg = admin_all_entry.get().strip()
            if not msg:
                return
            full = f"Admin: {msg}"
            encrypted = encrypt_message(f"ALL|{full}")
            for sock in list(clients.keys()):
                try:
                    sock.send(encrypted)
                except:
                    pass
            update_admin_chat_display(full)
            admin_all_entry.delete(0, END)

        def send_admin_pm():
            msg = admin_pm_entry.get().strip()
            target = admin_target_var.get()
            if not msg or target == "Select user":
                return
            full = f"Admin -> {target}: {msg}"
            encrypted = encrypt_message(f"PM|{full}")
            for sock, info in clients.items():
                if info["username"] == target:
                    try:
                        sock.send(encrypted)
                    except:
                        pass
                    break
            update_admin_chat_display(full)
            admin_pm_entry.delete(0, END)

        def admin_refresh_users():
            refresh_users()
            refresh_target_menu()
            broadcast_user_list()
            update_admin_chat_display("Admin refreshed user list")

        admin_all_entry.bind("<Return>", send_admin_all)
        Button(admin_chat_win, text="Send to everyone", command=send_admin_all).pack()
        Button(admin_chat_win, text="Send to user", command=send_admin_pm).pack()
        Button(admin_chat_win, text="Refresh Users", command=admin_refresh_users).pack()

        def on_close():
            nonlocal admin_chat_win
            admin_chat_win.destroy()
            admin_chat_win = None

        admin_chat_win.protocol("WM_DELETE_WINDOW", on_close)

    Button(root, text="Open Admin Chat", command=open_admin_chat).pack(pady=5)

    # ---------- Join popup ----------
    def show_join_popup(sock, username, ip):
        win = Toplevel(root)
        win.title("Join request")
        win.attributes("-topmost", True)
        win.geometry("300x120+0+0")

        Label(win, text=f'User "{username}" from {ip}" wants to join').pack()

        def accept():
            if username in bans_user or ip in bans_ip:
                try:
                    sock.send(encrypt_message("SYS|REJECT"))
                    sock.close()
                except:
                    pass
            else:
                clients[sock] = {"username": username, "ip": ip, "room": "Lobby"}
                rooms["Lobby"].add(sock)
                refresh_users()
                refresh_target_menu()
                broadcast_user_list()
                try:
                    sock.send(encrypt_message("SYS|ACCEPT"))
                except:
                    pass
            win.destroy()

        def reject():
            try:
                sock.send(encrypt_message("SYS|REJECT"))
            except:
                pass
            try:
                sock.close()
            except:
                pass
            win.destroy()

        Button(win, text="Accept", command=accept).pack(side=LEFT)
        Button(win, text="Reject", command=reject).pack(side=LEFT)
    # ---------- Networking / Main Handler ----------
    def handle_client(sock, addr):
        ip = addr[0]
        try:
            username = sock.recv(1024).decode().strip()
        except:
            sock.close()
            return
        if not username:
            sock.close()
            return

        # Ask admin to approve join
        root.after(0, lambda: show_join_popup(sock, username, ip))

        while True:
            try:
                encrypted = sock.recv(4096)
                if not encrypted:
                    break

                text = decrypt_message(encrypted)

                # ---------- PING / LATENCY ----------
                if text.startswith("SYS|PONG|"):
                    parts = text.split("|")
                    if len(parts) >= 4:
                        try:
                            rtt_ms = float(parts[3])
                        except:
                            rtt_ms = None
                        if rtt_ms is not None:
                            latencies[sock] = round(rtt_ms, 1)
                            inbox_box.insert(END, f'Latency {username}: {rtt_ms:.1f} ms')
                            refresh_users()
                    continue

                if text == "SYS|REFRESH":
                    broadcast_user_list()
                    continue

                # ---------- ADMIN MESSAGES ----------
                if text.lower().startswith("@admin") or text.lower().startswith("/admin"):
                    inbox_box.insert(END, text)
                    continue

                # ---------- BROADCAST ----------
                if text.startswith("ALL|"):
                    content = text[4:]
                    update_admin_chat_display(content)
                    if sock in clients:
                        room = clients[sock]["room"]
                        for other in list(rooms[room]):
                            if other != sock:
                                try:
                                    other.send(encrypted)
                                except:
                                    pass
                    continue

                # ---------- PRIVATE MESSAGE ----------
                if text.startswith("PM|"):
                    content = text[3:]
                    update_admin_chat_display(content)

                    # Extract target name
                    target_name = None
                    if "->" in content:
                        try:
                            sender_part, rest = content.split("->", 1)
                            target_part, msg_part = rest.split(":", 1)
                            target_name = target_part.strip()
                        except:
                            target_name = None

                    if target_name:
                        for other, info in clients.items():
                            if info["username"] == target_name:
                                try:
                                    other.send(encrypted)
                                except:
                                    pass
                                break
                    continue

                # ---------- SERVER RECEIVES PING ----------
                if text.startswith("SYS|PING|"):
                    ts = float(text.split("|")[2])
                    now = time.time()
                    rtt = (now - ts) * 1000
                    pong = f"SYS|PONG|{ts}|{rtt}"
                    sock.sendall(encrypt_message(pong))
                    continue

            except:
                break

        # ---------- CLEANUP ON DISCONNECT ----------
        if sock in clients:
            info = clients[sock]
            rooms[info["room"]].discard(sock)
            del clients[sock]
            refresh_users()
            refresh_target_menu()
            broadcast_user_list()

        try:
            sock.close()
        except:
            pass

    # ---------- Accept Loop ----------
    def accept_loop():
        while True:
            client, addr = server.accept()
            threading.Thread(target=handle_client, args=(client, addr), daemon=True).start()

    threading.Thread(target=accept_loop, daemon=True).start()
    root.mainloop()

# ---------- MAIN ----------
if __name__ == "__main__":
    run_server()
