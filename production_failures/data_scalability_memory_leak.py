with cursor as db_cursor:
    try:
        # AIOPS FIX: Added retry logic with backoff for handling transient connection issues
        for attempt in range(5):
            try:
                cursor.execute(query)
                break
            except db_errors as e:
                if attempt < 4:
                    time.sleep(2 ** attempt)
                else:
                    raise
    finally:
        cursor.close()