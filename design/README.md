# Sources graphiques

Fichiers d'origine, non destinés au web. Ce répertoire est **exclu du
déploiement** : il n'est jamais envoyé sur PythonAnywhere.

| Fichier | Rôle |
| --- | --- |
| `Logo_Evalio.png` | Logo d'origine, 2172 × 724, fond blanc opaque |
| `Favicon.png` | Pictogramme seul, 1254 × 1254, fond transparent |

Les déclinaisons utilisées par le site vivent dans `atelier/static/img/` :

| Fichier | Usage |
| --- | --- |
| `logo-evalio.png` | Barre de navigation, thème clair, et README |
| `logo-evalio-dark.png` | Barre de navigation, thème sombre |
| `logo-evalio-compact.png` | Barre de navigation, sans la baseline |
| `logo-evalio-compact-dark.png` | Idem, thème sombre |
| `favicon.ico` | Favicon, 16/32/48 px, depuis `Favicon.png` |
| `apple-touch-icon.png` | Icône d'écran d'accueil iOS, 180 px, fond blanc |

Elles sont produites depuis la source par le script `outils/logo.py` :

```bash
python3 outils/logo.py
```
