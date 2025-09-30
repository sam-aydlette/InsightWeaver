# Database Migrations

This directory contains SQL migration scripts for InsightWeaver database schema changes.

## How to Apply Migrations

### SQLite (Current)

```bash
# Apply migration
sqlite3 your_database.db < migrations/001_add_content_filtering.sql

# Or using Python
python -c "
import sqlite3
conn = sqlite3.connect('your_database.db')
with open('migrations/001_add_content_filtering.sql', 'r') as f:
    conn.executescript(f.read())
conn.close()
"
```

### Migration List

| Migration | Description | Date |
|-----------|-------------|------|
| 001_add_content_filtering.sql | Add `filtered` and `filter_reason` columns | 2025-09-30 |

## Best Practices

1. **Always backup database before running migrations**
2. **Test migrations on a copy first**
3. **Migrations should be idempotent where possible**
4. **Document all schema changes**