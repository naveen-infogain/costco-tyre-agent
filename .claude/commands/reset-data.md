# Reset runtime data

Reset appointments and cart state back to clean defaults (useful for fresh demo runs).

## Reset appointments (clear all bookings)

```bash
echo '[]' > c:\Users\satti.naveen\costco-tyre-agent\app\data\appointments.json
echo "Appointments reset."
```

## Clear log files

```bash
Get-ChildItem c:\Users\satti.naveen\costco-tyre-agent\app\logs\*.json | ForEach-Object { '[]' | Set-Content $_.FullName }
echo "Logs cleared."
```

## Full reset (appointments + logs)

```bash
echo '[]' > c:\Users\satti.naveen\costco-tyre-agent\app\data\appointments.json
Get-ChildItem c:\Users\satti.naveen\costco-tyre-agent\app\logs\ -Filter "*.json" -ErrorAction SilentlyContinue | ForEach-Object { '[]' | Set-Content $_.FullName }
echo "Full reset complete. Restart the server to clear in-memory session state."
```

> Note: Cart state and sessions are in-memory — restart the server to clear those.
