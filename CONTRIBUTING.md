# Contributing Guide

Merci de vouloir contribuer à PinkyBrain & PinkyBrainBug ! 🎉

## 🤝 Comment Contribuer

### Signaler des Bugs

Si vous trouvez un bug :
1. Vérifiez qu'il n'existe pas déjà dans les [Issues](https://github.com/PinkyBrain-ai/pinkybrain/issues)
2. Ouvrez une nouvelle issue avec :
   - Un titre descriptif
   - La description du bug
   - Étapes pour reproduire
   - Version de Python
   - Logs si possible

### Suggester des Fonctionnalités

Pour les nouvelles fonctionnalités :
1. Vérifiez qu'elle n'existe pas déjà
2. Ouvrez une issue avec :
   - Description de la fonctionnalité
   - Cas d'usage
   - Pourquoi c'est utile

### Pull Requests

Pour contribuer du code :

1. **Fork** le repo
2. **Clonez** votre fork :
   ```bash
   git clone https://github.com/votre-username/PinkyBrain.git
   cd PinkyBrain
   ```

3. **Créez une branche** :
   ```bash
   git checkout -b feature/AmazingFeature
   ```

4. **Faites vos changements** :
   - Suivez le style de code existant
   - Ajoutez des tests
   - Mettez à jour la documentation

5. **Testez** :
   ```bash
   pip install -r requirements.txt
   pytest tests/ -v
   ```

6. **Committez** :
   ```bash
   git add .
   git commit -m "Add AmazingFeature"
   ```

7. **Push** :
   ```bash
   git push origin feature/AmazingFeature
   ```

8. **Ouvrez une PR** sur GitHub

## 📝 Style de Code

- Python 3.12+
- PEP 8
- Type hints recommandés
- Docstrings pour les fonctions publiques
- Tests pour les nouvelles fonctionnalités

## 🧪 Tests

Exécuter les tests :
```bash
pytest tests/ -v
```

Avec couverture :
```bash
pytest tests/ --cov=src --cov-report=html
```

## 📚 Documentation

Mettez à jour la documentation si nécessaire :
- README.md
- Guides dans docs/
- Docstrings dans le code

## 🚀 Release Process

Les releases sont gérées via GitHub Releases avec un changelog.

## 📞 Contact

- GitHub Issues: https://github.com/PinkyBrain-ai/pinkybrain/issues
- Discord: https://discord.com/invite/clawd

MERCI de contribuer ! 🙏