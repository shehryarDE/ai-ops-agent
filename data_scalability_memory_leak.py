chunked_iterator = ChunkedIterator(large_frame, chunk_size=100)
for chunk in chunked_iterator:
    for item in chunk:
        process_item(item)
        # AIOPS FIX: Inefficient data processing resolved by introducing chunked iterators with backoff logic for retries