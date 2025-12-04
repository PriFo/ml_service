'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import styles from './ModelsTab.module.css';

interface ModelVersion {
  version: string;
  accuracy?: number;
  last_trained?: string;
  status: string;
  task_type?: string;
  target_field?: string;
  feature_fields?: string;
  created_at?: string;
}

interface Model {
  model_key: string;
  versions: string[];
  active_version: string;
  status: string;
  accuracy?: number;
  last_trained?: string;
  task_type?: string;
  target_field?: string;
  feature_fields?: string;
  versionsDetails?: ModelVersion[];
}

interface ModelDetails {
  model_key: string;
  version: string;
  status: string;
  accuracy?: number;
  created_at?: string;
  last_trained?: string;
  last_updated?: string;
  task_type?: string;
  target_field?: string;
  feature_fields?: string;
  dataset_size?: number;
  training_file?: string;
}

interface ModelsTabProps {
  onNavigateToTraining?: () => void;
}

export default function ModelsTab({ onNavigateToTraining }: ModelsTabProps = {}) {
  const [models, setModels] = useState<Model[]>([]);
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const [expandedModels, setExpandedModels] = useState<Set<string>>(new Set());
  const [selectedModel, setSelectedModel] = useState<{ modelKey: string; version: string } | null>(null);
  const [modelDetails, setModelDetails] = useState<ModelDetails | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    try {
      setIsLoading(true);
      const response = await api.getModels();
      const modelsData = response.models || [];
      
      // Данные уже приходят с полными деталями версий из API
      setModels(modelsData as Model[]);
    } catch (error) {
      console.error('Failed to load models:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Группируем модели по task_type с нормализацией
  const modelsByTask = models.reduce((acc, model) => {
    let taskType = model.task_type || 'unknown';
    // Нормализуем task_type: classification -> CLASSIFICATION, regression -> REGRESSION
    if (taskType.toLowerCase() === 'classification') {
      taskType = 'CLASSIFICATION';
    } else if (taskType.toLowerCase() === 'regression') {
      taskType = 'REGRESSION';
    } else if (taskType && taskType !== 'unknown') {
      // Оставляем как есть, но делаем первую букву заглавной
      taskType = taskType.charAt(0).toUpperCase() + taskType.slice(1).toLowerCase();
    }
    if (!acc[taskType]) {
      acc[taskType] = [];
    }
    acc[taskType].push(model);
    return acc;
  }, {} as Record<string, Model[]>);

  const toggleTask = (taskType: string) => {
    const newExpanded = new Set(expandedTasks);
    if (newExpanded.has(taskType)) {
      newExpanded.delete(taskType);
    } else {
      newExpanded.add(taskType);
    }
    setExpandedTasks(newExpanded);
  };

  const toggleModel = (modelKey: string) => {
    const newExpanded = new Set(expandedModels);
    if (newExpanded.has(modelKey)) {
      newExpanded.delete(modelKey);
    } else {
      newExpanded.add(modelKey);
    }
    setExpandedModels(newExpanded);
  };

  const handleModelClick = async (modelKey: string, version: string) => {
    try {
      setIsLoading(true);
      // Сначала пытаемся использовать данные из уже загруженных versionsDetails
      const model = models.find(m => m.model_key === modelKey);
      const versionDetail = model?.versionsDetails?.find(v => v.version === version);
      
      if (versionDetail) {
        // Используем данные из кэша, но получаем training_file из API
        const apiDetails = await api.getModelDetails(modelKey, version);
        setModelDetails({
          ...versionDetail,
          model_key: modelKey,
          version: version,
          training_file: apiDetails.training_file || getTrainingFileName(modelKey, version)
        } as ModelDetails);
      } else {
        // Если данных нет в кэше, загружаем из API
        const details = await api.getModelDetails(modelKey, version);
        setModelDetails({
          model_key: modelKey,
          version: version,
          ...details
        } as ModelDetails);
      }
      setSelectedModel({ modelKey, version });
      setIsModalOpen(true);
    } catch (error) {
      console.error('Failed to load model details:', error);
      alert('Не удалось загрузить детали модели');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUseForPredict = () => {
    if (!selectedModel) return;
    setIsModalOpen(false);
    // Сохраняем выбранную модель в localStorage для PredictTab
    localStorage.setItem('selectedModelForPredict', selectedModel.modelKey);
    localStorage.setItem('selectedVersionForPredict', selectedModel.version);
    // Переход на вкладку Predict с выбранной моделью
    const event = new CustomEvent('navigate', { 
      detail: { 
        tab: 'predict',
        model: selectedModel.modelKey,
        version: selectedModel.version
      } 
    });
    window.dispatchEvent(event);
  };

  const handleRetrain = () => {
    if (!selectedModel) return;
    setIsModalOpen(false);
    // Сохраняем данные для переобучения в localStorage
    localStorage.setItem('retrainModel', selectedModel.modelKey);
    localStorage.setItem('retrainBaseVersion', selectedModel.version);
    // Переход на вкладку Training для переобучения
    const event = new CustomEvent('navigate', { 
      detail: { 
        tab: 'training',
        retrain: true,
        model: selectedModel.modelKey,
        baseVersion: selectedModel.version
      } 
    });
    window.dispatchEvent(event);
  };

  const handleDelete = async () => {
    if (!selectedModel) return;
    
    if (!confirm(`Вы уверены, что хотите удалить модель "${selectedModel.modelKey}" версии "${selectedModel.version}"? Это действие нельзя отменить.`)) {
      return;
    }

    try {
      setIsDeleting(true);
      await api.deleteModel(selectedModel.modelKey, true);
      alert('Модель успешно удалена');
      setIsModalOpen(false);
      setSelectedModel(null);
      setModelDetails(null);
      await loadModels();
    } catch (error: any) {
      console.error('Failed to delete model:', error);
      alert(`Не удалось удалить модель: ${error.message || 'Неизвестная ошибка'}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const parseFeatureFields = (featureFields?: string): string[] => {
    if (!featureFields) return [];
    try {
      const parsed = JSON.parse(featureFields);
      if (Array.isArray(parsed)) return parsed;
      return [];
    } catch {
      try {
        // Попытка парсинга как строки Python списка
        const cleaned = featureFields.replace(/[\[\]'"]/g, '');
        return cleaned.split(',').map(f => f.trim()).filter(f => f);
      } catch {
        return [];
      }
    }
  };

  const getTrainingFileName = (modelKey: string, version: string): string => {
    // Формируем имя файла модели на основе ключа и версии
    return `${modelKey}_v${version}.pkl`;
  };

  return (
    <div className={styles.modelsTab}>
      <div className={styles.header}>
        <h2>Модели</h2>
        <button 
          className={styles.newButton}
          onClick={() => {
            if (onNavigateToTraining) {
              onNavigateToTraining();
            } else {
              const event = new CustomEvent('navigate', { detail: { tab: 'training' } });
              window.dispatchEvent(event);
            }
          }}
        >
          + Новая модель
        </button>
      </div>

      {isLoading && !models.length && (
        <div className={styles.loading}>Загрузка моделей...</div>
      )}

      {!isLoading && Object.keys(modelsByTask).length === 0 && (
        <div className={styles.empty}>Нет доступных моделей</div>
      )}

      <div className={styles.tree}>
        {Object.entries(modelsByTask).map(([taskType, taskModels]) => (
          <div key={taskType} className={styles.taskNode}>
            <div 
              className={styles.taskHeader}
              onClick={() => toggleTask(taskType)}
            >
              <span className={styles.expandIcon}>
                {expandedTasks.has(taskType) ? '▼' : '▶'}
              </span>
              <span className={styles.taskName}>{taskType || 'Без типа'}</span>
              <span className={styles.modelCount}>({taskModels.length})</span>
            </div>
            
            {expandedTasks.has(taskType) && (
              <div className={styles.modelsContainer}>
                {taskModels.map((model) => (
                  <div key={model.model_key} className={styles.modelNode}>
                    <div 
                      className={styles.modelHeader}
                      onClick={() => toggleModel(model.model_key)}
                    >
                      <span className={styles.expandIcon}>
                        {expandedModels.has(model.model_key) ? '▼' : '▶'}
                      </span>
                      <span className={styles.modelName}>{model.model_key}</span>
                      <span className={styles.versionCount}>({model.versions.length} версий)</span>
                    </div>
                    
                    {expandedModels.has(model.model_key) && (
                      <div className={styles.versionsContainer}>
                        {model.versionsDetails && model.versionsDetails.length > 0 ? (
                          model.versionsDetails.map((versionDetail) => (
                            <div 
                              key={versionDetail.version}
                              className={styles.versionItem}
                              onClick={() => handleModelClick(model.model_key, versionDetail.version)}
                            >
                              <span className={styles.versionName}>
                                v{versionDetail.version}
                                {versionDetail.version === model.active_version && (
                                  <span className={styles.activeBadge}>активная</span>
                                )}
                              </span>
                              {versionDetail.accuracy !== null && versionDetail.accuracy !== undefined && (
                                <span className={styles.accuracy}>
                                  Точность: {(versionDetail.accuracy * 100).toFixed(2)}%
                                </span>
                              )}
                            </div>
                          ))
                        ) : (
                          model.versions.map((version) => (
                            <div 
                              key={version}
                              className={styles.versionItem}
                              onClick={() => handleModelClick(model.model_key, version)}
                            >
                              <span className={styles.versionName}>
                                v{version}
                                {version === model.active_version && (
                                  <span className={styles.activeBadge}>активная</span>
                                )}
                              </span>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Модальное окно с деталями модели */}
      {isModalOpen && modelDetails && (
        <div className={styles.modalOverlay} onClick={() => setIsModalOpen(false)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>Детали модели</h3>
              <button 
                className={styles.closeButton}
                onClick={() => setIsModalOpen(false)}
                aria-label="Закрыть"
              >
                ×
              </button>
            </div>

            <div className={styles.modalBody}>
              <div className={styles.detailsSection}>
                <h4>Основная информация</h4>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Ключ модели:</span>
                  <span className={styles.detailValue}>{modelDetails.model_key}</span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Версия:</span>
                  <span className={styles.detailValue}>{modelDetails.version}</span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Статус:</span>
                  <span className={styles.detailValue}>{modelDetails.status}</span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Тип задачи:</span>
                  <span className={styles.detailValue}>
                    {modelDetails.task_type 
                      ? (modelDetails.task_type.toLowerCase() === 'classification' ? 'CLASSIFICATION' 
                         : modelDetails.task_type.toLowerCase() === 'regression' ? 'REGRESSION'
                         : modelDetails.task_type)
                      : 'Не указан'}
                  </span>
                </div>
              </div>

              <div className={styles.detailsSection}>
                <h4>Характеристики</h4>
                {modelDetails.accuracy !== null && modelDetails.accuracy !== undefined && (
                  <div className={styles.detailRow}>
                    <span className={styles.detailLabel}>Точность:</span>
                    <span className={styles.detailValue}>{(modelDetails.accuracy * 100).toFixed(2)}%</span>
                  </div>
                )}
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Целевое поле:</span>
                  <span className={styles.detailValue}>{modelDetails.target_field || 'Не указано'}</span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Признаки (фичи):</span>
                  <div className={styles.featuresList}>
                    {parseFeatureFields(modelDetails.feature_fields).length > 0 ? (
                      parseFeatureFields(modelDetails.feature_fields).map((feature, idx) => (
                        <span key={idx} className={styles.featureTag}>{feature}</span>
                      ))
                    ) : (
                      <span className={styles.noData}>Не указаны</span>
                    )}
                  </div>
                </div>
              </div>

              <div className={styles.detailsSection}>
                <h4>Данные обучения</h4>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Размер датасета:</span>
                  <span className={styles.detailValue}>
                    {modelDetails.dataset_size ? `${modelDetails.dataset_size} записей` : 'Не указан'}
                  </span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Файл модели:</span>
                  <span className={styles.detailValue}>
                    {getTrainingFileName(modelDetails.model_key, modelDetails.version)}
                  </span>
                </div>
              </div>

              <div className={styles.detailsSection}>
                <h4>Даты</h4>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Создана:</span>
                  <span className={styles.detailValue}>
                    {modelDetails.created_at 
                      ? new Date(modelDetails.created_at).toLocaleString('ru-RU')
                      : 'Не указана'}
                  </span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Обучена:</span>
                  <span className={styles.detailValue}>
                    {modelDetails.last_trained 
                      ? new Date(modelDetails.last_trained).toLocaleString('ru-RU')
                      : 'Не указана'}
                  </span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Обновлена:</span>
                  <span className={styles.detailValue}>
                    {modelDetails.last_updated 
                      ? new Date(modelDetails.last_updated).toLocaleString('ru-RU')
                      : 'Не указана'}
                  </span>
                </div>
              </div>
            </div>

            <div className={styles.modalFooter}>
              <button 
                className={styles.actionButton}
                onClick={handleUseForPredict}
                disabled={isLoading}
              >
                Использовать для предикта
              </button>
              <button 
                className={styles.actionButton}
                onClick={handleRetrain}
                disabled={isLoading}
              >
                Переобучить модель
              </button>
              <button 
                className={`${styles.actionButton} ${styles.deleteButton}`}
                onClick={handleDelete}
                disabled={isLoading || isDeleting}
              >
                {isDeleting ? 'Удаление...' : 'Удалить модель'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
