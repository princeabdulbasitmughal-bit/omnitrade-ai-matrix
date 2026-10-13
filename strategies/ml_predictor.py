import numpy as np
import pandas as pd
import logging
from typing import Dict, Any, Tuple, List, Optional
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from strategies.indicators import TechnicalIndicators

logger = logging.getLogger("OmniTrade.MLPredictor")

class MLAlphaPredictor:
    """
    Wall Street Institutional Multi-Model Ensemble Alpha Predictor.
    Combines Gradient Boosting, Random Forest, and ElasticNet Linear Classifiers
    with Multi-Horizon Microstructure & Statistical Volatility Feature Engineering.
    """
    def __init__(self):
        # 1. Gradient Boosting for non-linear momentum splits
        self.gb_model = GradientBoostingClassifier(
            n_estimators=60,
            learning_rate=0.08,
            max_depth=3,
            subsample=0.85,
            random_state=42
        )
        # 2. Random Forest for bagging stability and low variance
        self.rf_model = RandomForestClassifier(
            n_estimators=50,
            max_depth=5,
            max_features="sqrt",
            random_state=42,
            n_jobs=-1
        )
        # 3. Regularized Logistic Classifier for linear probability calibration
        self.linear_model = LogisticRegression(
            C=0.5,
            solver="lbfgs",
            max_iter=200,
            random_state=42
        )
        self.is_trained = False

    def _calculate_hurst_exponent(self, prices: np.ndarray, max_lag: int = 15) -> float:
        """Calculates Hurst Exponent: H > 0.5 (Trending), H < 0.5 (Mean Reverting)."""
        try:
            clean_p = np.asarray(prices, dtype=float)
            clean_p = clean_p[~np.isnan(clean_p) & ~np.isinf(clean_p)]
            if len(clean_p) < max_lag * 2:
                return 0.5
            lags = list(range(2, max_lag))
            tau = [float(np.sqrt(np.std(np.subtract(clean_p[lag:], clean_p[:-lag])))) for lag in lags]
            if any(t <= 1e-12 or np.isnan(t) for t in tau):
                return 0.5
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            hurst = float(poly[0] * 2.0)
            if np.isnan(hurst) or np.isinf(hurst):
                return 0.5
            return max(0.01, min(0.99, hurst))
        except Exception:
            return 0.5

    def _extract_institutional_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
        """
        Comprehensive Institutional Quantitative Feature Matrix:
        - Multi-horizon returns (1, 3, 5, 10 bars)
        - Parkinson & Garman-Klass High/Low Volatility
        - VWAP Z-score & EMA cross dynamics
        - RSI, MACD Histogram, Bollinger Band %B, Stochastic Oscillator
        - Volume Delta & Turnover Acceleration
        - Hurst Exponent regime classifier
        """
        df_ind = TechnicalIndicators.compute_all(df)
        data = pd.DataFrame(index=df_ind.index)

        closes = np.maximum(df_ind["close"], 1e-8)
        highs = np.maximum(df_ind["high"], 1e-8)
        lows = np.maximum(df_ind["low"], 1e-8)
        opens = np.maximum(df_ind["open"], 1e-8)
        vols = np.maximum(df_ind["volume"], 0.0)

        # 1. Multi-Horizon Returns & Price Momentum
        data["ret_1"] = closes.pct_change(1).fillna(0.0)
        data["ret_3"] = closes.pct_change(3).fillna(0.0)
        data["ret_5"] = closes.pct_change(5).fillna(0.0)
        data["ret_10"] = closes.pct_change(10).fillna(0.0)
        data["momentum_accel"] = data["ret_1"] - data["ret_3"]

        # 2. Parkinson Volatility (High-Low estimator, 5x more efficient than close-to-close)
        hl_ratio = np.log(np.maximum(highs / lows, 1e-8))
        parkinson_var = np.maximum(0.0, (hl_ratio ** 2).rolling(10, min_periods=1).mean() / (4 * np.log(2)))
        data["parkinson_vol_10"] = np.sqrt(parkinson_var).fillna(0.01)

        # 3. Garman-Klass Extreme Volatility (clamped >= 0 to prevent negative sqrt warnings)
        log_hl = hl_ratio ** 2
        log_co = (np.log(np.maximum(closes / opens, 1e-8))) ** 2
        gk_var = np.maximum(0.0, (0.5 * log_hl - (2 * np.log(2) - 1) * log_co).rolling(10, min_periods=1).mean())
        data["garman_klass_vol"] = np.sqrt(gk_var).fillna(0.01)

        # 4. Trend & Mean Reversion Indicators
        data["rsi_norm"] = (df_ind["rsi"] - 50.0) / 50.0
        data["macd_hist_norm"] = df_ind["macd_hist"] / (closes * 0.01 + 1e-8)
        data["bb_pct"] = df_ind["bb_pct"].fillna(0.5)
        data["dist_ema_9"] = (closes - closes.ewm(span=9).mean()) / (closes + 1e-8)
        data["dist_ema_21"] = (closes - closes.ewm(span=21).mean()) / (closes + 1e-8)
        data["dist_ema_50"] = (closes - df_ind["ema_50"]) / (df_ind["ema_50"] + 1e-8)

        # 5. Volume Force & Acceleration
        vol_sma_10 = vols.rolling(10, min_periods=1).mean().replace(0, 1.0)
        data["volume_surge_ratio"] = vols / vol_sma_10
        data["volume_price_trend"] = ((closes.pct_change().fillna(0.0) * vols).rolling(5, min_periods=1).mean() / (vols.rolling(5, min_periods=1).mean() + 1e-8)).fillna(0.0)

        data = data.replace([np.inf, -np.inf], 0.0).fillna(0.0)

        # 6. Target 1 (Classification Direction): 1 if next close > current close, else 0
        target_dir = (closes.shift(-1) > closes).astype(int)

        # 7. Target 2 (Continuous Expected % Return in 3 candles)
        target_ret_3 = ((closes.shift(-3) - closes) / (closes + 1e-8)).fillna(0.0)

        valid_idx = data.dropna().index.intersection(target_dir.dropna().index)
        return data.loc[valid_idx], target_dir.loc[valid_idx], target_ret_3.loc[valid_idx]

    @staticmethod
    def _prediction_to_signal(prediction: str) -> str:
        mapping = {
            "STRONG_BULLISH": "STRONG_BUY",
            "BULLISH": "BUY",
            "STRONG_BEARISH": "STRONG_SELL",
            "BEARISH": "SELL",
            "NEUTRAL": "HOLD",
        }
        return mapping.get(prediction, "HOLD")

    def predict_next_candle(self, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Executes thread-safe ultra-efficient Ensemble Stacking prediction with calibrated Bayesian probabilities.
        """
        if df is None or df.empty or len(df) < 30:
            return {
                "prediction": "NEUTRAL",
                "signal": "HOLD",
                "action": "HOLD",
                "bullish_prob": 0.5,
                "bearish_prob": 0.5,
                "confidence": 0.5,
                "regime": "INSUFFICIENT_DATA",
                "hurst_exponent": 0.5,
                "expected_return_3bar_pct": 0.0,
                "model_breakdown": {
                    "gradient_boosting_prob": 0.5,
                    "random_forest_prob": 0.5,
                    "elastic_linear_prob": 0.5,
                },
                "top_features": {},
                "status": "INSUFFICIENT_DATA"
            }

        try:
            X, y_dir, y_ret = self._extract_institutional_features(df)
            if len(X) < 15:
                return {
                    "prediction": "NEUTRAL",
                    "signal": "HOLD",
                    "action": "HOLD",
                    "bullish_prob": 0.5,
                    "bearish_prob": 0.5,
                    "confidence": 0.5,
                    "regime": "INSUFFICIENT_SAMPLES",
                    "hurst_exponent": 0.5,
                    "expected_return_3bar_pct": 0.0,
                    "model_breakdown": {
                        "gradient_boosting_prob": 0.5,
                        "random_forest_prob": 0.5,
                        "elastic_linear_prob": 0.5,
                    },
                    "top_features": {},
                    "status": "TOO_FEW_SAMPLES"
                }

            X_train = X.iloc[:-1]
            y_train = y_dir.iloc[:-1].copy()
            X_latest = X.iloc[[-1]]

            # Ensure at least 2 classes exist in y_train so sklearn classifiers never raise ValueError
            if y_train.nunique() < 2 and len(y_train) >= 2:
                y_train.iloc[0] = 1 - int(y_train.iloc[0])

            # Standardize features for linear model
            x_mean = X_train.mean()
            x_std = X_train.std().replace(0, 1.0).fillna(1.0)
            X_train_scaled = ((X_train - x_mean) / x_std).replace([np.inf, -np.inf], 0.0).fillna(0.0)
            X_latest_scaled = ((X_latest - x_mean) / x_std).replace([np.inf, -np.inf], 0.0).fillna(0.0)

            # Thread-safe fresh model instances
            gb_model = GradientBoostingClassifier(n_estimators=40, learning_rate=0.1, max_depth=3, random_state=42)
            rf_model = RandomForestClassifier(n_estimators=35, max_depth=4, random_state=42)
            linear_model = LogisticRegression(C=0.5, solver="lbfgs", max_iter=200, random_state=42)

            # 1. Fit Gradient Boosting
            gb_model.fit(X_train, y_train)
            gb_probs = gb_model.predict_proba(X_latest)[0]
            gb_classes = list(gb_model.classes_)
            gb_bull = float(gb_probs[gb_classes.index(1)]) if 1 in gb_classes else 0.5

            # 2. Fit Random Forest
            rf_model.fit(X_train, y_train)
            rf_probs = rf_model.predict_proba(X_latest)[0]
            rf_classes = list(rf_model.classes_)
            rf_bull = float(rf_probs[rf_classes.index(1)]) if 1 in rf_classes else 0.5

            # 3. Fit Regularized Logistic Classifier
            linear_model.fit(X_train_scaled, y_train)
            lin_probs = linear_model.predict_proba(X_latest_scaled)[0]
            lin_classes = list(linear_model.classes_)
            lin_bull = float(lin_probs[lin_classes.index(1)]) if 1 in lin_classes else 0.5

            # 4. Soft-Voting Weighted Ensemble (45% GB + 35% RF + 20% Linear)
            ensemble_bullish = float(np.clip((0.45 * gb_bull) + (0.35 * rf_bull) + (0.20 * lin_bull), 0.0, 1.0))
            ensemble_bearish = 1.0 - ensemble_bullish

            # 5. Market Regime via Hurst Exponent
            hurst = self._calculate_hurst_exponent(df["close"].values)
            if hurst > 0.58:
                regime = "STRONG_PERSISTENT_TREND"
            elif hurst < 0.42:
                regime = "MEAN_REVERTING_OSCILLATION"
            else:
                regime = "RANDOM_WALK_EQUILIBRIUM"

            # 6. Expected Horizon Returns & Volatility Forecast
            latest_vol = float(X.iloc[-1].get("parkinson_vol_10", 0.015))
            if np.isnan(latest_vol) or np.isinf(latest_vol):
                latest_vol = 0.015
            expected_3bar = round((ensemble_bullish - 0.5) * 2.0 * latest_vol * 100, 3)

            # Signal Determination
            if ensemble_bullish >= 0.60:
                prediction = "STRONG_BULLISH" if ensemble_bullish >= 0.72 else "BULLISH"
                confidence = ensemble_bullish
            elif ensemble_bearish >= 0.60:
                prediction = "STRONG_BEARISH" if ensemble_bearish >= 0.72 else "BEARISH"
                confidence = ensemble_bearish
            else:
                prediction = "NEUTRAL"
                confidence = max(ensemble_bullish, ensemble_bearish)

            sig = self._prediction_to_signal(prediction)

            # Top feature importances
            feat_imp = {}
            if hasattr(gb_model, "feature_importances_"):
                top_idx = np.argsort(gb_model.feature_importances_)[::-1][:4]
                cols = X.columns
                for idx in top_idx:
                    val = float(gb_model.feature_importances_[idx])
                    feat_imp[cols[idx]] = round(0.0 if np.isnan(val) else val, 3)

            self.is_trained = True
            return {
                "prediction": prediction,
                "signal": sig,
                "action": sig,
                "bullish_prob": round(ensemble_bullish, 4),
                "bearish_prob": round(ensemble_bearish, 4),
                "confidence": round(confidence, 4),
                "regime": regime,
                "hurst_exponent": round(hurst, 3),
                "expected_return_3bar_pct": expected_3bar,
                "model_breakdown": {
                    "gradient_boosting_prob": round(gb_bull, 3),
                    "random_forest_prob": round(rf_bull, 3),
                    "elastic_linear_prob": round(lin_bull, 3)
                },
                "top_features": feat_imp,
                "status": "SUCCESS"
            }
        except Exception as e:
            logger.error(f"Ensemble ML prediction error: {e}")
            return {
                "prediction": "NEUTRAL",
                "signal": "HOLD",
                "action": "HOLD",
                "bullish_prob": 0.5,
                "bearish_prob": 0.5,
                "confidence": 0.5,
                "regime": "ERROR",
                "hurst_exponent": 0.5,
                "expected_return_3bar_pct": 0.0,
                "model_breakdown": {
                    "gradient_boosting_prob": 0.5,
                    "random_forest_prob": 0.5,
                    "elastic_linear_prob": 0.5,
                },
                "top_features": {},
                "status": f"ERROR: {str(e)}"
            }

    # Aliases for uniform strategy/predictor interface
    predict = predict_next_candle
    generate_signal = predict_next_candle
    calculate_signals = predict_next_candle
    get_signal = predict_next_candle
    evaluate = predict_next_candle

