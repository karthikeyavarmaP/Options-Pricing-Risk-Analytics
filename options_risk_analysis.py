import os
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

from scipy.stats import norm

# ============================================================
# CONFIGURATION
# ============================================================

TICKER = "AAPL"

STRIKE_PRICE = 200
TIME_TO_MATURITY = 0.5        # years
RISK_FREE_RATE = 0.045        # 4.5%
NUM_SIMULATIONS = 100000

PORTFOLIO_VALUE = 100000      # $100,000 for VaR demonstration
CONFIDENCE_LEVELS = [0.95, 0.99]

os.makedirs("outputs", exist_ok=True)

np.random.seed(42)


# ============================================================
# DOWNLOAD HISTORICAL MARKET DATA
# ============================================================

print("\nDownloading historical market data...")

data = yf.download(
    TICKER,
    period="2y",
    auto_adjust=True,
    progress=False
)

if data.empty:
    raise ValueError("No market data downloaded.")

# Handle newer yfinance MultiIndex format
if isinstance(data.columns, pd.MultiIndex):
    close_prices = data["Close"][TICKER]
else:
    close_prices = data["Close"]

close_prices = close_prices.dropna()

spot_price = float(close_prices.iloc[-1])

returns = close_prices.pct_change().dropna()

# Annualized historical volatility
volatility = float(returns.std() * np.sqrt(252))

print(f"Ticker: {TICKER}")
print(f"Current Stock Price: ${spot_price:.2f}")
print(f"Annualized Volatility: {volatility:.2%}")


# ============================================================
# BLACK-SCHOLES MODEL
# ============================================================

def calculate_d1_d2(S, K, T, r, sigma):

    d1 = (
        np.log(S / K)
        + (r + 0.5 * sigma ** 2) * T
    ) / (sigma * np.sqrt(T))

    d2 = d1 - sigma * np.sqrt(T)

    return d1, d2


def black_scholes_call(S, K, T, r, sigma):

    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)

    call_price = (
        S * norm.cdf(d1)
        - K * np.exp(-r * T) * norm.cdf(d2)
    )

    return call_price


def black_scholes_put(S, K, T, r, sigma):

    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)

    put_price = (
        K * np.exp(-r * T) * norm.cdf(-d2)
        - S * norm.cdf(-d1)
    )

    return put_price


bs_call = black_scholes_call(
    spot_price,
    STRIKE_PRICE,
    TIME_TO_MATURITY,
    RISK_FREE_RATE,
    volatility
)

bs_put = black_scholes_put(
    spot_price,
    STRIKE_PRICE,
    TIME_TO_MATURITY,
    RISK_FREE_RATE,
    volatility
)


# ============================================================
# OPTION GREEKS
# ============================================================

def calculate_greeks(S, K, T, r, sigma):

    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)

    delta_call = norm.cdf(d1)
    delta_put = norm.cdf(d1) - 1

    gamma = (
        norm.pdf(d1)
        / (S * sigma * np.sqrt(T))
    )

    vega = (
        S * norm.pdf(d1) * np.sqrt(T)
    ) / 100

    theta_call = (
        -(S * norm.pdf(d1) * sigma)
        / (2 * np.sqrt(T))
        - r * K * np.exp(-r * T) * norm.cdf(d2)
    ) / 365

    theta_put = (
        -(S * norm.pdf(d1) * sigma)
        / (2 * np.sqrt(T))
        + r * K * np.exp(-r * T) * norm.cdf(-d2)
    ) / 365

    rho_call = (
        K * T * np.exp(-r * T) * norm.cdf(d2)
    ) / 100

    rho_put = (
        -K * T * np.exp(-r * T) * norm.cdf(-d2)
    ) / 100

    return {
        "Call Delta": delta_call,
        "Put Delta": delta_put,
        "Gamma": gamma,
        "Vega": vega,
        "Call Theta": theta_call,
        "Put Theta": theta_put,
        "Call Rho": rho_call,
        "Put Rho": rho_put
    }


greeks = calculate_greeks(
    spot_price,
    STRIKE_PRICE,
    TIME_TO_MATURITY,
    RISK_FREE_RATE,
    volatility
)


# ============================================================
# MONTE CARLO OPTION PRICING
# ============================================================

Z = np.random.standard_normal(NUM_SIMULATIONS)

future_prices = (
    spot_price
    * np.exp(
        (RISK_FREE_RATE - 0.5 * volatility ** 2)
        * TIME_TO_MATURITY
        +
        volatility
        * np.sqrt(TIME_TO_MATURITY)
        * Z
    )
)

call_payoffs = np.maximum(
    future_prices - STRIKE_PRICE,
    0
)

put_payoffs = np.maximum(
    STRIKE_PRICE - future_prices,
    0
)

mc_call = (
    np.exp(-RISK_FREE_RATE * TIME_TO_MATURITY)
    * np.mean(call_payoffs)
)

mc_put = (
    np.exp(-RISK_FREE_RATE * TIME_TO_MATURITY)
    * np.mean(put_payoffs)
)


# ============================================================
# VALUE AT RISK
# ============================================================

def historical_var(returns, portfolio_value, confidence):

    percentile = np.percentile(
        returns,
        (1 - confidence) * 100
    )

    var = -percentile * portfolio_value

    return var


var_results = {}

for confidence in CONFIDENCE_LEVELS:

    var_results[f"{int(confidence*100)}% VaR"] = historical_var(
        returns,
        PORTFOLIO_VALUE,
        confidence
    )


# ============================================================
# MODEL COMPARISON
# ============================================================

comparison = pd.DataFrame({
    "Model": [
        "Black-Scholes",
        "Monte Carlo"
    ],

    "Call Price": [
        bs_call,
        mc_call
    ],

    "Put Price": [
        bs_put,
        mc_put
    ]
})

comparison["Call Difference"] = (
    comparison["Call Price"] - bs_call
)

comparison["Put Difference"] = (
    comparison["Put Price"] - bs_put
)

comparison.to_csv(
    "outputs/model_comparison.csv",
    index=False
)


# ============================================================
# SAVE GREEKS
# ============================================================

greeks_df = pd.DataFrame(
    list(greeks.items()),
    columns=["Greek", "Value"]
)

greeks_df.to_csv(
    "outputs/option_greeks.csv",
    index=False
)


# ============================================================
# SAVE RISK METRICS
# ============================================================

risk_df = pd.DataFrame({
    "Metric": [
        "Portfolio Value",
        "95% Historical VaR",
        "99% Historical VaR",
        "Annualized Volatility"
    ],

    "Value": [
        PORTFOLIO_VALUE,
        var_results["95% VaR"],
        var_results["99% VaR"],
        volatility
    ]
})

risk_df.to_csv(
    "outputs/risk_metrics.csv",
    index=False
)


# ============================================================
# OPTION PRICE SENSITIVITY
# ============================================================

stock_price_range = np.linspace(
    spot_price * 0.6,
    spot_price * 1.4,
    100
)

call_prices = []

put_prices = []

for price in stock_price_range:

    call_prices.append(
        black_scholes_call(
            price,
            STRIKE_PRICE,
            TIME_TO_MATURITY,
            RISK_FREE_RATE,
            volatility
        )
    )

    put_prices.append(
        black_scholes_put(
            price,
            STRIKE_PRICE,
            TIME_TO_MATURITY,
            RISK_FREE_RATE,
            volatility
        )
    )


plt.figure(figsize=(10, 6))

plt.plot(
    stock_price_range,
    call_prices,
    label="Call Option"
)

plt.plot(
    stock_price_range,
    put_prices,
    label="Put Option"
)

plt.axvline(
    STRIKE_PRICE,
    linestyle="--",
    label="Strike Price"
)

plt.xlabel("Underlying Stock Price")

plt.ylabel("Option Price")

plt.title(
    f"{TICKER} Option Price Sensitivity"
)

plt.legend()

plt.tight_layout()

plt.savefig(
    "outputs/option_price_sensitivity.png",
    dpi=300
)

plt.close()


# ============================================================
# MONTE CARLO DISTRIBUTION
# ============================================================

plt.figure(figsize=(10, 6))

plt.hist(
    future_prices,
    bins=60,
    alpha=0.8
)

plt.axvline(
    STRIKE_PRICE,
    linestyle="--",
    label="Strike Price"
)

plt.xlabel(
    "Simulated Stock Price at Expiration"
)

plt.ylabel(
    "Frequency"
)

plt.title(
    f"{TICKER} Monte Carlo Price Distribution"
)

plt.legend()

plt.tight_layout()

plt.savefig(
    "outputs/monte_carlo_distribution.png",
    dpi=300
)

plt.close()


# ============================================================
# RETURN DISTRIBUTION AND VaR
# ============================================================

plt.figure(figsize=(10, 6))

plt.hist(
    returns,
    bins=60,
    alpha=0.8
)

var95_return = np.percentile(
    returns,
    5
)

plt.axvline(
    var95_return,
    linestyle="--",
    label="95% VaR Threshold"
)

plt.xlabel(
    "Daily Return"
)

plt.ylabel(
    "Frequency"
)

plt.title(
    f"{TICKER} Historical Return Distribution"
)

plt.legend()

plt.tight_layout()

plt.savefig(
    "outputs/return_distribution_var.png",
    dpi=300
)

plt.close()


# ============================================================
# PRINT RESULTS
# ============================================================

print("\n==============================")
print("BLACK-SCHOLES OPTION PRICING")
print("==============================")

print(
    f"Call Price: ${bs_call:.2f}"
)

print(
    f"Put Price: ${bs_put:.2f}"
)


print("\n==============================")
print("MONTE CARLO OPTION PRICING")
print("==============================")

print(
    f"Call Price: ${mc_call:.2f}"
)

print(
    f"Put Price: ${mc_put:.2f}"
)


print("\n==============================")
print("OPTION GREEKS")
print("==============================")

for greek, value in greeks.items():

    print(
        f"{greek}: {value:.6f}"
    )


print("\n==============================")
print("VALUE AT RISK")
print("==============================")

for metric, value in var_results.items():

    print(
        f"{metric}: ${value:,.2f}"
    )


print("\n==============================")
print("MODEL COMPARISON")
print("==============================")

print(
    comparison.round(4)
)


print("\nAnalysis complete.")

print(
    "Outputs saved inside outputs/ folder."
)
