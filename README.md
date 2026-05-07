# Messagerie Chiffrée

Application de chat chiffrée de bout en bout entre deux machines, implémentant un protocole cryptographique custom inspiré d'AES.

---

## Sommaire

1. [Lancer l'application](#lancer-lapplication)
2. [Architecture des fichiers](#architecture-des-fichiers)
3. [Protocole de connexion](#protocole-de-connexion)
4. [Échange de clés — Diffie-Hellman](#échange-de-clés--diffie-hellman)
5. [Chiffrement des messages](#chiffrement-des-messages)
6. [Trame réseau](#trame-réseau)
7. [Intégrité et authentification](#intégrité-et-authentification)
8. [Failles et limites connues](#failles-et-limites-connues)

---

## Lancer l'application

### Prérequis

```
pip install customtkinter numpy
```

### Démarrage

**Sur la machine serveur :**
```
python server.py
```
→ Une popup demande le pseudo  
→ L'IP locale et le port s'affichent dans le terminal  
→ Le programme attend une connexion entrante  

**Sur la machine client :**
```
python client.py
```
→ Une popup demande l'IP du serveur  
→ Une popup demande le pseudo  
→ La connexion s'établit automatiquement  

Le chat s'ouvre dès que les deux parties sont connectées et que l'échange de clés est terminé.

> **Port utilisé :** 37859 (TCP)  
> Les deux machines doivent être sur le même réseau, ou le port doit être ouvert/forwardé.

---

## Architecture des fichiers

```
├── server.py            # Point d'entrée serveur (connexion, DH, échange pseudo)
├── client.py            # Point d'entrée client  (connexion, DH, échange pseudo)
├── interface.py         # Interface graphique (customtkinter) — ChatApp
├── aes.py               # Algorithme de chiffrement custom
├── keygen_server_side.py  # Génération de clé DH côté serveur
├── keygen_clt_side.py     # Génération de clé DH côté client
```

---

## Protocole de connexion

La connexion se déroule en 4 phases dans l'ordre suivant :

```
SERVEUR                                    CLIENT
  |                                          |
  |──── key_a (texte brut) ────────────────>|
  |<─── key_b (texte brut) ─────────────────|
  |                                          |
  |   [secret partagé calculé des deux côtés]
  |                                          |
  |──── pseudo serveur (chiffré) ──────────>|
  |<─── pseudo client  (chiffré) ───────────|
  |                                          |
  |   [chat chiffré commence]                |
```

`p` et `g` sont hardcodés identiquement des deux côtés (RFC 3526) — seules les clés publiques `key_a` et `key_b` transitent en clair. Tout ce qui suit est **chiffré**.

---

## Échange de clés — Diffie-Hellman

### Principe

Diffie-Hellman permet à deux parties de se mettre d'accord sur un secret commun **sans jamais l'envoyer sur le réseau**.

### Implémentation

`p` et `g` sont hardcodés dans les deux fichiers keygen — ce sont les paramètres standardisés **RFC 3526 Group 14** :

```
p = prime de 2048 bits (vérifié, utilisé dans TLS/SSH/VPN)
g = 2 (générateur standard pour ce groupe)
```

**Serveur** (`keygen_server_side.py`) :
```
a     = nombre secret aléatoire entre 2 et p-2 (~2048 bits, jamais envoyé)
key_a = pow(g, a, p)   → envoyé au client
```

**Client** (`keygen_clt_side.py`) :
```
b     = nombre secret aléatoire entre 2 et p-2 (~2048 bits, jamais envoyé)
key_b = pow(g, b, p)   → envoyé au serveur
```

**Secret partagé** (calculé indépendamment) :
```
Serveur : pow(key_b, a, p)
Client  : pow(key_a, b, p)
→ Les deux donnent le même résultat : g^(a×b) mod p
```

`pow(x, y, p)` utilise l'exponentiation modulaire rapide de Python — ne calcule jamais l'entier `x^y` en entier.

Ce secret partagé devient la base de dérivation des 4 clés de chiffrement.

---

## Chiffrement des messages

### Vue d'ensemble

Chaque message passe par un pipeline de chiffrement custom en 4 rounds, inspiré d'AES.

### 1. Dérivation des 4 clés

À partir du secret partagé `S`, 4 clés de 32 octets sont dérivées via SHA-256 :

```python
k1 = SHA256(S + 18)
k2 = SHA256(S + 61)
k3 = SHA256(S + 74)
k4 = SHA256(S + 3)
```

Seuls les 16 premiers octets de chaque clé sont utilisés, reshapés en matrice 4×4.

### 2. Mise en matrice

Le message (texte UTF-8) est converti en octets ASCII, paddé avec des espaces jusqu'à un multiple de 16, puis découpé en blocs de 16 octets reshapés en matrices 4×4 :

```
"Bonjour!" → [66, 111, 110, 106, 111, 117, 114, 33, 32, 32, 32, 32, 32, 32, 32, 32]
           → matrice numpy 4×4
```

### 3. Pipeline de chiffrement (par bloc)

Chaque bloc 4×4 passe dans la séquence suivante, **3 fois** puis une dernière XOR+S-box :

```
┌─────────────────────────────────────────┐
│  XOR avec clé k_n                       │
│  ↓                                      │
│  SubBytes  (S-box)                      │
│  ↓                                      │
│  ShiftRows (décalage de lignes)         │
│  ↓                                      │
│  MixColumns (multiplication matricielle)│
└─────────────────────────────────────────┘
     × 3 rounds  (k1→k2→k3)
puis :
     XOR k4 → SubBytes(sbox4) → fin
```

**Schéma complet :**
```
message_bloc
    │
    ▼
[XOR k1] → [sbox1] → [ShiftRows] → [MixColumns]
    │
    ▼
[XOR k2] → [sbox2] → [ShiftRows] → [MixColumns]
    │
    ▼
[XOR k3] → [sbox3] → [ShiftRows] → [MixColumns]
    │
    ▼
[XOR k4] → [sbox4]
    │
    ▼
bloc chiffré
```

### 4. SubBytes — S-boxes

4 paires de tables de substitution (S-box / inverse) de 256 entrées chacune, soit **8 tables** au total.  
Chaque octet est remplacé par sa valeur dans la table correspondante.  
Les tables sont des permutations aléatoires générées avec une graine fixe — leur inverse est calculé automatiquement.

```
sbox1[x] = y  →  sbox1bis[y] = x  (propriété d'inverse)
```

### 5. ShiftRows

Décalage circulaire de chaque ligne de la matrice :

```
Ligne 0 : pas de décalage
Ligne 1 : décalage gauche de 1
Ligne 2 : décalage gauche de 2
Ligne 3 : décalage gauche de 3
```

Inverse : décalage à droite de la même valeur.

### 6. MixColumns

Multiplication matricielle mod 256 sur chaque colonne :

```
nouvelle_colonne = colonne @ random_matrice  (mod 256)
```

Matrice utilisée :
```
[[5, 3, 4, 2],
 [3, 4, 3, 2],
 [2, 4, 1, 2],
 [2, 2, 2, 1]]
```

Son inverse mod 256 est précalculée et hardcodée pour le déchiffrement.  
Le déterminant de la matrice est impair (copremier avec 256), ce qui garantit l'existence de l'inverse modulaire.

### 7. Déchiffrement

Strictement l'inverse du chiffrement, opérations et clés dans l'ordre inverse :

```
bloc chiffré
    │
    ▼
[inv_sbox4]
    │
    ▼
[XOR k4] → [inv_MixColumns] → [inv_ShiftRows] → [inv_sbox3]
    │
    ▼
[XOR k3] → [inv_MixColumns] → [inv_ShiftRows] → [inv_sbox2]
    │
    ▼
[XOR k2] → [inv_MixColumns] → [inv_ShiftRows] → [inv_sbox1]
    │
    ▼
[XOR k1]
    │
    ▼
message original
```

---

## Trame réseau

### Format de chaque paquet chiffré

```
┌──────────────────────────────────────────────────────┐
│  4 octets        │  N octets                         │
│  longueur (big-  │  ciphertext                       │
│  endian uint32)  │  (blocs de 16 octets)             │
└──────────────────────────────────────────────────────┘
```

- **`longueur`** : taille du message original **avant padding** (permet de supprimer les espaces ajoutés)
- **`ciphertext`** : multiple de 16 octets (blocs 4×4)

### Contenu déchiffré de chaque message

```
┌────────────────────────────────────────────────────────┐
│  64 caractères hex    │ 1 char │  message               │
│  SHA-256(pseudo)      │  ":"   │  texte du message      │
└────────────────────────────────────────────────────────┘
```

Exemple (avant chiffrement) :
```
a3f2...c9d1:Salut, comment tu vas ?
```

### Échange des pseudos (au démarrage)

Même format que les messages, mais le payload déchiffré est **uniquement le pseudo** (pas de hash prefixe) :

```
┌──────────────┬──────────────────────────────┐
│  4 octets    │  N octets                    │
│  longueur    │  chiffrement(pseudo)          │
└──────────────┴──────────────────────────────┘
```

Ordre d'échange : serveur envoie en premier, client reçoit puis envoie.

### Buffer de réception

Buffer TCP fixé à **4096 octets**. Pour des messages très longs (> ~4000 caractères), le paquet pourrait être fragmenté par TCP et arriver en plusieurs `recv()` — cela n'est pas géré dans la version actuelle.

---

## Intégrité et authentification

### Mécanisme

À chaque message, l'expéditeur préfixe son message du hash de son pseudo :

```python
payload = SHA256(pseudo).hexdigest() + ":" + message
```

Le destinataire, qui connaît le pseudo de l'expéditeur (échangé au démarrage), recalcule `SHA256(pseudo_connu)` et compare :

- **Match** → message affiché
- **Pas de match** → message rejeté, avertissement affiché

### Ce que ça prouve

✅ Le message vient bien de quelqu'un qui connaît le pseudo de l'expéditeur  
✅ Le canal est déjà chiffré, donc le pseudo ne circule pas en clair après l'échange initial

### Ce que ça ne prouve pas

❌ Ce n'est pas une vraie signature cryptographique — `SHA256(pseudo)` est une valeur **fixe** pour toute la session, elle ne lie pas le hash au contenu du message. Un attaquant qui intercepte un message valide pourrait rejouer le même hash avec un message différent, si le chiffrement était cassé.

Un vrai HMAC serait : `HMAC(clé_secrète, message)` — ce qui lierait à la fois l'identité et le contenu.

---

## Failles et limites connues


### 🔴 Pas de protection contre le Man-in-the-Middle (MITM)

L'échange DH se fait en clair sans authentification des parties. Un attaquant entre les deux machines peut intercepter `key_a`, substituer sa propre clé, et déchiffrer/rechiffrer les messages de façon transparente.

**Fix** : ajouter un mécanisme d'authentification des clés publiques (certificats, clés prépartagées, SRP…).

### 🟡 Hash du pseudo statique

`SHA256(pseudo)` ne change pas pendant la session. Si la même valeur est reconnue dans plusieurs trames (une fois le chiffrement cassé), elle ne protège pas contre le replay.

**Fix** : utiliser `HMAC-SHA256(secret_partagé, message)` pour une authentification liée au contenu.

### 🟡 Pas de gestion de la fragmentation TCP

TCP est un protocole de flux. Un message peut arriver en plusieurs `recv()`. Si le message dépasse le buffer de 4096 octets, le déchiffrement échouera silencieusement.

**Fix** : lire exactement `longueur` octets après avoir reçu les 4 premiers, en bouclant si nécessaire.

### 🟡 S-boxes et MixColumns statiques

Les tables de substitution et la matrice MixColumns sont hardcodées et identiques pour tous les utilisateurs. Un attaquant connaissant le code source connaît ces tables.

En AES, les S-boxes sont publiques aussi — la sécurité repose sur les clés, pas sur le secret des tables. Ici c'est pareil, mais la conception custom n'a pas été auditée comme AES.

### 🟡 Taille des clés DH utilisée pour AES

Seuls les **16 premiers octets** du digest SHA-256 (32 octets) sont utilisés comme clé. C'est 128 bits — correct, mais on perd 128 bits d'entropie potentielle.

### 🟢 Points positifs

- Le secret DH ne transite jamais sur le réseau
- Les pseudos sont échangés sur le canal chiffré
- Chaque message utilise la même clé dérivée (pas de nonce/IV) — pas de réutilisation de nonce puisqu'il n'y en a pas, mais cela signifie que deux messages identiques produiront le même ciphertext
- L'interface est thread-safe (mise à jour UI via `root.after()`)
- Paramètres DH standardisés RFC 3526 — prime 2048 bits, exposants ~2048 bits
