# Project Context: Iddaa Value Bet AI

This document serves as a persistent context bridge for AI agents.

## Project Vision
An AI-driven football betting analyzer that identifies "Value Bets" by comparing AI-calculated probabilities with bookmaker (Iddaa) odds. Optimized for mobile and automated background analysis.

## Superpowers Status
- **Altyapı**: `.agent/` dizini altında kurulu.
- **Yetenekler**: Brainstorming, Planning, Execution, Debugging, Verification.
- **İş Akışları**: `/superpowers-write-plan`, `/superpowers-execute-plan`, `/superpowers-brainstorm`.

## Core Logic Flow
1. `scraper.py` fetches the real-time bulletin from iddaa.com.
2. `data_fetcher.py` gathers historical stats, Elo (ClubElo), and injury data (Transfermarkt).
3. `predictor.py` uses XGBoost/MLP and Poisson distribution to calculate true probabilities.
4. `analyzer.py` calculates Expected Value (EV) and Kelly Criterion stakes.
5. `app.py` displays the results with a Premium Glassmorphism UI.
6. `utils/background_worker.py` runs this cycle every 15 minutes.

## Important Links
- Role Instructions: [.agent/AGENTS.md](file:///c:/Users/fkaga/Documents/Yeni%20klasör/iddaa_value_bet/.agent/AGENTS.md)
- Knowledge Item: Search for "Superpowers Integration" in KI summaries.
