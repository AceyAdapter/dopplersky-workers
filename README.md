# Dopplersky Workers

This repository contains the backend services that power the analytics features of [Dopplersky](https://dopplersky.com).

## Features

## Quick Start

### Prerequisites

- Python 3.8+
- Crendentials to a hosted PostgreSQL database

### Installation

```bash
git clone https://github.com/aceyadapter/dopplersky-bots
cd dopplersky-bots
pip install -r requirements.txt
```

### Using the Workers

Running the main script with no flags pulls only users that have been active within the past week. This decision was made to reduce server costs.

```bash
python scripts/run_snapshots.py
```

Running the script with the --simple-query flag will make the workers update ALL registered users in the database

```bash
python scripts/run_snapshots.py --simple-query
```
