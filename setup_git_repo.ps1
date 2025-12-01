# Скрипт для инициализации Git репозитория и создания на GitHub
# Установка кодировки UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "Инициализация Git репозитория..." -ForegroundColor Green

# Проверка наличия Git
try {
    $gitVersion = git --version
    Write-Host "Найден: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "Ошибка: Git не установлен или не найден в PATH" -ForegroundColor Red
    Write-Host "Пожалуйста, установите Git с https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

# Инициализация репозитория
Write-Host "`nИнициализация репозитория..." -ForegroundColor Cyan
git init
if ($LASTEXITCODE -ne 0) {
    Write-Host "Ошибка при инициализации репозитория" -ForegroundColor Red
    exit 1
}

# Добавление файлов
Write-Host "Добавление файлов в staging..." -ForegroundColor Cyan
git add .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Ошибка при добавлении файлов" -ForegroundColor Red
    exit 1
}

# Создание коммита
Write-Host "Создание начального коммита..." -ForegroundColor Cyan
git commit -m "Initial commit: ML Service project"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Ошибка при создании коммита" -ForegroundColor Red
    exit 1
}

Write-Host "`n✓ Git репозиторий успешно инициализирован!" -ForegroundColor Green
Write-Host "`nДля создания репозитория на GitHub:" -ForegroundColor Yellow
Write-Host "`n1. Если у вас установлен GitHub CLI (gh):" -ForegroundColor Cyan
Write-Host "   gh repo create ml_service --public --source=. --remote=origin --push" -ForegroundColor White
Write-Host "`n2. Или создайте репозиторий вручную на GitHub.com и выполните:" -ForegroundColor Cyan
Write-Host "   git remote add origin https://github.com/YOUR_USERNAME/ml_service.git" -ForegroundColor White
Write-Host "   git branch -M main" -ForegroundColor White
Write-Host "   git push -u origin main" -ForegroundColor White
Write-Host ""

