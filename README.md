# Metaculus-Bot-Pirohuni

Starting off from the basics:

1. Adapt API call functions from TemplateBot

Check Usage of OpenRouter here:
https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key?explorer=true

2. Edge case to test in future

https://www.metaculus.com/questions/42079/largest-gdpr-fine-till-2031/

3. Hit API call limit for metaculus. Need to fix that. Second question failed.

## Poetry export

If you need a `requirements.txt` for compatibility (pip, Docker, CI), export from Poetry:

```bash
poetry export -f requirements.txt --output requirements.txt --without-hashes
```

## Running locally without committing `.env`

You can run the bot locally without committing `.env`. Options:

- Put secrets in a local `.env` (it's gitignored) and the project uses `python-dotenv` to load it.
- Or set environment variables in your shell before running (safer than committing):

Windows PowerShell:

```powershell
$env:METACULUS_TOKEN = 'your_token_here'
poetry run python forecasting_bot.py --mode examples --no-submit
```

Windows CMD:

```cmd
set METACULUS_TOKEN=your_token_here
poetry run python forecasting_bot.py --mode examples --no-submit
```

Note: GitHub repository Settings → Secrets are for CI and Actions only; they do not set environment variables for your local terminal. Use a local `.env` or shell variables for local runs.
