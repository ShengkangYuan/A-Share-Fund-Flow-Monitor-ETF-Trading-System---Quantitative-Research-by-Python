# A-Share Fund Flow Monitor & ETF Trading System

A real-time quantitative research system that tracks institutional capital flow across 55+ Chinese A-share industries, converts the signals into ETF rotation decisions, and evaluates the strategy through realistic event-driven backtesting.

## Overview
The project investigates whether institutional fund-flow information can provide useful signals for systematic ETF rotation after accounting for transaction costs and real-world data limitations.

During market hours, the system collects industry-level fund-flow data every five minutes from public financial APIs, stores timestamped snapshots, maps industries to ETFs, and generates daily trading signals. The complete pipeline covers data collection, quantitative analysis, backtesting, visualization, and deployment. 

## Quantitative Strategy
The current strategy uses an interpretable three-factor scoring model:

- Net fund-flow rank — 40%
- Price-change rank — 30%
- Inflow/outflow ratio — 30%

The factors are combined into a 0–100 composite score. At 14:30 each trading day, the system selects the highest-ranked ETFs for the next rotation. 

## Backtesting
I built an event-driven backtesting engine that models:

- Commission and slippage
- Stamp duty
- Position and share-lot constraints
- Stop-loss / take-profit rules
- Next-day portfolio rotation

The engine reports 40+ performance and risk metrics, including Sharpe ratio, maximum drawdown, Alpha, Beta, and information ratio. 

## Engineering
The system was designed for real-world data rather than idealized datasets. Key engineering components include:

- Multi-source API fallback and retry logic
- Historical data reconstruction
- Industry-name entity resolution
- Rate-limit protection and circuit breaking
- Automated scheduling and watchdog recovery
- Docker deployment
- Automated regression testing

The project includes 140 automated test runs covering the bilingual Streamlit dashboard. 

## Key Finding
The results suggest that fund-flow signals contain predictive information, but their effectiveness is sensitive to transaction costs, data completeness, and infrastructure reliability. 
A key lesson was that **a quantitative signal is only as reliable as the data pipeline and assumptions behind it**.

## Why No Machine Learning Yet?
The current signal model is intentionally rule-based. With limited and noisy intraday data, directly fitting a flexible ML model could increase overfitting risk. I therefore use the current system as an interpretable baseline and plan to investigate learned factor weights and nonlinear interactions once sufficient historical data are available, with strict time-series validation. 

## Tech Stack
Python · pandas · NumPy · AKShare · Streamlit · Plotly · Matplotlib · Docker · curl_cffi