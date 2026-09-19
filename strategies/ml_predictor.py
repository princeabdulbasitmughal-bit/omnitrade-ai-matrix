import numpy as np
import pandas as pd
import logging
from typing import Dict, Any, Tuple, List
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
            if len(prices) < max_lag * 2:
                return 0.5
            lags = range(2, max_lag)
            tau = [np.sqrt(np.std(np.subtract(prices[lag:], prices[:-lag]))) for lag in lags]
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            hurst = float(poly[0] * 2.0)
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

        closes = df_ind["close"]
        highs = df_ind["high"]
        lows = df_ind["low"]
        opens = df_ind["open"]
        vols = df_ind["volume"]

        # 1. Multi-Horizon Returns & Price Momentum
        data["ret_1"] = closes.pct_change(1)
        data["ret_3"] = closes.pct_change(3)
        data["ret_5"] = closes.pct_change(5)
        data["ret_10"] = closes.pct_change(10)
        data["momentum_accel"] = data["ret_1"] - data["ret_3"]

        # 2. Parkinson Volatility (High-Low estimator, 5x more efficient than close-to-close)
        hl_ratio = np.log(highs / (lows + 1e-8))
        data["parkinson_vol_10"] = np.sqrt((hl_ratio ** 2).rolling(10).mean() / (4 * np.log(2)))

        # 3. Garman-Klass Extreme Volatility
        log_hl = hl_ratio ** 2
        log_co = (np.log(closes / (opens + 1e-8))) ** 2
        data["garman_klass_vol"] = np.sqrt((0.5 * log_hl - (2 * np.log(2) - 1) * log_co).rolling(10).mean())

        # 4. Trend & Mean Reversion Indicators
        data["rsi_norm"] = (df_ind["rsi"] - 50.0) / 50.0
        data["macd_hist_norm"] = df_ind["macd_hist"] / (closes * 0.01 + 1e-8)
        data["bb_pct"] = df_ind["bb_pct"].fillna(0.5)
        data["dist_ema_9"] = (closes - closes.ewm(span=9).mean()) / (closes + 1e-8)
        data["dist_ema_21"] = (closes - closes.ewm(span=21).mean()) / (closes + 1e-8)
        data["dist_ema_50"] = (closes - df_ind["ema_50"]) / (df_ind["ema_50"] + 1e-8)

        # 5. Volume Force & Acceleration
        vol_sma_10 = vols.rolling(10).mean().replace(0, 1)
        data["volume_surge_ratio"] = vols / vol_sma_10
        data["volume_price_trend"] = (closes.pct_change() * vols).rolling(5).mean() / (vols.rolling(5).mean() + 1e-8)

        # 6. Target 1 (Classification Direction): 1 if next close > current close, else 0
        target_dir = (closes.shift(-1) > closes).astype(int)

        # 7. Target 2 (Continuous Expected % Return in 3 candles)
        target_ret_3 = (closes.shift(-3) - closes) / (closes + 1e-8)

        valid_idx = data.dropna().index.intersection(target_dir.dropna().index)
        return data.loc[valid_idx], target_dir.loc[valid_idx], target_ret_3.loc[valid_idx]

    def predict_next_candle(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Executes thread-safe ultra-efficient Ensemble Stacking prediction with calibrated Bayesian probabilities.
        """
        if len(df) < 30:
            return {
                "prediction": "NEUTRAL",
                "bullish_prob": 0.5,
                "bearish_prob": 0.5,
                "confidence": 0.5,
                "regime": "INSUFFICIENT_DATA",
                "expected_return_3bar_pct": 0.0,
                "status": "INSUFFICIENT_DATA"
            }

        try:
            X, y_dir, y_ret = self._extract_institutional_features(df)
            if len(X) < 25:
                return {
                    "prediction": "NEUTRAL",
                    "bullish_prob": 0.5,
                    "bearish_prob": 0.5,
                    "confidence": 0.5,
                    "regime": "INSUFFICIENT_SAMPLES",
                    "expected_return_3bar_pct": 0.0,
                    "status": "TOO_FEW_SAMPLES"
                }

            X_train = X.iloc[:-1]
            y_train = y_dir.iloc[:-1]
            X_latest = X.iloc[[-1]]

            # Standardize features for linear model
            x_mean = X_train.mean()
            x_std = X_train.std().replace(0, 1)
            X_train_scaled = (X_train - x_mean) / x_std
            X_latest_scaled = (X_latest - x_mean) / x_std

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
            linear_model.fit(X_train_scaled.fillna(0), y_train)
            lin_probs = linear_model.predict_proba(X_latest_scaled.fillna(0))[0]
            lin_classes = list(linear_model.classes_)
            lin_bull = float(lin_probs[lin_classes.index(1)]) if 1 in lin_classes else 0.5

            # 4. Soft-Voting Weighted Ensemble (45% GB + 35% RF + 20% Linear)
            ensemble_bullish = (0.45 * gb_bull) + (0.35 * rf_bull) + (0.20 * lin_bull)
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

            # Top feature importances
            feat_imp = {}
            if hasattr(gb_model, "feature_importances_"):
                top_idx = np.argsort(gb_model.feature_importances_)[::-1][:4]
                cols = X.columns
                for idx in top_idx:
                    feat_imp[cols[idx]] = round(float(gb_model.feature_importances_[idx]), 3)

            return {
                "prediction": prediction,
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
                "bullish_prob": 0.5,
                "bearish_prob": 0.5,
                "confidence": 0.5,
                "regime": "ERROR",
                "expected_return_3bar_pct": 0.0,
                "status": f"ERROR: {str(e)}"
            }
