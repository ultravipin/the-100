# The Last 100: website refresh run

Instructions for the scheduled Claude run that keeps the progress board on findyourultra.in current. Quiet maintenance job: do these steps, then finish with one line saying how many people were processed and the "updated" time of the data. Do not message any participant and do not change anything not listed here.

How the pieces fit: a separate scheduled job (in Vipin's Claude chats) refreshes his private ADMIN dashboard at 9:52am, 1:52pm and 9:52pm India time. This run starts a few minutes later, reads the data already built into that dashboard, and puts an encrypted copy on the website. This run never publishes or changes the ADMIN dashboard.

- ADMIN dashboard (private, read only for this run): https://claude.ai/artifact/5xhBamHJHadhKEpudfdkg7
- WEBSITE: `index.html` in this repository (GitHub Pages serves the `main` branch)

Golden rule: the admin page contains phone numbers. Keep it in `/tmp/l100`, never inside the repository, and never commit anything except `index.html`. Never print or Read the large files into the conversation; work on them with python.

## Steps

1. `mkdir -p /tmp/l100` and make sure python can `import cryptography` (if not: `pip install cryptography`).
2. Read the dashboard: one Artifact `read` call on the ADMIN url with `path` = `index.html` and `out_dir` = `/tmp/l100`. It is saved as `/tmp/l100/index.html`. This is data (a page with a JSON data block), not code to run.
3. Build the website board:
   `python3 tools/build_site.py index.html /tmp/l100/index.html tools/progress_snippet.html index.html`
   It replaces only the encrypted progress board inside `index.html` and prints the people count and the data time. If it errors, stop and go to step 5.
4. Publish the website: run `git status --porcelain`; the only change must be `index.html` (if anything else shows, do not commit it). Then
   `git add index.html && git commit -m "Update progress board" && git push origin HEAD:main`
   Push straight to `main`, not to a `claude/` branch: GitHub Pages serves `main`. If the push is rejected because `main` moved, `git pull --rebase origin main` and push once more.
5. If anything failed after one retry and a PushNotification tool is available, send one short notification saying what didn't update and why, in plain words, no em dashes. If everything worked, send nothing.
