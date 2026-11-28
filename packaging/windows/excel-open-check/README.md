# Excel open check

Saves workbooks with `gridz-cli` and opens each result in real Excel (COM), recording per file `PASS` or the
exact failure. Windows with Excel only. See `check.ps1` for the options.

```powershell
.\check.ps1 -Cli C:\gridz\gridz-cli.exe -Inputs C:\workbooks -Csv result.csv
```

Inputs are any `.xlsx`/`.xlsm` (the synthetic `gridz/` fixtures in a public fixtures repo are a good start); each
`*.jsonl` here is a feature scenario run on the Sales sample. Add a scenario by dropping in another `.jsonl`
(`gridz-cli run --script` format). Results: `Original` is the input opened in Excel (so a file Excel itself
rejects or loads slowly isn't blamed on GridZ), `Saved` is the GridZ-saved copy.
