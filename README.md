# Dopplersky Workers

This repository contains the backend services that power the analytics features of [Dopplersky](https://dopplersky.com).

## Features

- **User Profile Tracking** - Monitors Bluesky user profiles and updates changes in handles, display names, and avatars
- **Post Analytics** - Collects engagement metrics (likes, replies, quotes, reposts) from user posts
- **Daily Snapshots** - Creates daily analytics snapshots for follower counts, engagement totals, and growth tracking
- **Efficient Processing** - Uses concurrent processing and batched API calls for optimal performance
- **Flexible User Selection** - Process only recently active users or all registered users

## Quick Start

### Prerequisites

- Python 3.8+
- Credentials to a hosted PostgreSQL database

### Installation

```bash
git clone https://github.com/aceyadapter/dopplersky-workers
cd dopplersky-workers
pip install -r requirements.txt
```

### Configuration

Copy the example environment file and configure your database connection:

```bash
cp .env.example .env
```

Edit `.env` with your database credentials:

```env
DB_HOST=localhost
DB_NAME=dopplersky_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_PORT=5432
```

### Database Setup

These scripts require a PostgreSQL database with registered users. Users are typically registered through the Dopplersky website registration form, but you can populate the `users` table however works best for your implementation.

Run the following SQL queries to create the necessary tables and indexes:

```sql
-- Users table
CREATE TABLE users (
    did VARCHAR(255) PRIMARY KEY,
    handle VARCHAR(255) UNIQUE NOT NULL,
    "displayName" VARCHAR(255),
    avatar TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    skip_user BOOLEAN DEFAULT FALSE
);

-- Posts table
CREATE TABLE posts (
    uri VARCHAR(500) PRIMARY KEY,
    did VARCHAR(255) REFERENCES users(did) ON DELETE CASCADE,
    likes INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    quotes INTEGER DEFAULT 0,
    reposts INTEGER DEFAULT 0,
    "createdAt" TIMESTAMP WITH TIME ZONE NOT NULL,
    "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Snapshots table
CREATE TABLE snapshots (
    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    did VARCHAR(255) REFERENCES users(did) ON DELETE CASCADE,
    date DATE NOT NULL,
    followers INTEGER DEFAULT 0,
    following INTEGER DEFAULT 0,
    posts INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    quotes INTEGER DEFAULT 0,
    reposts INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(did, date)
);

-- Views table (for tracking user activity)
CREATE TABLE views (
    id SERIAL PRIMARY KEY,
    did VARCHAR(255) REFERENCES users(did) ON DELETE CASCADE,
    date DATE NOT NULL,
    view_count INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(did, date)
);

-- Snapshot logs table
CREATE TABLE snapshot_logs (
    id INTEGER PRIMARY KEY,
    status VARCHAR(50) DEFAULT 'in_progress',
    time_started TIMESTAMP WITH TIME ZONE NOT NULL,
    time_completed TIMESTAMP WITH TIME ZONE,
    duration REAL,
    total_users INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

```sql
-- Performance indexes
CREATE INDEX idx_users_handle ON users(handle);
CREATE INDEX idx_users_last_active ON users(last_active);
CREATE INDEX idx_posts_did ON posts(did);
CREATE INDEX idx_posts_created_at ON posts("createdAt");
CREATE INDEX idx_snapshots_did_date ON snapshots(did, date);
CREATE INDEX idx_snapshots_date ON snapshots(date);
CREATE INDEX idx_views_did_date ON views(did, date);
CREATE INDEX idx_views_date ON views(date);
```

### Usage

#### Basic Usage

Run the snapshot collection for recently active users (default behavior):

```bash
python scripts/run_snapshots.py
```

By default, this processes only users who have been active within the past week to optimize server costs and API usage.

#### Process All Users

To update ALL registered users in the database:

```bash
python scripts/run_snapshots.py --simple-query
```

#### Additional Options

Run a health check to verify database and API connectivity:

```bash
python scripts/run_snapshots.py --health-check
```

Enable verbose logging for debugging:

```bash
python scripts/run_snapshots.py --verbose
```

Use a custom configuration file:

```bash
python scripts/run_snapshots.py --config .env.production
```

## How It Works

1. **User Selection** - Queries the database for users to process (recent activity or all users)
2. **Profile Updates** - Fetches current profile data from Bluesky API and updates changed information
3. **Post Collection** - Retrieves recent posts and updates engagement metrics
4. **Snapshot Creation** - Generates daily analytics snapshots with follower counts and engagement totals
5. **Logging** - Records execution details for monitoring and debugging

## Configuration Options

| Variable           | Default                     | Description                                     |
| ------------------ | --------------------------- | ----------------------------------------------- |
| `MAX_WORKERS`      | 10                          | Number of concurrent workers for processing     |
| `LOG_LEVEL`        | INFO                        | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `BLUESKY_BASE_URL` | https://public.api.bsky.app | Bluesky API endpoint                            |

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
