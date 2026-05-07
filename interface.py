import threading
import hashlib
import customtkinter as ctk
import aes

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class ChatApp(ctk.CTk):
    def __init__(self, conn, cle_finale, pseudo, pseudo_distant):
        super().__init__()
        self.conn = conn
        self.cle_finale = cle_finale
        self.pseudo = pseudo
        self.pseudo_distant = pseudo_distant
        self.hash_distant = hashlib.sha256(pseudo_distant.encode()).hexdigest()

        self.title(f"Chat — {pseudo}")
        self.geometry("520x420")

        self.zone_chat = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.zone_chat.pack(padx=10, pady=10, fill="both", expand=True)

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(padx=10, pady=(0, 10), fill="x")

        self.entry = ctk.CTkEntry(frame, placeholder_text="Message...")
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self.envoyer)

        ctk.CTkButton(frame, text="Envoyer", width=90, command=self.envoyer, fg_color="#2d8a4e", hover_color="#1f6b3a").pack(side="right")

        threading.Thread(target=self.reception_loop, daemon=True).start()

    def afficher(self, texte):
        self.zone_chat.configure(state="normal")
        self.zone_chat.insert("end", texte + "\n")
        self.zone_chat.configure(state="disabled")
        self.zone_chat.see("end")

    def envoyer(self, event=None):
        msg = self.entry.get().strip()
        if not msg:
            return
        self.entry.delete(0, "end")
        payload = hashlib.sha256(self.pseudo.encode()).hexdigest() + ":" + msg
        ct, longueur = aes.chiffrement(payload, self.cle_finale)
        self.conn.send(longueur.to_bytes(4, "big") + ct)
        self.afficher(f"Moi ({self.pseudo}) : {msg}")

    def reception_loop(self):
        while True:
            try:
                data = self.conn.recv(4096)
                if not data:
                    break
                longueur = int.from_bytes(data[:4], "big")
                payload = aes.dechiffrement(data[4:], self.cle_finale, longueur)
                hash_recu, msg = payload.split(":", 1)
                if hash_recu != self.hash_distant:
                    self.after(0, lambda: self.afficher("[⚠ MESSAGE REJETÉ]"))
                    continue
                self.after(0, lambda m=msg: self.afficher(f"{self.pseudo_distant} : {m}"))
            except:
                break
