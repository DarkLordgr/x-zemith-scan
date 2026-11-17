# x-zemith-scan — ready-to-upload package

This repository runs a read-only X watchlist scan through TwitterAPI.io and
commits a Markdown digest. It cannot post, like, follow, repost, or send DMs.

## Upload to GitHub

1. Create a private repository named `x-zemith-scan`. Select **Add a README
   file** so the repository is not empty, then create it.
2. Extract the supplied ZIP on your computer. Inside the extracted
   `x-zemith-scan-upload` folder you should see:

   ```text
   scan_accounts.py
   test_scan_accounts.py
   accounts.txt
   README.md
   .github/workflows/x-scan.yml
   ```

   The `.github` folder may be hidden by your operating system. It is already
   inside the ZIP; do not rename or move it.
3. In the GitHub repository, choose **Add file → Upload files**. Drag the
   entire extracted `x-zemith-scan-upload` folder into the upload area, wait
   for every file to appear, then choose **Commit changes**.
4. Confirm the repository contains `.github/workflows/x-scan.yml`. If GitHub
   placed everything inside an extra `x-zemith-scan-upload/` folder, move the
   files to the repository root or start again by selecting the files and the
   `.github` folder inside the extracted folder.
5. Open **Settings → Secrets and variables → Actions → New repository
   secret**. Use the exact name `TWITTERAPI_IO_KEY` and your TwitterAPI.io key
   as the value. Never paste the key into chat or any repository file.
6. Open **Actions → X morning scan (TwitterAPI.io) → Run workflow**.

After a successful run, the repository contains `digest/latest.md` and a dated
copy under `digest/`. Edit `accounts.txt` to change the watchlist.

The schedule is 04:30 UTC daily: 06:30 Athens in winter and 07:30 in summer.
GitHub cron uses UTC and does not adjust automatically for daylight saving.
Each run scans the preceding 26 hours and can repeat a recent post across
consecutive digests.

## If the workflow does not appear

The workflow path must be exactly `.github/workflows/x-scan.yml` at the
repository root, with the other files at the root too. Do not leave the
supplied `workflow.yml` at the root; the ready-to-upload ZIP already places it
correctly.

## Reading results in Zemith

For a private repository, open `digest/latest.md` and paste its contents into
the chat when you want it used for research or content. The digest does not
automatically appear in Zemith. Never share your API key.
