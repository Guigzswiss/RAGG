# Impression automatique de dossier (Windows)

Surveille un dossier et imprime automatiquement chaque fichier PDF, image
(JPG/PNG/BMP/GIF/TIFF) ou Office (Word/Excel/PowerPoint) qui y est depose,
sur l'imprimante par defaut de Windows.

Aucune dependance a installer : le script n'utilise que la bibliotheque
standard de Python.

## Prerequis

- Python 3 installe sur le PC, avec la case **"Add python.exe to PATH"**
  cochee pendant l'installation (https://www.python.org/downloads/).
- Une imprimante par defaut configuree dans Windows.

## Dossier surveille

Par defaut : `Bureau\A imprimer` (cree automatiquement au premier lancement).

Pour utiliser un autre dossier, passe-le en argument :

```
python watch_and_print.py "C:\Users\moi\Desktop\Mon dossier"
```

Trois sous-dossiers sont crees automatiquement dans le dossier surveille :

- `Imprimes` : fichiers envoyes a l'imprimante avec succes
- `Erreurs` : fichiers dont l'impression a echoue
- `Non supportes` : fichiers d'un type non pris en charge, deplaces sans
  impression

Un fichier `auto_print.log` journalise chaque action.

## Tester manuellement

Double-clique sur `start_visible.bat` : une fenetre console s'ouvre et
affiche les logs en direct. Depose un PDF ou une image dans le dossier
surveille pour verifier que l'impression se declenche. Ferme la fenetre
(ou Ctrl+C) pour arreter.

## Lancer automatiquement au demarrage de Windows

Double-clique sur `install_startup.bat`. Cela cree une tache planifiee
Windows ("AutoPrintDossier") qui lance le script silencieusement (sans
fenetre) a chaque ouverture de session.

Pour desinstaller : double-clique sur `uninstall_startup.bat`.

## Notes

- Pour les PDF et les images, l'impression se fait generalement sans
  ouvrir de fenetre visible (via l'application par defaut associee).
- Pour les fichiers Office (Word/Excel/PowerPoint), l'application
  correspondante doit etre installee ; elle peut s'ouvrir brievement le
  temps d'imprimer avant de se refermer.
- Le script attend que la taille du fichier arrete de changer avant de
  l'imprimer, pour eviter d'imprimer un fichier encore en cours de copie
  ou de telechargement.
