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
  }>;
  processing_time_ms?: number;
  unexpected_items?: any[];
}

export default function PredictTab() {
  const { modal, showError, showSuccess } = useModal();
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedVersion, setSelectedVersion] = useState('');
  const [dataSource, setDataSource] = useState<'manual' | 'json'>('manual');
  const [jobId, setJobId] = useState<string | null>(null);
  const [data, setData] = useState<any[]>([]);
  const [jsonText, setJsonText] = useState('');
  const [models, setModels] = useState<Model[]>([]);
  const [modelDetails, setModelDetails] = useState<ModelDetails | null>(null);
  const [featureFields, setFeatureFields] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingFeatures, setLoadingFeatures] = useState(false);
  const [isPredicting, setIsPredicting] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

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
        try {
          const parsed = JSON.parse(details.feature_fields);
          if (Array.isArray(parsed)) {
            features = parsed;
          } else if (typeof parsed === 'object' && parsed.feature_fields) {
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

  const handleJsonParse = () => {
    try {
      const parsed = JSON.parse(jsonText);
      if (Array.isArray(parsed)) {
        setData(parsed);
        setError(null);
      } else if (typeof parsed === 'object' && parsed !== null) {
        // Если это объект, попробуем найти массив внутри
        const arrayKey = Object.keys(parsed).find(key => Array.isArray(parsed[key]));
        if (arrayKey) {
          setData(parsed[arrayKey]);
          setError(null);
        } else {
          // Если это один объект, обернем в массив
          setData([parsed]);
          setError(null);
        }
      } else {
        setError('JSON должен содержать массив объектов или объект');
      }
    } catch (e) {
      setError(`Ошибка парсинга JSON: ${(e as Error).message}`);
    }
  };

  const handleAddRow = () => {
    const newRow: any = {};
    featureFields.forEach(field => {
      newRow[field] = '';
    });
    setData([...data, newRow]);
  };

  const handleRemoveRow = (index: number) => {
    setData(data.filter((_, i) => i !== index));
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
    } catch (error) {
      console.error('Failed to start prediction:', error);
      await showError(`Ошибка запуска предсказания: ${(error as Error).message}`);
      setIsPredicting(false);
    }
  };

  const handleReset = () => {
    setData([]);
    setJsonText('');
    setResult(null);
    setError(null);
    setJobId(null);
    setIsPredicting(false);
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
      <div className={styles.predictTab}>
        <div className={styles.header}>
          <h2>Предсказание</h2>
          <button 
            className={styles.resetButton}
            onClick={handleReset}
            disabled={isPredicting}
          >
            Сбросить
          </button>
        </div>

        <div className={styles.container}>
          {/* Левая панель - выбор модели и данных */}
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
              <h3>2. Источник данных</h3>
              <div className={styles.radioGroup}>
                <label>
                  <input
                    type="radio"
                    value="manual"
                    checked={dataSource === 'manual'}
                    onChange={(e) => setDataSource(e.target.value as 'manual')}
                    disabled={isPredicting || !selectedModel}
                  />
                  Ручной ввод
                </label>
                <label>
                  <input
                    type="radio"
                    value="json"
                    checked={dataSource === 'json'}
                    onChange={(e) => setDataSource(e.target.value as 'json')}
                    disabled={isPredicting || !selectedModel}
                  />
                  JSON файл
                </label>
              </div>
            </div>

            <div className={styles.section}>
              <h3>3. Ввод данных</h3>
              {!selectedModel ? (
                <div className={styles.emptyState}>Сначала выберите модель</div>
              ) : featureFields.length === 0 ? (
                <div className={styles.emptyState}>Загрузка features модели...</div>
              ) : dataSource === 'manual' ? (
                <div className={styles.manualInput}>
                  <button 
                    className={styles.addButton}
                    onClick={handleAddRow}
                    disabled={isPredicting}
                  >
                    + Добавить строку
                  </button>
                  {data.length > 0 && (
                    <div className={styles.dataTableWrapper}>
                      <table className={styles.dataTable}>
                        <thead>
                          <tr>
                            <th>#</th>
                            {featureFields.map((field) => (
                              <th key={field}>{field}</th>
                            ))}
                            <th>Действия</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.map((row, index) => (
                            <tr key={index}>
                              <td className={styles.rowNumber}>{index + 1}</td>
                              {featureFields.map((field) => (
                                <td key={field}>
                                  <input
                                    type="text"
                                    value={row[field] || ''}
                                    onChange={(e) => handleFieldChange(index, field, e.target.value)}
                                    placeholder={field}
                                    disabled={isPredicting}
                                    className={styles.tableInput}
                                  />
                                </td>
                              ))}
                              <td>
                                <button
                                  className={styles.removeButton}
                                  onClick={() => handleRemoveRow(index)}
                                  disabled={isPredicting}
                                  title="Удалить строку"
                                >
                                  ×
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {data.length === 0 && (
                    <div className={styles.emptyState}>
                      Нажмите "Добавить строку" для начала ввода данных
                    </div>
                  )}
                </div>
              ) : (
                <div className={styles.jsonInput}>
                  <textarea
                    value={jsonText}
                    onChange={(e) => setJsonText(e.target.value)}
                    placeholder='[{"field1": "value1", "field2": "value2"}, ...]'
                    className={styles.jsonTextarea}
                    disabled={isPredicting}
                  />
                  <button
                    className={styles.parseButton}
                    onClick={handleJsonParse}
                    disabled={isPredicting || !jsonText.trim()}
                  >
                    Загрузить JSON
                  </button>
                  {data.length > 0 && (
                    <div className={styles.dataInfo}>
                      Загружено записей: {data.length}
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

          {/* Правая панель - результаты */}
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
                {result.processing_time_ms && (
                  <div className={styles.resultInfo}>
                    Время обработки: {result.processing_time_ms} мс
                  </div>
                )}
                {result.predictions && result.predictions.length > 0 && (
                  <div className={styles.predictionsTable}>
                    <table>
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Входные данные</th>
                          <th>Предсказание</th>
                          {result.predictions.some(p => p.confidence !== undefined) && (
                            <th>Уверенность</th>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {result.predictions.map((pred, index) => (
                          <tr key={index}>
                            <td>{index + 1}</td>
                            <td>
                              <pre className={styles.jsonPreview}>
                                {JSON.stringify(pred.input, null, 2)}
                              </pre>
                            </td>
                            <td>
                              <strong>{JSON.stringify(pred.prediction)}</strong>
                            </td>
                            {pred.confidence !== undefined && (
                              <td>{(pred.confidence * 100).toFixed(2)}%</td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
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
        </div>
      </div>
    </>
  );
}
