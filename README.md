# Omarchy ScreenPad

Un petit plugin pour régler la luminosité matérielle du ScreenPad Plus ASUS
depuis la barre Omarchy Quattro. Version : 0.1.1.

## Installation

Prérequis : Omarchy Quattro 4.x, Quickshell, Python 3 et `brightnessctl`.
Le noyau doit exposer `/sys/class/backlight/asus_screenpad` ou l’ancien
`/sys/class/leds/asus::screenpad`. Aucun module noyau n’est installé.

```sh
omarchy plugin add https://github.com/pinpin-http/omarchy-screenpad.git --enable
```

Pour travailler sur le code local :

```sh
git clone https://github.com/pinpin-http/omarchy-screenpad.git
cd omarchy-screenpad
./install.sh
```

L’installateur local copie les fichiers dans
`~/.config/omarchy/plugins/soheib.screenpad`, sauvegarde `shell.json`,
puis place le bouton à côté du widget Display. Elle ne demande pas sudo.
Relancer l’installation applique les mises à jour du code local.

### Démarrage automatique

L’activation est enregistrée dans `~/.config/omarchy/shell.json` : le plugin
est rechargé à chaque ouverture de session avec la barre Omarchy. Aucun
autostart ou service supplémentaire n’est nécessaire. Si le pilote ScreenPad
arrive après la barre, le plugin le détecte lors de la lecture suivante.

```sh
omarchy plugin enable soheib.screenpad --before omarchy.monitor
```

## Utilisation

- Clic : panneau avec curseur, préréglages 25/50/75/100 % et marche/arrêt.
- Molette sur le bouton : luminosité par pas de 5 %.
- Dans le panneau : gauche/droite pour ±5 %, Entrée/Espace pour marche/arrêt,
  Échap pour fermer.
- L’arrêt conserve la dernière luminosité non nulle dans
  `$XDG_STATE_HOME/omarchy-screenpad` (par défaut `~/.local/state/omarchy-screenpad`).
- Le curseur ne descend pas sous 1 % ; l’arrêt utilise un bouton séparé.

Le contrôleur cible **uniquement** le pilote ASUS ScreenPad. Il appelle
`brightnessctl` sans shell et utilise les permissions de la session logind.
Il ne lance aucun service système, ne modifie aucune règle udev et n’accorde
aucun accès sudo. Les réglages faits dans une autre application sont relus
toutes les trois secondes (une seconde quand le panneau est ouvert).

```sh
./screenpadctl status
./screenpadctl set 50
./screenpadctl toggle
omarchy-shell shell summon soheib.screenpad '{}'
omarchy-shell shell hide soheib.screenpad
omarchy plugin disable soheib.screenpad
```

L’IPC de diagnostic est propre à chaque écran de barre, par exemple :
`omarchy-shell screenpad-eDP-1 state` et
`omarchy-shell screenpad-eDP-1 brightness 50`.

## Validation et diffusion

```sh
omarchy plugin validate ~/.config/omarchy/plugins/soheib.screenpad
python3 -m unittest discover -s tests -v
```

Prototype développé sur un ASUS ZenBook UX482EG, Omarchy 4.0.4,
Quickshell 0.3.1 et noyau 7.2.5. L’installation locale reste spécifique à
Omarchy ; le CLI `screenpadctl` fonctionne indépendamment de la barre.
La compatibilité avec les autres modèles et l’ancien pilote LED reste à
tester. Le rappel de luminosité concerne marche/arrêt ; la restauration au
démarrage est laissée au système.

Le dossier `packaging/` contient le `PKGBUILD` et `.SRCINFO`. Le paquet
utilise l’archive de version GitHub avec vérification SHA-256. Pour le construire :

```sh
cd packaging
makepkg -s
```

La soumission AUR reste à faire après validation sur quelques sessions et
après un redémarrage complet de la machine. Le dépôt GitHub est public ;
la création du dépôt ne publie pas automatiquement le paquet dans l’AUR.

Le paquet place les sources sous `/usr/share/omarchy-screenpad` et fournit
`omarchy-screenpad-install` pour l’activation par l’utilisateur, sans modifier
automatiquement son dossier personnel à l’installation pacman.

```sh
bash packaging/build-local.sh
```

Le script crée une archive locale reproductible, calcule son SHA-256 et
lance `makepkg` avec les tests, sans modifier le PKGBUILD public.

La sauvegarde de la configuration précédente est dans
`~/.local/state/omarchy-screenpad/backups/`. Pour retirer seulement le bouton :
`omarchy plugin disable soheib.screenpad`.
