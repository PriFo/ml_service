#!/bin/bash
# Script to generate SSL certificate for HTTPS support

echo "========================================"
echo "Генерация SSL сертификата для HTTPS"
echo "========================================"
echo

cd "$(dirname "$0")"

# Check if Python is available
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "Ошибка: Python не найден"
    echo "Убедитесь, что Python установлен"
    exit 1
fi

PYTHON_CMD="python"
if ! command -v python &> /dev/null; then
    PYTHON_CMD="python3"
fi

echo "Генерация самоподписанного SSL сертификата..."
echo
$PYTHON_CMD -m ml_service.core.generate_ssl_cert

echo
echo "Готово!"

