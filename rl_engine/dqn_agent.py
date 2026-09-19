import numpy as np
import random
from collections import deque
from typing import Dict, Any, Tuple

class DQNAgent:
    def __init__(self, state_dim: int = 12, action_dim: int = 3, gamma: float = 0.95, epsilon: float = 0.05):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = epsilon
        self.memory = deque(maxlen=2000)

        # Q-Network weight matrix
        np.random.seed(1337)
        self.W1 = np.random.randn(state_dim, 32) * 0.1
        self.b1 = np.zeros(32)
        self.W2 = np.random.randn(32, action_dim) * 0.1
        self.b2 = np.zeros(action_dim)

    def _forward(self, state: np.ndarray) -> np.ndarray:
        h = np.maximum(0, np.dot(state, self.W1) + self.b1) # ReLU
        q_values = np.dot(h, self.W2) + self.b2
        return q_values

    def act(self, state: np.ndarray) -> int:
        if random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)
        q_values = self._forward(state)
        return int(np.argmax(q_values))

    def evaluate(self, state: np.ndarray) -> Dict[str, Any]:
        q_vals = self._forward(state)
        best_act = int(np.argmax(q_vals))
        
        # Softmax over Q values to compute action confidence
        exp_q = np.exp(q_vals - np.max(q_vals))
        probs = exp_q / np.sum(exp_q)

        action_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
        return {
            "model": "Deep Q-Network (DQN Replay Agent)",
            "signal": action_map.get(best_act, "HOLD"),
            "confidence": round(float(probs[best_act]), 3),
            "q_values": {
                "HOLD": round(float(q_vals[0]), 3),
                "BUY": round(float(q_vals[1]), 3),
                "SELL": round(float(q_vals[2]), 3),
            }
        }
