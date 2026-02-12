'use client';

import React, { useState, useEffect } from 'react';
import { useJob } from '@/lib/hooks/useJob';
import { api } from '@/lib/api';
import { useModal } from '@/lib/hooks/useModal';
import Modal from './Modal';
import ProgressBar from './ProgressBar';
import styles from './PredictTab.module.css';

interface Model {
  model_key: string;
  versions: string[];
  active_version: string;
  task_type?: string;
}

interface ModelDetails {
  model_key: string;
  version: string;
  feature_fields?: string;
  target_field?: string;
}

interface PredictionResult {
  predictions?: Array<{
    input: any;
    prediction: any;
    confidence?: number;
    all_scores?: Record<string, number>;
  }>;
  processing_time_ms?: number;
  unexpected_items?: any[];
}

export default function PredictTab() {
  const { modal, showError, showSuccess } = useModal();
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedVersion, setSelectedVersion] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [data, setData] = useState<any[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [modelDetails, setModelDetails] = useState<ModelDetails | null>(null);
  const [featureFields, setFeatureFields] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingFeatures, setLoadingFeatures] = useState(false);
  const [isPredicting, setIsPredicting] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'predict' | 'result'>('predict');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(50);
  const [dataCurrentPage, setDataCurrentPage] = useState(1);
  const [dataItemsPerPage, setDataItemsPerPage] = useState(50);
  const [fileUploadProgress, setFileUploadProgress] = useState<{
    isOpen: boolean;
    status: string;
  }>({ isOpen: false, status: '' });

  const { job } = useJob(jobId);

  useEffect(() => {
    loadModels();
    // Проверяем, есть ли сохраненная модель из ModelsTab
    const savedModel = localStorage.getItem('selectedModelForPredict');
    const savedVersion = localStorage.getItem('selectedVersionForPredict');
    if (savedModel) {
      setSelectedModel(savedModel);
      if (savedVersion) {
        setSelectedVersion(savedVersion);
      }
      localStorage.removeItem('selectedModelForPredict');
      localStorage.removeItem('selectedVersionForPredict');
    }
  }, []);

  useEffect(() => {
    // Загружаем features при выборе модели
    if (selectedModel) {
      loadModelFeatures();
    } else {
      setFeatureFields([]);
      setModelDetails(null);
      setData([]);
    }
  }, [selectedModel, selectedVersion]);

  useEffect(() => {
    // Проверяем статус джобы и загружаем результат
    if (job && job.status === 'completed' && jobId) {
      loadPredictionResult();
    } else if (job && job.status === 'failed') {
      setError(job.error_message || 'Предсказание завершилось с ошибкой');
      setIsPredicting(false);
    }
  }, [job, jobId]);

  const loadModels = async () => {
    setLoadingModels(true);
    try {
      const response = await api.getModels();
      setModels(response.models || []);
    } catch (error) {
      console.error('Failed to load models:', error);
      await showError(`Ошибка загрузки моделей: ${(error as Error).message}`);
    } finally {
      setLoadingModels(false);
    }
  };

  const loadModelFeatures = async () => {
    if (!selectedModel) return;
    
    setLoadingFeatures(true);
    try {
      const version = selectedVersion || models.find(m => m.model_key === selectedModel)?.active_version;
      const details = await api.getModelDetails(selectedModel, version);
      setModelDetails(details);
      
      // Парсим feature_fields
      let features: string[] = [];
      if (details.feature_fields) {
        // Если feature_fields уже массив, используем его напрямую
        if (Array.isArray(details.feature_fields)) {
          features = details.feature_fields;
        } else if (typeof details.feature_fields === 'string') {
          // Если это строка, пытаемся распарсить
          try {
            const parsed = JSON.parse(details.feature_fields);
            if (Array.isArray(parsed)) {
              features = parsed;
            } else if (typeof parsed === 'object' && parsed !== null && parsed.feature_fields) {
              features = Array.isArray(parsed.feature_fields) ? parsed.feature_fields : [];
            }
          } catch {
            // Попробуем парсить как строку Python списка
            try {
              const cleaned = details.feature_fields.replace(/[\[\]'"]/g, '');
              features = cleaned.split(',').map(f => f.trim()).filter(f => f);
            } catch {
              features = [];
            }
          }
        }
      }
      
      setFeatureFields(features);
      
      // Если есть данные, но они не соответствуют features, очищаем
      if (data.length > 0 && features.length > 0) {
        const hasValidStructure = data.every(row => 
          features.every(field => field in row)
        );
        if (!hasValidStructure) {
          setData([]);
        }
      }
    } catch (error) {
      console.error('Failed to load model features:', error);
      await showError(`Ошибка загрузки features модели: ${(error as Error).message}`);
      setFeatureFields([]);
      setModelDetails(null);
    } finally {
      setLoadingFeatures(false);
    }
  };

  const loadPredictionResult = async () => {
    if (!jobId) return;
    try {
      const response = await api.getPredictResult(jobId);
      setResult({
        predictions: response.predictions,
        processing_time_ms: response.processing_time_ms,
        unexpected_items: response.unexpected_items
      });
      setIsPredicting(false);
      if (response.predictions && response.predictions.length > 0) {
        await showSuccess('Предсказание успешно завершено!');
      }
    } catch (error) {
      console.error('Failed to load prediction result:', error);
      setError(`Ошибка загрузки результата: ${(error as Error).message}`);
      setIsPredicting(false);
    }
  };

  const selectedModelData = models.find(m => m.model_key === selectedModel);

  // Get all unique keys from loaded data for table display
  const getAllDataKeys = (): string[] => {
    if (data.length === 0) return [];
    const keys = new Set<string>();
    data.forEach(row => {
      Object.keys(row).forEach(key => keys.add(key));
    });
    return Array.from(keys);
  };

  const handleFileUpload = async (file: File, fileType: 'json' | 'csv') => {
    // Open progress modal
    setFileUploadProgress({ isOpen: true, status: 'Загрузка данных' });
    
    try {
      // Step 1: Load file
      await new Promise<void>((resolve, reject) => {
        const reader = new FileReader();
        
        reader.onload = async (e) => {
          try {
            setFileUploadProgress({ isOpen: true, status: 'Чтение данных' });
            
            // Small delay to show status update
            await new Promise(resolve => setTimeout(resolve, 100));
            
            const content = e.target?.result as string;
            let parsedData: any[] = [];

            if (fileType === 'json') {
              setFileUploadProgress({ isOpen: true, status: 'Парсинг JSON' });
              await new Promise(resolve => setTimeout(resolve, 50));
              
              const parsed = JSON.parse(content);
              if (Array.isArray(parsed)) {
                parsedData = parsed;
              } else if (typeof parsed === 'object' && parsed !== null) {
                // Если это объект, попробуем найти массив внутри
                const arrayKey = Object.keys(parsed).find(key => Array.isArray(parsed[key]));
                if (arrayKey) {
                  parsedData = parsed[arrayKey];
                } else {
                  // Если это один объект, обернем в массив
                  parsedData = [parsed];
                }
              } else {
                setFileUploadProgress({ isOpen: false, status: '' });
                setError('JSON должен содержать массив объектов или объект');
                reject(new Error('Invalid JSON format'));
                return;
              }
            } else if (fileType === 'csv') {
              setFileUploadProgress({ isOpen: true, status: 'Парсинг CSV' });
              await new Promise(resolve => setTimeout(resolve, 50));
              
              // Parse CSV
              const lines = content.split('\n').filter(line => line.trim());
              if (lines.length === 0) {
                setFileUploadProgress({ isOpen: false, status: '' });
                setError('CSV файл пуст');
                reject(new Error('CSV file is empty'));
                return;
              }

              // Parse CSV line (handle quoted values)
              const parseCSVLine = (line: string): string[] => {
                const result: string[] = [];
                let current = '';
                let inQuotes = false;

                for (let i = 0; i < line.length; i++) {
                  const char = line[i];
                  const nextChar = line[i + 1];

                  if (char === '"') {
                    if (inQuotes && nextChar === '"') {
                      current += '"';
                      i++; // Skip next quote
                    } else {
                      inQuotes = !inQuotes;
                    }
                  } else if (char === ',' && !inQuotes) {
                    result.push(current.trim());
                    current = '';
                  } else {
                    current += char;
                  }
                }
                result.push(current.trim());
                return result;
              };

              const headers = parseCSVLine(lines[0]).map(h => h.replace(/^"|"$/g, ''));
              
              // Process CSV in chunks to show progress
              const chunkSize = 1000;
              for (let i = 1; i < lines.length; i += chunkSize) {
                if (i % (chunkSize * 5) === 0) {
                  setFileUploadProgress({ 
                    isOpen: true, 
                    status: `Парсинг CSV: ${Math.min(i, lines.length - 1)} из ${lines.length - 1} строк` 
                  });
                  await new Promise(resolve => setTimeout(resolve, 10));
                }
                
                const endIndex = Math.min(i + chunkSize, lines.length);
                for (let j = i; j < endIndex; j++) {
                  const values = parseCSVLine(lines[j]).map(v => v.replace(/^"|"$/g, ''));
                  if (values.length !== headers.length) continue;

                  const row: any = {};
                  headers.forEach((header, index) => {
                    const value = values[index];
                    // Try to parse as number
                    const numValue = Number(value);
                    row[header] = value === '' ? null : (isNaN(numValue) ? value : numValue);
                  });
                  parsedData.push(row);
                }
              }
            }

            if (parsedData.length === 0) {
              setFileUploadProgress({ isOpen: false, status: '' });
              setError('Файл не содержит данных');
              reject(new Error('No data in file'));
              return;
            }

            setFileUploadProgress({ isOpen: true, status: 'Загрузка таблицы' });
            await new Promise(resolve => setTimeout(resolve, 100));
            
            setData(parsedData);
            setDataCurrentPage(1); // Reset to first page
            setError(null);
            
            setFileUploadProgress({ isOpen: true, status: 'Успешно' });
            await new Promise(resolve => setTimeout(resolve, 500));
            
            setFileUploadProgress({ isOpen: false, status: '' });
            await showSuccess(`Загружено ${parsedData.length} записей из файла`);
            resolve();
          } catch (error) {
            setFileUploadProgress({ isOpen: false, status: '' });
            setError(`Ошибка обработки файла: ${(error as Error).message}`);
            reject(error);
          }
        };

        reader.onerror = () => {
          setFileUploadProgress({ isOpen: false, status: '' });
          setError('Ошибка чтения файла');
          reject(new Error('File read error'));
        };

        reader.readAsText(file);
      });
    } catch (error) {
      setFileUploadProgress({ isOpen: false, status: '' });
      // Error already handled in reader.onload
    }
  };

  const handleJSONFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileUpload(file, 'json');
    }
    // Reset input to allow selecting the same file again
    e.target.value = '';
  };

  const handleCSVFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileUpload(file, 'csv');
    }
    // Reset input to allow selecting the same file again
    e.target.value = '';
  };

  const handleAddRow = () => {
    // Get all existing keys from current data to maintain structure
    const existingKeys = getAllDataKeys();
    const newRow: any = {};
    
    // If we have feature fields, use them; otherwise use existing keys
    const keysToUse = featureFields.length > 0 ? featureFields : existingKeys;
    keysToUse.forEach(field => {
      newRow[field] = '';
    });
    
    setData([...data, newRow]);
  };

  const handleRemoveRow = (index: number) => {
    const newData = data.filter((_, i) => i !== index);
    setData(newData);
    
    // Adjust page if needed - if we removed the last item on the current page, go to previous page
    const newTotalPages = Math.ceil(newData.length / dataItemsPerPage);
    if (dataCurrentPage > newTotalPages && newTotalPages > 0) {
      setDataCurrentPage(newTotalPages);
    } else if (newData.length === 0) {
      setDataCurrentPage(1);
    }
  };

  const handleFieldChange = (index: number, field: string, value: any) => {
    const newData = [...data];
    newData[index] = { ...newData[index], [field]: value };
    setData(newData);
  };

  const handlePredict = async () => {
    if (!selectedModel) {
      await showError('Выберите модель');
      return;
    }

    if (data.length === 0) {
      await showError('Добавьте данные для предсказания');
      return;
    }

    // Валидация: проверяем только что есть хотя бы одна строка данных
    // Недостающие поля будут обработаны бэкендом (заполнены значениями по умолчанию)
    const hasData = data.some(row => {
      // Проверяем что хотя бы одно поле заполнено
      return Object.values(row).some(value => 
        value !== undefined && value !== null && value !== ''
      );
    });
    
    if (!hasData) {
      await showError('Заполните хотя бы одно поле в данных');
      return;
    }

    try {
      setIsPredicting(true);
      setError(null);
      setResult(null);
      const version = selectedVersion || selectedModelData?.active_version;
      const response = await api.predict(selectedModel, data, version);
      setJobId(response.job_id);
      setActiveTab('result'); // Переключиться на вкладку результатов при начале предсказания
    } catch (error) {
      console.error('Failed to start prediction:', error);
      await showError(`Ошибка запуска предсказания: ${(error as Error).message}`);
      setIsPredicting(false);
    }
  };

  const handleReset = () => {
    setData([]);
    setResult(null);
    setError(null);
    setJobId(null);
    setIsPredicting(false);
    setCurrentPage(1);
  };

  // Pagination logic
  const totalItems = result?.predictions?.length || 0;
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const displayedPredictions = result?.predictions?.slice(startIndex, endIndex) || [];

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
    // Scroll to top of results section when page changes
    const resultsSection = document.querySelector(`.${styles.resultsSection}`);
    if (resultsSection) {
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleItemsPerPageChange = (newItemsPerPage: number) => {
    setItemsPerPage(newItemsPerPage);
    setCurrentPage(1); // Reset to first page when changing items per page
  };

  const handleExportJSON = () => {
    if (!result?.predictions || result.predictions.length === 0) {
      showError('Нет данных для экспорта');
      return;
    }

    // Convert standard format to merged format for export
    const targetField = modelDetails?.target_field || 'prediction';
    const dataToExport = result.predictions.map(p => ({
      ...(p.input || {}),
      [targetField]: p.prediction
    }));

    const blob = new Blob([JSON.stringify(dataToExport, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `predictions_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleExportCSV = () => {
    if (!result?.predictions || result.predictions.length === 0) {
      showError('Нет данных для экспорта');
      return;
    }

    // Convert standard format to merged format for export
    const targetField = modelDetails?.target_field || 'prediction';
    const dataToExport = result.predictions.map(p => ({
      ...(p.input || {}),
      [targetField]: p.prediction
    }));

    // Get all unique keys from all objects
    const allKeys = new Set<string>();
    dataToExport.forEach(item => {
      Object.keys(item).forEach(key => allKeys.add(key));
    });
    const headers = Array.from(allKeys);

    // Escape CSV value (handle commas, quotes, newlines)
    const escapeCSV = (value: any): string => {
      if (value === null || value === undefined) {
        return '';
      }
      const str = String(value);
      // If contains comma, quote, or newline, wrap in quotes and escape quotes
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    // Build CSV content
    const csvRows: string[] = [];
    
    // Header row
    csvRows.push(headers.map(escapeCSV).join(','));

    // Data rows
    dataToExport.forEach(item => {
      const row = headers.map(header => escapeCSV(item[header]));
      csvRows.push(row.join(','));
    });

    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `predictions_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Pagination for input data table
  const dataTotalItems = data.length;
  const dataTotalPages = Math.ceil(dataTotalItems / dataItemsPerPage);
  const dataStartIndex = (dataCurrentPage - 1) * dataItemsPerPage;
  const dataEndIndex = dataStartIndex + dataItemsPerPage;
  const displayedData = data.slice(dataStartIndex, dataEndIndex);

  const handleDataPageChange = (newPage: number) => {
    setDataCurrentPage(newPage);
  };

  const handleDataItemsPerPageChange = (newItemsPerPage: number) => {
    setDataItemsPerPage(newItemsPerPage);
    setDataCurrentPage(1);
  };

  return (
    <>
      <Modal
        isOpen={modal.isOpen}
        type={modal.type}
        title={modal.title}
        message={modal.message}
        onConfirm={modal.onConfirm}
        onCancel={modal.onCancel}
        confirmText={modal.confirmText}
        cancelText={modal.cancelText}
      />
      {/* File upload progress modal */}
      {fileUploadProgress.isOpen && (
        <div className={styles.progressModalBackdrop}>
          <div className={styles.progressModal}>
            <div className={styles.progressModalContent}>
              <div className={styles.progressSpinner}></div>
              <h3 className={styles.progressModalTitle}>Загрузка файла</h3>
              <p className={styles.progressModalStatus}>{fileUploadProgress.status}</p>
            </div>
          </div>
        </div>
      )}
      <div className={styles.predictTab}>
        <div className={styles.header}>
          <div className={styles.tabs}>
            <button
              className={`${styles.tab} ${activeTab === 'predict' ? styles.tabActive : ''}`}
              onClick={() => setActiveTab('predict')}
              disabled={isPredicting}
            >
              Предсказание
            </button>
            <button
              className={`${styles.tab} ${activeTab === 'result' ? styles.tabActive : ''}`}
              onClick={() => setActiveTab('result')}
              disabled={isPredicting}
            >
              Результат
            </button>
          </div>
          <button 
            className={styles.resetButton}
            onClick={handleReset}
            disabled={isPredicting}
          >
            Сбросить
          </button>
        </div>

        <div className={styles.container}>
          {activeTab === 'predict' && (
            <div className={styles.leftPanel}>
            <div className={styles.section}>
              <h3>1. Выбор модели</h3>
              {loadingModels ? (
                <div className={styles.loading}>Загрузка моделей...</div>
              ) : (
                <>
                  <select
                    value={selectedModel}
                    onChange={(e) => {
                      setSelectedModel(e.target.value);
                      setSelectedVersion('');
                      setData([]);
                    }}
                    className={styles.select}
                    disabled={isPredicting}
                  >
                    <option value="">Выберите модель...</option>
                    {models.map((model) => (
                      <option key={model.model_key} value={model.model_key}>
                        {model.model_key} {model.task_type ? `(${model.task_type})` : ''} - v{model.active_version}
                      </option>
                    ))}
                  </select>
                  {selectedModelData && selectedModelData.versions.length > 1 && (
                    <div className={styles.versionSelect}>
                      <label>Версия:</label>
                      <select
                        value={selectedVersion}
                        onChange={(e) => {
                          setSelectedVersion(e.target.value);
                          setData([]);
                        }}
                        className={styles.select}
                        disabled={isPredicting}
                      >
                        <option value="">Активная версия ({selectedModelData.active_version})</option>
                        {selectedModelData.versions.map((version) => (
                          <option key={version} value={version}>
                            v{version}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  {loadingFeatures && (
                    <div className={styles.loading}>Загрузка features...</div>
                  )}
                  {featureFields.length > 0 && (
                    <div className={styles.featuresInfo}>
                      <strong>Features модели:</strong> {featureFields.join(', ')}
                    </div>
                  )}
                </>
              )}
            </div>

            <div className={styles.section}>
              <h3>2. Загрузка данных</h3>
              <div className={styles.fileUploadButtons}>
                <label className={styles.fileUploadButton}>
                  <input
                    type="file"
                    accept=".json,application/json"
                    onChange={handleJSONFileSelect}
                    disabled={isPredicting}
                    style={{ display: 'none' }}
                  />
                  Загрузить JSON
                </label>
                <label className={styles.fileUploadButton}>
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={handleCSVFileSelect}
                    disabled={isPredicting}
                    style={{ display: 'none' }}
                  />
                  Загрузить CSV
                </label>
              </div>
            </div>

            <div className={styles.section}>
              <h3>3. Данные для предсказания</h3>
              {!selectedModel ? (
                <div className={styles.emptyState}>Сначала выберите модель</div>
              ) : (
                <div className={styles.dataInput}>
                  <div className={styles.dataControls}>
                    <button 
                      className={styles.addButton}
                      onClick={handleAddRow}
                      disabled={isPredicting}
                    >
                      + Добавить строку
                    </button>
                    {data.length > 0 && (
                      <div className={styles.dataInfo}>
                        Всего записей: {data.length}
                      </div>
                    )}
                  </div>
                  {data.length > 0 && (
                    <>
                      <div className={styles.paginationControls}>
                        <div className={styles.paginationInfo}>
                          Показано {dataStartIndex + 1}-{Math.min(dataEndIndex, dataTotalItems)} из {dataTotalItems} записей
                        </div>
                        <div className={styles.paginationOptions}>
                          <label>
                            На странице:
                            <select
                              value={dataItemsPerPage}
                              onChange={(e) => handleDataItemsPerPageChange(Number(e.target.value))}
                              className={styles.itemsPerPageSelect}
                            >
                              <option value={25}>25</option>
                              <option value={50}>50</option>
                              <option value={100}>100</option>
                              <option value={200}>200</option>
                            </select>
                          </label>
                        </div>
                      </div>
                      <div className={styles.dataTableWrapper}>
                        <table className={styles.dataTable}>
                          <thead>
                            <tr>
                              <th>#</th>
                              {getAllDataKeys().map((field) => (
                                <th key={field}>{field}</th>
                              ))}
                              <th>Действия</th>
                            </tr>
                          </thead>
                          <tbody>
                            {displayedData.map((row, index) => {
                              const actualIndex = dataStartIndex + index;
                              return (
                                <tr key={actualIndex}>
                                  <td className={styles.rowNumber}>{actualIndex + 1}</td>
                                  {getAllDataKeys().map((field) => (
                                    <td key={field}>
                                      <input
                                        type="text"
                                        value={row[field] !== null && row[field] !== undefined ? String(row[field]) : ''}
                                        onChange={(e) => handleFieldChange(actualIndex, field, e.target.value)}
                                        placeholder={field}
                                        disabled={isPredicting}
                                        className={styles.tableInput}
                                      />
                                    </td>
                                  ))}
                                  <td>
                                    <button
                                      className={styles.removeButton}
                                      onClick={() => handleRemoveRow(actualIndex)}
                                      disabled={isPredicting}
                                      title="Удалить строку"
                                    >
                                      ×
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      {dataTotalPages > 1 && (
                        <div className={styles.pagination}>
                          <button
                            className={styles.paginationButton}
                            onClick={() => handleDataPageChange(1)}
                            disabled={dataCurrentPage === 1}
                            title="Первая страница"
                          >
                            ««
                          </button>
                          <button
                            className={styles.paginationButton}
                            onClick={() => handleDataPageChange(dataCurrentPage - 1)}
                            disabled={dataCurrentPage === 1}
                            title="Предыдущая страница"
                          >
                            ‹
                          </button>
                          <span className={styles.paginationPageInfo}>
                            Страница{' '}
                            <input
                              type="number"
                              min={1}
                              max={dataTotalPages}
                              value={dataCurrentPage}
                              onChange={(e) => {
                                const page = parseInt(e.target.value);
                                if (page >= 1 && page <= dataTotalPages) {
                                  handleDataPageChange(page);
                                }
                              }}
                              className={styles.pageInput}
                            />
                            {' '}из {dataTotalPages}
                          </span>
                          <button
                            className={styles.paginationButton}
                            onClick={() => handleDataPageChange(dataCurrentPage + 1)}
                            disabled={dataCurrentPage === dataTotalPages}
                            title="Следующая страница"
                          >
                            ›
                          </button>
                          <button
                            className={styles.paginationButton}
                            onClick={() => handleDataPageChange(dataTotalPages)}
                            disabled={dataCurrentPage === dataTotalPages}
                            title="Последняя страница"
                          >
                            »»
                          </button>
                        </div>
                      )}
                    </>
                  )}
                  {data.length === 0 && (
                    <div className={styles.emptyState}>
                      Загрузите файл (JSON/CSV) или добавьте строку вручную
                    </div>
                  )}
                </div>
              )}
              {error && <div className={styles.error}>{error}</div>}
            </div>

            <div className={styles.section}>
              <button
                className={styles.predictButton}
                onClick={handlePredict}
                disabled={isPredicting || !selectedModel || data.length === 0 || featureFields.length === 0}
              >
                {isPredicting ? 'Выполняется...' : 'Выполнить предсказание'}
              </button>
            </div>
          </div>
          )}

          {activeTab === 'result' && (
            <div className={styles.rightPanel}>
            <h3>Результаты</h3>
            {isPredicting && job && (
              <div className={styles.progressSection}>
                <ProgressBar
                  progress={job.progress_current && job.progress_total 
                    ? Math.round((job.progress_current / job.progress_total) * 100)
                    : 0}
                  status={job.status as any}
                />
                <div className={styles.jobStatus}>
                  Статус: {job.status} {job.stage ? `(${job.stage})` : ''}
                </div>
              </div>
            )}
            {result && (
              <div className={styles.resultsSection}>
                <div className={styles.exportControls}>
                  <button
                    className={styles.exportButton}
                    onClick={handleExportJSON}
                    disabled={!result.predictions || result.predictions.length === 0}
                  >
                    Экспорт JSON
                  </button>
                  <button
                    className={styles.exportButton}
                    onClick={handleExportCSV}
                    disabled={!result.predictions || result.predictions.length === 0}
                  >
                    Экспорт CSV
                  </button>
                </div>
                {result.processing_time_ms && (
                  <div className={styles.resultInfo}>
                    Время обработки: {result.processing_time_ms} мс
                  </div>
                )}
                {result.predictions && result.predictions.length > 0 && (
                  <>
                    <div className={styles.paginationControls}>
                      <div className={styles.paginationInfo}>
                        Показано {startIndex + 1}-{Math.min(endIndex, totalItems)} из {totalItems} результатов
                      </div>
                      <div className={styles.paginationOptions}>
                        <label>
                          На странице:
                          <select
                            value={itemsPerPage}
                            onChange={(e) => handleItemsPerPageChange(Number(e.target.value))}
                            className={styles.itemsPerPageSelect}
                          >
                            <option value={10}>10</option>
                            <option value={25}>25</option>
                            <option value={50}>50</option>
                            <option value={100}>100</option>
                          </select>
                        </label>
                      </div>
                    </div>
                    <div className={styles.resultCards}>
                      {displayedPredictions.map((pred, index) => (
                        <div key={startIndex + index} className={styles.resultCard}>
                          <div className={styles.resultCardHeader}>
                            #{startIndex + index + 1}
                          </div>
                          <div className={styles.resultCardBody}>
                            <div className={`${styles.resultFrame} ${styles.resultFrameLeft}`}>
                              <div className={styles.resultFrameTitle}>Reference:</div>
                              <div className={styles.resultFrameContent}>
                                {pred.input && Object.entries(pred.input).map(([key, value]) => (
                                  <div key={key} className={styles.resultField}>
                                    <span className={styles.resultFieldKey}>{key}:</span>
                                    <span className={styles.resultFieldValue}>
                                      {value !== null && value !== undefined ? String(value) : 'null'}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                            <div className={`${styles.resultFrame} ${styles.resultFrameRight}`}>
                              <div className={styles.resultFrameTitle}>Output:</div>
                              <div className={styles.resultFrameContent}>
                                <div className={styles.resultField}>
                                  <span className={styles.resultFieldKey}>prediction:</span>
                                  <span className={styles.resultFieldValue}>
                                    {pred.prediction !== null && pred.prediction !== undefined 
                                      ? String(pred.prediction) 
                                      : 'null'}
                                  </span>
                                </div>
                                {pred.confidence !== undefined && (
                                  <div className={styles.resultField}>
                                    <span className={styles.resultFieldKey}>confidence:</span>
                                    <span className={styles.resultFieldValue}>
                                      {(pred.confidence * 100).toFixed(2)}%
                                    </span>
                                  </div>
                                )}
                                {pred.all_scores && Object.keys(pred.all_scores).length > 0 && (
                                  <>
                                    <div className={styles.allScoresDivider}></div>
                                    <div className={styles.allScores}>
                                      <div className={styles.allScoresTitle}>All Scores:</div>
                                      {Object.entries(pred.all_scores)
                                        .sort(([, a], [, b]) => (b as number) - (a as number))
                                        .map(([label, score]) => (
                                          <div key={label} className={styles.resultField}>
                                            <span className={styles.resultFieldKey}>{label}:</span>
                                            <span className={styles.resultFieldValue}>
                                              {((score as number) * 100).toFixed(2)}%
                                            </span>
                                          </div>
                                        ))}
                                    </div>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    {totalPages > 1 && (
                      <div className={styles.pagination}>
                        <button
                          className={styles.paginationButton}
                          onClick={() => handlePageChange(1)}
                          disabled={currentPage === 1}
                          title="Первая страница"
                        >
                          ««
                        </button>
                        <button
                          className={styles.paginationButton}
                          onClick={() => handlePageChange(currentPage - 1)}
                          disabled={currentPage === 1}
                          title="Предыдущая страница"
                        >
                          ‹
                        </button>
                        <span className={styles.paginationPageInfo}>
                          Страница{' '}
                          <input
                            type="number"
                            min={1}
                            max={totalPages}
                            value={currentPage}
                            onChange={(e) => {
                              const page = parseInt(e.target.value);
                              if (page >= 1 && page <= totalPages) {
                                handlePageChange(page);
                              }
                            }}
                            className={styles.pageInput}
                          />
                          {' '}из {totalPages}
                        </span>
                        <button
                          className={styles.paginationButton}
                          onClick={() => handlePageChange(currentPage + 1)}
                          disabled={currentPage === totalPages}
                          title="Следующая страница"
                        >
                          ›
                        </button>
                        <button
                          className={styles.paginationButton}
                          onClick={() => handlePageChange(totalPages)}
                          disabled={currentPage === totalPages}
                          title="Последняя страница"
                        >
                          »»
                        </button>
                      </div>
                    )}
                  </>
                )}
                {result.unexpected_items && result.unexpected_items.length > 0 && (
                  <div className={styles.unexpectedSection}>
                    <h4>Неожиданные элементы:</h4>
                    <pre className={styles.jsonPreview}>
                      {JSON.stringify(result.unexpected_items, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
            {!isPredicting && !result && (
              <div className={styles.emptyResults}>
                Результаты появятся здесь после выполнения предсказания
              </div>
            )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
