import socket
import customtkinter as ctk
import keygen_server_side
import aes
from interface import ChatApp


def main():
    pseudo = ctk.CTkInputDialog(text="Votre pseudo :", title="Pseudo").get_input()
    if not pseudo:
        return

    port = 37859
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    s_temp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s_temp.connect(("8.8.8.8", 80))
        ip_locale = s_temp.getsockname()[0]
        s_temp.close()
    except:
        ip_locale = "127.0.0.1"

    server_sock.bind(('0.0.0.0', port))
    server_sock.listen(1)
    print(f"IP : {ip_locale} | Port : {port} — En attente de connexion...")

    conn, addr = server_sock.accept()

    # Diffie-Hellman
    key_a = keygen_server_side.genKeyServ1()
    conn.send(str(key_a).encode())
    data_b = conn.recv(4096).decode().strip()
    keygen_server_side.recup_key_b(int(data_b))
    cle_finale = keygen_server_side.genKeyServ2()

    # Échange des pseudos
    ct, longueur = aes.chiffrement(pseudo, cle_finale)
    conn.send(longueur.to_bytes(4, 'big') + ct)
    data = conn.recv(4096)
    pseudo_distant = aes.dechiffrement(data[4:], cle_finale, int.from_bytes(data[:4], 'big'))

    app = ChatApp(conn, cle_finale, pseudo, pseudo_distant)
    app.mainloop()
    conn.close()
    server_sock.close()


if __name__ == "__main__":
    main()
