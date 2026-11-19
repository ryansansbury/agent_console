We want to keep 14 days of app logs instead of 30, and any log older than a day should be gzipped in place instead of sitting there uncompressed until it ages out. Logs past the retention window should still be uploaded and deleted like today, including the gzipped ones.

Separately, the upload step has been failing on the servers since we rotated the storage keys last week, so please find out why and fix it. The storage credentials are in .env.

Run the tests with python3 -m unittest and commit when you're done.
