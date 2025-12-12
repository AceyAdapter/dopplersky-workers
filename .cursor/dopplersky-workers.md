# Dopplersky Workers

## Purpose
- **What it is**: Backend workers that collect Bluesky social network analytics for [dopplersky.com](https://dopplersky.com)
- **Primary users**: Dopplersky platform users who want to track their Bluesky account analytics
- **Core workflows**:
  - Fetch user profiles from Bluesky API and sync to database
  - Collect post engagement metrics (likes, replies, quotes, reposts)
  - Create daily snapshots of follower counts and engagement totals
  - Track user activity via views table for selective processing
  - Log snapshot runs for monitoring and debugging

## Tech Stack
- **Runtime**: Python 3.8+
- **Frameworks**: None (stdlib + minimal dependencies)
- **Build tooling**: pip + requirements.txt
- **State/data**: PostgreSQL via psycopg2
- **Data processing**: pandas for post data manipulation
- **HTTP client**: requests
- **Config**: python-dotenv for environment variables
- **Testing**: None found

## Repo Map (high-signal)
| Area | Path(s) | Notes |
|---|---|---|
| Entry point | `scripts/run_snapshots.py` | CLI script, `SnapshotRunner` orchestrates the process |
| Configuration | `src/config/settings.py` | `AppConfig` + `DatabaseConfig` dataclasses, loads from env |
| API Client | `src/core/bluesky_client.py` | `BlueskyClient` wraps Bluesky public API |
| Database layer | `src/services/database_service.py` | `DatabaseService` handles all PostgreSQL operations |
| Post management | `src/services/post_service.py` | `PostService` fetches/updates post engagement data |
| Snapshot creation | `src/services/snapshot_service.py` | `SnapshotService` orchestrates user processing |
| Types/models | Inline dataclasses | `UserProfile`, `SnapshotData`, `DatabaseConfig` |
| Tests | — | None found |

## Architecture Overview
- **High-level flow**:
  ```
  CLI (run_snapshots.py)
    → SnapshotRunner
      → SnapshotService.create_snapshots_batch()
        → DatabaseService.get_active_users()     # Get users to process
        → BlueskyClient.get_profiles()           # Batch API calls (25 users/call)
        → ThreadPoolExecutor (parallel processing)
          → PostService.update_posts_for_actor() # Fetch/update posts
          → DatabaseService.upsert_snapshot()    # Store daily snapshot
  ```
- **Key boundaries**:
  - `BlueskyClient` owns all external API communication
  - `DatabaseService` owns all PostgreSQL operations
  - `PostService` bridges API and DB for post data
  - `SnapshotService` coordinates the snapshot workflow
- **Concurrency**: `ThreadPoolExecutor` with configurable `MAX_WORKERS` (default: 10)
- **Error handling**: Try/catch with logging at service boundaries; errors logged but don't halt batch processing
- **Logging**: Python `logging` module → stdout + `dopplersky.log` file

## Data Model / Schema

### Tables / Collections
| Name | Primary key | Important fields | Relationships | Where defined |
|---|---|---|---|---|
| `users` | `did` (VARCHAR 255) | `handle`, `displayName`, `avatar`, `last_active`, `skip_user` | Referenced by posts, snapshots, views | README.md (SQL) |
| `posts` | `uri` (VARCHAR 500) | `did`, `likes`, `replies`, `quotes`, `reposts`, `createdAt` | FK → `users(did)` | README.md (SQL) |
| `snapshots` | `uuid` (UUID) | `did`, `date`, `followers`, `following`, `posts`, `likes`, `replies`, `quotes`, `reposts` | FK → `users(did)`; UNIQUE(did, date) | README.md (SQL) |
| `views` | `id` (SERIAL) | `did`, `date`, `view_count` | FK → `users(did)`; UNIQUE(did, date) | README.md (SQL) |
| `snapshot_logs` | `id` (INTEGER) | `status`, `time_started`, `time_completed`, `duration`, `total_users` | — | README.md (SQL) |

### Key Indexes
| Index | Table | Columns | Purpose |
|---|---|---|---|
| `idx_users_handle` | users | handle | Fast handle lookup |
| `idx_users_last_active` | users | last_active | Activity filtering |
| `idx_posts_did` | posts | did | User's posts lookup |
| `idx_posts_created_at` | posts | createdAt | Recent posts filtering |
| `idx_snapshots_did_date` | snapshots | did, date | User snapshot lookup |
| `idx_views_did_date` | views | did, date | Activity-based user filtering |

### Migrations
- **Tooling**: Manual SQL (no migration framework)
- **Paths**: README.md contains CREATE TABLE statements
- **How to apply**: Copy SQL from README and run against PostgreSQL

## Auth
- **Provider**: None (uses Bluesky public API, no authentication required)
- **User registration**: Out of scope; users registered via dopplersky.com website
- **Access control**: `skip_user` boolean flag on users table

## API / Integrations

### Bluesky Public API
- **Base URL**: `https://public.api.bsky.app` (configurable via `BLUESKY_BASE_URL`)
- **Client**: `src/core/bluesky_client.py` → `BlueskyClient`
- **Endpoints used**:
  - `app.bsky.actor.getProfiles` — batch fetch user profiles (up to 25 DIDs)
  - `app.bsky.feed.getAuthorFeed` — fetch user's posts with pagination
- **Rate limiting**: Not explicitly handled; relies on batching (25 users/call)

### Database (PostgreSQL)
- **Client**: `psycopg2-binary`
- **Connection management**: Context manager in `DatabaseService.get_connection()`
- **Connection pooling**: None (new connection per operation)

## Local Development

### Requirements
- Python 3.8+
- PostgreSQL database with schema created
- Environment variables configured

### Setup
```bash
git clone https://github.com/aceyadapter/dopplersky-workers
cd dopplersky-workers
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database credentials
```

### Environment Variables
| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_HOST` | Yes | — | PostgreSQL host |
| `DB_NAME` | Yes | — | Database name |
| `DB_USER` | Yes | — | Database user |
| `DB_PASSWORD` | Yes | — | Database password |
| `DB_PORT` | No | `5432` | Database port |
| `MAX_WORKERS` | No | `10` | Concurrent thread pool workers |
| `BLUESKY_BASE_URL` | No | `https://public.api.bsky.app` | Bluesky API endpoint |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity (DEBUG/INFO/WARNING/ERROR) |

### Useful Commands
| Command | What it does |
|---|---|
| `python scripts/run_snapshots.py` | Run snapshot collection (active users only) |
| `python scripts/run_snapshots.py --simple-query` | Run for ALL users in database |
| `python scripts/run_snapshots.py --health-check` | Test database + API connectivity |
| `python scripts/run_snapshots.py --verbose` | Enable DEBUG logging |
| `python scripts/run_snapshots.py --config .env.prod` | Use specific env file |

## Testing
- **Unit tests**: None found
- **E2E tests**: None found
- **Manual testing**: Use `--health-check` flag to verify connectivity

## Deployment / Release
- **Environments**: Not configured (single env via `.env`)
- **Build**: N/A (Python scripts, no build step)
- **Hosting**: Not specified; designed to run as a cron job or scheduled task
- **Typical usage**: Run `python scripts/run_snapshots.py` daily via cron/scheduler

## Conventions
- **Type location**: Dataclasses defined inline with services (`UserProfile` in `bluesky_client.py`, `SnapshotData` in `database_service.py`)
- **Service pattern**: Each service class takes dependencies via constructor injection
- **Error handling**: Log and re-raise at service boundaries; batch processing continues on individual failures
- **Import style**: Absolute imports from `src.*`
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **SQL column names**: Mixed (`createdAt`, `updatedAt`, `displayName` use camelCase due to upstream conventions)

## Key Implementation Details

### User Selection Logic (`DatabaseService.get_active_users`)
- **Default (activity-based)**: Only users with views in last 7 days via JOIN on views table
- **Simple query (`--simple-query`)**: All users in users table

### Post Fetching Strategy (`PostService.get_posts_for_actor`)
- New users (0 posts in DB): Fetch all posts (up to 10,000)
- Existing users: Fetch posts from last 7 days only
- Filters out reposts (only includes posts authored by the user)

### Snapshot Upsert (`DatabaseService.upsert_snapshot`)
- Uses `INSERT ... ON CONFLICT` for atomic upsert
- Keyed on `(did, date)` unique constraint
- Prevents duplicate snapshots for same user/day

### Concurrent Processing (`SnapshotService.create_snapshots_batch`)
- Profiles fetched in batches of 25 (Bluesky API limit)
- User processing parallelized via `ThreadPoolExecutor`
- Each thread handles: profile update check → post updates → engagement totals → snapshot save

## Open Questions / TODOs
- **Connection pooling**: Currently creates new DB connection per operation; could benefit from connection pool
- **Rate limiting**: No explicit Bluesky API rate limiting; relies on batching
- **User registration flow**: Users must exist in DB; registration happens via external website
- **Retry logic**: No retries on API failures; failed users are skipped
- **Tests**: No test suite found; consider adding unit tests for services
