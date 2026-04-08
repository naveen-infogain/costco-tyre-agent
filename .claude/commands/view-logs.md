# View agent logs

Display recent structured JSON logs from the Costco Tyre Agent.

## All logs (last 50 lines)

```bash
Get-ChildItem c:\Users\satti.naveen\costco-tyre-agent\app\logs\*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | ForEach-Object { Get-Content $_.FullName | ConvertFrom-Json | ConvertTo-Json -Depth 10 }
```

## Guardrail violation logs only

```bash
Get-Content c:\Users\satti.naveen\costco-tyre-agent\app\logs\guardrail.json -ErrorAction SilentlyContinue | ConvertFrom-Json | Where-Object { $_.level -eq 'violation' } | ConvertTo-Json
```

## Error logs only

```bash
Get-Content c:\Users\satti.naveen\costco-tyre-agent\app\logs\errors.json -ErrorAction SilentlyContinue | ConvertFrom-Json | ConvertTo-Json
```

## Count logs by type

```bash
Get-ChildItem c:\Users\satti.naveen\costco-tyre-agent\app\logs\ | ForEach-Object { "$($_.Name): $((Get-Content $_.FullName | ConvertFrom-Json).Count) entries" }
```
