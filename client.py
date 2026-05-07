import socket
import customtkinter as ctk
import keygen_clt_side
import aes
from interface import ChatApp


def main():
    ip = ctk.CTkInputDialog(text="IP du serveur :", title="Connexion").get_input()
    pseudo = ctk.CTkInputDialog(text="Votre pseudo :", title="Pseudo").get_input()
    if not ip or not pseudo:
        return

    port = 37859
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        conn.connect((ip, port))

        # Diffie-Hellman
        key_a = int(conn.recv(4096).decode().strip())
        keygen_clt_side.recup_key_a(key_a)
        conn.send(str(keygen_clt_side.genKeyClt1()).encode())
        cle_finale = keygen_clt_side.genKeyClt2()

        # Échange des pseudos
        data = conn.recv(4096)
        pseudo_distant = aes.dechiffrement(data[4:], cle_finale, int.from_bytes(data[:4], 'big'))
        ct, longueur = aes.chiffrement(pseudo, cle_finale)
        conn.send(longueur.to_bytes(4, 'big') + ct)

        app = ChatApp(conn, cle_finale, pseudo, pseudo_distant)
        app.mainloop()

    except Exception as e:
        print(f"Erreur : {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
