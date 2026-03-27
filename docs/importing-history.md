## Importing Historical Messages

The bot only logs messages going forward. To backfill transcripts with
historical PBP messages, export the chat from Telegram Desktop and run
the import script.

### Steps

1. **Export from Telegram Desktop:**
   - Settings → Advanced → Export chat history
   - Select the Path_Wars supergroup
   - Format: **Machine-readable JSON**
   - Uncheck everything except "Text messages" (media metadata is preserved)
   - Click Export

2. **Run the import script:**
   ```bash
   # Preview what would be imported (no files written)
   python3 scripts/import_history.py path/to/result.json --dry-run

   # Actually import
   python3 scripts/import_history.py path/to/result.json
   ```

3. **Commit the transcripts:**
   ```bash
   git add data/pbp_logs
   git commit -m "Import historical PBP transcripts"
   git push
   ```

The script is idempotent — safe to run multiple times on the same export.
It tracks imported message IDs per campaign and only appends new ones.

---

