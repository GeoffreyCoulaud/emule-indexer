# Documentation — emule-indexer

`emule-indexer` surveille en continu le réseau eMule (eD2k + Kad) pour retrouver les épisodes perdus
de la VF de *Keroro mission Titar*, en cataloguant les métadonnées disponibles au passage. Contrainte
de conception : **le sujet du catalogue est le fichier, jamais la personne** (pas de pistage, pas de
désanonymisation).

Cette doc est organisée **par audience**. Choisissez votre point d'entrée :

## Opérateur / hébergeur de nœud

Vous voulez **déployer et exploiter** un nœud (homelab, serveur) : monter la stack `docker compose`,
configurer le VPN, obtenir un High-ID, activer l'analyse antivirus (clamav), exposer les métriques,
fusionner plusieurs catalogues, valider votre config.

→ **[Runbook de déploiement](runbook-deployment.md)**

## Développeur / contributeur / CI

Vous **modifiez le code** ou montez la CI : comment lancer les suites de tests (gate par paquet +
suites d'intégration), leurs prérequis exacts, les pistes d'intégration continue, et l'architecture /
les décisions de conception.

- **[Guide des tests](testing-guide.md)** — toutes les suites (unitaire + intégration) + pistes CI +
  outils de diagnostic.
- **[Specs de conception](superpowers/specs/)** — le design MVP autoritatif (17 sections) et
  l'architecture (moteur de matching, hexagonal/Clean).
- Le **gate** (commandes de build/test/lint, règles dures) est décrit dans le `CLAUDE.md` à la racine.

## Historique / trace de décision

Le **pourquoi** des choix, jalon par jalon, et les plans d'implémentation exécutés.

- **[Handoffs](handoffs/)** — un guide de continuation par jalon (`<date ISO> - handoff - <contexte>.md`) ;
  le plus récent est le point d'entrée du contexte courant.
- **[Plans d'implémentation](superpowers/plans/)** — les plans exécutés en mode subagent-driven.
- **[Notes de référence](reference/)** — constats empiriques datés (richesse des champs EC, opcodes
  download, etc.).
