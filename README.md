# ASUS ScreenPad

Luminosité et marche/arrêt du ScreenPad Plus ASUS, depuis une fenêtre ou la zone de notification.
Pour Arch Linux et ses dérivées, sous X11 ou Wayland. Omarchy n’est pas requis.

## Installation

```sh
git clone https://github.com/pinpin-http/asus-screenpad.git
cd asus-screenpad/packaging
makepkg -si
asus-screenpad
```

Ou télécharger le `.pkg.tar.zst` dans les [releases](https://github.com/pinpin-http/asus-screenpad/releases), puis :

```sh
sudo pacman -U asus-screenpad-*.pkg.tar.zst
asus-screenpad
```

Cocher **Lancer à la connexion** pour le démarrage automatique.

Nécessite le pilote noyau `asus_screenpad` (ou `asus::screenpad`). Testé sur ZenBook UX482EG.
L’icône nécessite une zone de notification ; la fenêtre fonctionne aussi sans.

[Intégration Omarchy facultative](docs/omarchy.md) · Licence MIT · Soumission AUR à venir.
