import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import os
import uuid

def fetch_data(ticker: str):
    df = yf.download(ticker, period="1y", interval="1d")
    return df.tail().to_string()

def calculate_indicator(ticker: str, indicator: str):
    df = yf.download(ticker, period="6mo", interval="1d")
    if indicator.upper() == "SMA":
        df["SMA20"] = df["Close"].rolling(20).mean()
        return df[["Close", "SMA20"]].tail().to_string()
    elif indicator.upper() == "RSI":
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))
        return df[["Close", "RSI"]].tail().to_string()
    return "Indicator not supported."

def backtest_strategy(ticker: str, strategy: str):
    try:
        df = yf.download(ticker, period="1y", interval="1d")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        df = df.dropna()
        if "Close" not in df.columns:
            return f"ERROR: No 'Close' column found for {ticker}"
        if strategy.upper() == "SMA":
            df["SMA20"] = df["Close"].rolling(20).mean()
            df = df.dropna()
            df["Signal"] = (df["Close"] > df["SMA20"]).astype(int)
            df["Returns"] = df["Close"].pct_change().fillna(0)
            shifted_signal = df["Signal"].shift(1).fillna(0).reindex(df.index)
            df["Strategy"] = shifted_signal * df["Returns"]
            perf = df[["Returns", "Strategy"]].cumsum().tail()
            # Generate chart
            chart_file = plot_chart(df, ticker, strategy)
            # trades_df, accuracy = analyze_trades(df)
            # print(f"Winning trades accuracy: {accuracy:.2f}%")
            # plot_trades(df, trades_df, ticker)
            return f"Backtest completed for {ticker} ({strategy}).\nChart saved: {chart_file}\n\n{perf.to_string()}"
        else:
            return "Strategy not supported."

    except Exception as e:
        return f"ERROR in backtest: {e}"

def execute_command(command: str):
    try:
        if command.startswith("FETCH"):
            ticker = command.split('"')[1]
            return fetch_data(ticker)
        elif command.startswith("INDICATOR"):
            parts = command.split('"')
            ticker, indicator = parts[1], parts[3]
            return calculate_indicator(ticker, indicator)
        elif command.startswith("BACKTEST"):
            parts = command.split('"')
            ticker, strat = parts[1], parts[3]
            return backtest_strategy(ticker, strat)
        elif command.startswith("FINISH"):
            return command.split('"')[1] if '"' in command else "Finished."
    except Exception as e:
        return f"ERROR: {e}"


def analyze_trades(df):
    """Extract trades and calculate winning trade accuracy."""
    trades = []
    in_trade = False
    buy_price = 0
    for i in range(len(df)):
        if df["Signal"].iloc[i] == 1 and not in_trade:
            buy_price = df["Close"].iloc[i]
            buy_date = df.index[i]
            in_trade = True
        elif df["Signal"].iloc[i] == 0 and in_trade:
            sell_price = df["Close"].iloc[i]
            sell_date = df.index[i]
            trades.append({
                "Buy Date": buy_date,
                "Buy Price": buy_price,
                "Sell Date": sell_date,
                "Sell Price": sell_price,
                "Profit": sell_price - buy_price
            })
            in_trade = False

    trades_df = pd.DataFrame(trades)
    trades_df["Winning Trade"] = trades_df["Profit"] > 0
    accuracy = trades_df["Winning Trade"].mean() * 100 if not trades_df.empty else 0
    return trades_df, accuracy


def plot_chart(df, ticker, strategy):
    """Plots price, SMA, strategy equity curve, and trades. Saves as PNG in charts."""

    trades_df, accuracy = analyze_trades(df)
    fig, axs = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    axs[0].plot(df.index, df["Close"], label="Close Price", color="blue")
    if "SMA20" in df.columns:
        axs[0].plot(df.index, df["SMA20"], label="SMA20", color="orange")

        for _, row in trades_df.iterrows():
            color = "green" if row["Winning Trade"] else "red"
            axs[0].scatter(row["Buy Date"], row["Buy Price"], marker="^", color=color, s=100)
            axs[0].scatter(row["Sell Date"], row["Sell Price"], marker="v", color=color, s=100)

    axs[0].set_title(f"{ticker} Price & SMA - Trade Accuracy: {accuracy:.2f}%")
    axs[0].legend()
    if "Strategy" in df.columns:
        axs[1].plot(df.index, df["Returns"].cumsum(), label="Buy & Hold", color="green")
        axs[1].plot(df.index, df["Strategy"].cumsum(), label=f"{strategy} Strategy", color="red")
        axs[1].set_title("Equity Curve")
        axs[1].legend()
    plt.tight_layout()
    filename = f"chart_{ticker}_{uuid.uuid4().hex[:6]}.png"
    filepath = os.path.join("charts", filename)
    os.makedirs("charts", exist_ok=True)
    plt.savefig(filepath)
    plt.close(fig)

    return filepath
