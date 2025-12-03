$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

git add -A
git commit -F COMMIT_MESSAGE.txt

Remove-Item COMMIT_MESSAGE.txt -ErrorAction SilentlyContinue
Remove-Item do_commit.ps1 -ErrorAction SilentlyContinue
Remove-Item do_commit.bat -ErrorAction SilentlyContinue

