# Инструкция по созданию публичного репозитория на GitHub

## Шаг 1: Инициализация Git репозитория

Выполните один из скриптов:

### Вариант A: PowerShell (рекомендуется)
```powershell
.\setup_git_repo.ps1
```

### Вариант B: Batch файл
```cmd
setup_git_repo.bat
```

### Вариант C: Вручную
```bash
git init
git add .
git commit -m "Initial commit: ML Service project"
```

## Шаг 2: Создание репозитория на GitHub

### Способ 1: Использование GitHub CLI (если установлен)

```bash
gh repo create ml_service --public --source=. --remote=origin --push
```

### Способ 2: Создание через веб-интерфейс GitHub

1. Перейдите на https://github.com/new
2. Заполните форму:
   - **Repository name**: `ml_service`
   - **Description**: (опционально) ML Service - сервис машинного обучения
   - **Visibility**: выберите **Public**
   - **НЕ** добавляйте README, .gitignore или лицензию (они уже есть)
3. Нажмите "Create repository"

4. После создания выполните команды:
```bash
git remote add origin https://github.com/YOUR_USERNAME/ml_service.git
git branch -M main
git push -u origin main
```

Замените `YOUR_USERNAME` на ваш GitHub username.

## Проверка

После выполнения всех команд проверьте, что репозиторий создан:
- Откройте https://github.com/YOUR_USERNAME/ml_service
- Убедитесь, что все файлы загружены
- Проверьте, что репозиторий публичный

## Примечания

- Убедитесь, что Git установлен: https://git-scm.com/download/win
- Для использования GitHub CLI установите: https://cli.github.com/
- Если возникнут проблемы с аутентификацией, используйте Personal Access Token

