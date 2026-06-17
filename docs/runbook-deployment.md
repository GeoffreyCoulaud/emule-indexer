# Runbook de déploiement — emule-indexer

Ce guide explique comment **monter la stack `docker compose` d'emule-indexer** sur une machine
(homelab, serveur) et la voir tourner — le **chemin direct**, rien de plus. Le sujet du catalogue
reste **le fichier, jamais la personne**.

> **À qui ça s'adresse, franchement.** Ce guide suppose que vous êtes **à l'aise avec un terminal et
> avec Docker**, et il est **orienté Linux/serveur** : chaque étape passe par des commandes et
> l'édition de fichiers de configuration. Si ce n'est pas votre cas, ce déploiement n'est pas (encore)
> pour vous. Bonne nouvelle : l'état par défaut (**Low-ID**) suffit largement à contribuer — aucun
> réglage réseau avancé n'est nécessaire. *(Sous Docker Desktop Windows/macOS, attendez-vous à des
> écarts non couverts ici ; le High-ID automatique notamment n'y est pas disponible.)*

> Une fois le nœud monté : pour l'**exploiter et le régler** (cycle de vie, High-ID, analyse
> antivirus, métriques, durcissement gVisor, outils de catalogue), voir le
> **[Runbook d'administration](runbook-administration.md)** ; en cas de souci, le
> **[Runbook de dépannage](runbook-troubleshooting.md)**.

Deux profils de déploiement :

- **observer** — recherche + catalogage + notifications. Ne télécharge **rien**.
- **full** — observer + téléchargement automatique + vérification isolée des fichiers reçus.

---

## Glossaire (sigles utilisés ici)

| Terme | Signification |
|-------|---------------|
| **VPN** | Tunnel chiffré qui masque l'IP de la machine. Ici assuré par le conteneur **gluetun**. |
| **eD2k** | Le réseau eDonkey2000 (serveurs centralisés). L'un des deux réseaux que surveille le projet. |
| **Kad** | Réseau Kademlia (décentralisé, sans serveur). Le second réseau surveillé. |
| **EC** | *External Connection* — le protocole par lequel le crawler pilote le client aMule (`amuled`). |
| **Low-ID / High-ID** | Statut de joignabilité sur eD2k. **High-ID** = la machine est joignable depuis l'extérieur (meilleures sources). **Low-ID** = elle ne l'est pas (fonctionne quand même, mais sous-optimal). |
| **quarantine** | Dossier isolé où atterrissent les fichiers téléchargés, **avant** vérification. |
| **GHCR** | GitHub Container Registry — l'endroit où sont publiées les images Docker du projet. |

---

## Prérequis

- **Docker** + **docker compose v2** (vérifier : `docker compose version`).
- Un compte chez un **fournisseur VPN WireGuard** (voir l'encadré ci-dessous), d'où vous tirez une
  **clé privée WireGuard**.
- Le device **`/dev/net/tun`** disponible sur l'hôte (gluetun en a besoin pour monter le tunnel).
- *(Optionnel)* le runtime **gVisor** (`runsc`), si vous voulez le durcissement noyau supplémentaire
  de `compose.hardening.yml` — voir le [runbook d'administration](runbook-administration.md). Sans
  gVisor, n'utilisez simplement pas ce fichier : la base est déjà durcie.

> ### Choix du fournisseur VPN
> N'importe quel fournisseur **VPN WireGuard** supporté par gluetun fait tourner la stack. Le
> fournisseur se choisit dans `compose.yaml` (`VPN_SERVICE_PROVIDER`) ; les secrets vont dans `.env`
> (voir Démarrage rapide). Vous tournerez en **Low-ID** — l'état normal, **suffisant pour
> contribuer**. Viser le **High-ID** (joignabilité optimale) est une optimisation **optionnelle**,
> traitée dans le [runbook d'administration](runbook-administration.md) ; **le choix du fournisseur y
> joue**, donc lisez-la *avant* de choisir si le High-ID vous intéresse.

---

## Démarrage rapide

### 1. Récupérer le dépôt et préparer les secrets

Récupérez une copie du dépôt (clone Git ou archive), placez-vous à sa racine, puis copiez le modèle
de secrets :

```bash
cp .env.example .env
```

Renseignez dans `.env` :

- `WIREGUARD_PRIVATE_KEY` — la clé privée WireGuard de votre fournisseur VPN.
- `SERVER_COUNTRIES` — le pays de sortie souhaité (ex. `Switzerland`).
- `AMULE_EC_PASSWORD` — un mot de passe que **vous** choisissez ; il protège le canal EC entre le
  crawler et amuled.

Le `.env` est **gitignoré** : il ne sera jamais committé.

> Si votre fournisseur n'est pas ProtonVPN, ajustez aussi `VPN_SERVICE_PROVIDER` dans `compose.yaml`
> et, selon le fournisseur, les variables WireGuard correspondantes attendues par gluetun.

### 2. Configurer le crawler

```bash
cp config/local.example.yaml config/local.yaml
```

Renseignez dans `config/local.yaml` :

- `amules[].host: gluetun`, `amules[].port: 4712`, `amules[].password:` = la valeur de
  `AMULE_EC_PASSWORD`. *(L'hôte EC est `gluetun`, car amuled partage son réseau.)*
- `catalog_db_path: /data/catalog/catalog.db` et `local_db_path: /data/local/local.db`.
- **Mode full uniquement** : décommentez le bloc `download_endpoint`, mettez `staging_dir:
  /data/quarantine` + `quarantine_dir: /data/quarantine`, et `verifier_url: http://verifier:8000`.
  *(C'est la présence de `verifier_url` qui bascule le crawler en mode full.)*

> #### Contraintes du mode full (à respecter pour que le téléchargement marche)
> Quatre conditions pour que la chaîne téléchargement → quarantaine → vérification fonctionne :
>
> 1. `staging_dir` = `quarantine_dir` = l'**IncomingDir d'amuled** (le même volume `/data/quarantine`)
>    — configurez l'IncomingDir d'amuled sur ce dossier, **pas** son TempDir.
> 2. Ce volume sur un **FS Linux** (ext4/overlay…), pas vfat/NTFS/HFS.
> 3. **Pas de catégories** amuled (une catégorie redirigerait le fichier).
> 4. amuled **dédié** au crawler, **jeu partagé restreint** (ne pointez pas une grosse bibliothèque
>    partagée pré-existante).

### 3. Récupérer (ou construire) les images

Tirer depuis GHCR (recommandé) :

```bash
docker compose --profile full pull   # --profile requis : tous les services sont profilés
```

Ou construire localement :

```bash
docker compose --profile full build
```

> **Astuce pré-vol** : avant de démarrer, vous pouvez valider vos configs sans rien lancer avec
> `uv run python -m emule_indexer validate-config` (voir [runbook d'administration](runbook-administration.md),
> « Outils de catalogue »).

### 4. Démarrer

Observer (pas de téléchargement) :

```bash
docker compose --profile observer up -d
```

Full (avec téléchargement + vérification) :

```bash
docker compose --profile full up -d
```

> En full, le crawler **vérifie que le verifier répond** au démarrage et **refuse de démarrer** s'il
> est injoignable (pas de téléchargement sans vérification). Si le verifier n'est pas encore prêt, le
> crawler s'arrête et son `restart: unless-stopped` le relance jusqu'à ce que le verifier soit sain.
> Pour éviter ces redémarrages, démarrez le verifier d'abord :
> ```bash
> docker compose --profile full up -d verifier
> docker compose --profile full up -d
> ```

> En full, l'**analyse antivirus (clamav)** est active par défaut. Au premier démarrage, sa base de
> signatures se synchronise (quelques minutes) et les fichiers ressortent `suspicious` en attendant —
> c'est **transitoire**. Détails et réglage dans le [runbook d'administration](runbook-administration.md).

### 5. Vérifier que ça tourne

```bash
docker compose logs -f crawler                  # suivre les logs du crawler
docker compose exec crawler ls /data            # /data/catalog, /data/local, /data/quarantine
```

Vous devriez voir le cycle s'enchaîner sur le vrai réseau eMule : recherche → (en full)
téléchargement → quarantaine → vérification.

---

## Premier démarrage : amorçage automatique du réseau

Au **tout premier run**, amuled récupère **automatiquement** sa liste de serveurs eD2k (`server.met`)
et de nœuds Kad (`nodes.dat`) pour se connecter — patientez quelques instants après le démarrage,
vous n'avez rien à faire. *(Si amuled ne se connecte à aucun réseau, voir le
[runbook de dépannage](runbook-troubleshooting.md).)*

---

## Low-ID : c'est normal

Par défaut la stack tourne en **Low-ID**, et **ce n'est pas une panne** :

- La recherche, le catalogage et le téléchargement **fonctionnent**.
- Seule la joignabilité est sous-optimale (moins de sources directes).

Ne traitez donc pas un statut « Low-ID » dans les logs comme une erreur à corriger.

Le **High-ID** (joignabilité optimale, plus de sources) est une optimisation **optionnelle** — son
activation, ses prérequis et ses compromis (y compris l'ouverture d'un port et ses risques) sont
décrits dans le [runbook d'administration](runbook-administration.md).

---

## Pour aller plus loin

- **[Runbook de dépannage](runbook-troubleshooting.md)** — symptômes courants et résolutions (amuled
  ne se connecte pas, fichier sain en `suspicious`, port-sync inopérant, droits de volume…).
- **[Runbook d'administration](runbook-administration.md)** — exploiter et régler un nœud monté :
  cycle de vie (arrêt/mise à jour/persistance), High-ID (optionnel), analyse antivirus (clamav),
  métriques Prometheus, durcissement gVisor, outils de catalogue, limites connues.
- **[Guide des tests](testing-guide.md)** — valider/tester en profondeur (suites d'intégration,
  smoke, CI).
