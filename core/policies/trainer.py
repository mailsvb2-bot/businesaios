from __future__ import annotations


class OfflineTrainer:
    def train(self, dataset):
        """
        Возвращает новую policy-модель (артефакт).
        Здесь может быть RL / bandits / LTV-оптимизация.
        OfflineTrainer не исполняет решения.
        """
        model = {}
        for state, action in dataset:
            model[state] = action
        return model
