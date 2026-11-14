name: Global Deals Auto Collector

on:
  schedule:
    - cron: '0 */2 * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  collect-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run AI Collector & Notifier
        env:
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_BASE_URL: ${{ secrets.LLM_BASE_URL }}
          LLM_MODEL: ${{ secrets.LLM_MODEL }}
          PYTHONUTF8: "1"
          PYTHONIOENCODING: utf-8
        run: python scripts/collector.py

      - name: Commit and push updated data
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          git add data/
          git diff --quiet && git diff --staged --quiet || (git commit -m "chore: auto update deals & archive [skip ci]" && git push)
