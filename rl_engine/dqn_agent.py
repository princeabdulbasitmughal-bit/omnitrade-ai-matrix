import numpy as np
import pandas as pd
import random
from collections import deque
from typing import Dict, Any, Tuple

class DQNAgent:
    def __init__(self, state_dim: int = 12, action_dim: int = 3, gamma: float = 0.95, epsilon: float = 0.05):
        self.state_dim = max(1, int(state_dim))
        self.action_dim = max(1, int(action_dim))
        self.gamma = gamma
        self.epsilon = epsilon
        self.memory = deque(maxlen=2000)

        # Q-Network weight matrix
        rng = np.random.RandomState(1337)
        self.W1 = rng.randn(self.state_dim, 32) * 0.1
        self.b1 = np.zeros(32)
        self.W2 = rng.randn(32, self.action_dim) * 0.1
        self.b2 = np.zeros(self.action_dim)

    def _prepare_state(self, state: Any) -> np.ndarray:
        if state is None:
            return np.zeros(self.state_dim, dtype=np.float32)
        if isinstance(state, pd.DataFrame):
            if state.empty:
                return np.zeros(self.state_dim, dtype=np.float32)
            from rl_engine.env import TradingEnvironment
            arr = TradingEnvironment(state)._get_state()
        else:
            arr = np.asarray(state, dtype=np.float32).flatten()
        arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=-1.0)
        if len(arr) < self.state_dim:
            arr = np.pad(arr, (0, self.state_dim - len(arr)), mode="constant")
        elif len(arr) > self.state_dim:
            arr = arr[:self.state_dim]
        return arr

    def _forward(self, state: Any = None) -> np.ndarray:
        s = self._prepare_state(state)
        h = np.maximum(0.0, np.dot(s, self.W1) + self.b1)  # ReLU
        q_values = np.dot(h, self.W2) + self.b2
        return np.nan_to_num(q_values, nan=0.0, posinf=10.0, neginf=-10.0)

    def act(self, state: Any = None) -> int:
        if random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)
        q_values = self._forward(state)
        return int(np.argmax(q_values))

    def select_action(self, state: Any = None) -> Tuple[int, float, float]:
        q_vals = self._forward(state)
        best_act = int(np.argmax(q_vals))
        exp_q = np.exp(q_vals - np.max(q_vals))
        probs = exp_q / max(float(np.sum(exp_q)), 1e-8)
        return best_act, float(np.log(max(float(probs[best_act]), 1e-8))), float(q_vals[best_act])

    def evaluate(self, state: Any = None) -> Dict[str, Any]:
        q_vals = self._forward(state)
        best_act = int(np.argmax(q_vals))
        
        # Softmax over Q values to compute action confidence
        exp_q = np.exp(q_vals - np.max(q_vals))
        probs = exp_q / max(float(np.sum(exp_q)), 1e-8)

        action_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
        best_signal = action_map.get(best_act, "HOLD")
        return {
            "model": "Deep Q-Network (DQN Replay Agent)",
            "signal": best_signal,
            "action": best_signal,
            "confidence": round(float(probs[best_act]), 3),
            "q_value": round(float(q_vals[best_act]), 3),
            "q_values": {
                "HOLD": round(float(q_vals[0]), 3) if len(q_vals) > 0 else 0.0,
                "BUY": round(float(q_vals[1]), 3) if len(q_vals) > 1 else 0.0,
                "SELL": round(float(q_vals[2]), 3) if len(q_vals) > 2 else 0.0,
            },
            "status": "ONLINE"
        }

    # Aliases for uniform RL / strategy evaluation
    get_signal = evaluate
    get_signal_and_confidence = evaluate
    predict = evaluate
    generate_signal = evaluate
    calculate_signals = evaluate

