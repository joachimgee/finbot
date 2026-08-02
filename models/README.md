# Models

Ce dossier contient les modèles entraînés (RL, LSTM, Transformer). Les binaires
ne sont plus versionnés dans git (ils pesaient ~175 Mo et sont régénérables).

## Régénérer les modèles

```bash
# Modèle RL long (PPO) — configuration dans config/rl_train_long.yaml
python examples/train_long.py --config config/rl_train_long.yaml

# Démo RL simple
python examples/rl_example_simple.py
```

Les modèles produits ici sont ignorés par git (voir `.gitignore`).
