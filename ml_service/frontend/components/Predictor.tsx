'use client';

import { useState, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import styles from './Predictor.module.css';

interface PredictionResult {
  input: Record<string, any>;
  prediction: string;
  confidence: number;
  all_scores: Record<string, number>;
}

type InputMode = 'manual' | 'file';

export default function Predictor() {
  const { state, dispatch } = useAppStore();
  const [selectedModelKey, setSelectedModelKey] = useState<string>('');
  const [selectedModelVersion, setSelectedModelVersion] = useState<string>('');
  const [inputMode, setInputMode] = useState<InputMode>('manual');
  const [inputData, setInputData] = useState<string>('');
  const [results, setResults] = useState<PredictionResult[]>([]);
  const [isPredicting, setIsPredicting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelDetails, setModelDetails] = useState<any>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [jobStage, setJobStage] = useState<string | null>(null);

  // Get active version from models list when model is selected
  useEffect(() => {
    if (selectedModelKey) {
      const model = state.models.find(m => m.model_key === selectedModelKey);
      if (model) {
        setSelectedModelVersion(model.active_version);
        loadModelDetails(selectedModelKey, model.active_version);
      }
    } else {
      setModelDetails(null);
      setSelectedModelVersion('');
    }
  }, [selectedModelKey, state.models]);

  const loadModelDetails = async (modelKey: string, version?: string) => {
    setIsLoadingDetails(true);
    try {
      const details = await api.getModelDetails(modelKey, version);
      setModelDetails(details);
      setError(null);
    } catch (error) {
      console.error('Failed to load model details:', error);
      setModelDetails(null);
      const errorMessage = (error as Error).message;
      setError(`Failed to load model details: ${errorMessage}`);
    } finally {
      setIsLoadingDetails(false);
    }
  };

  const parseCSV = (text: string): any[] => {
    const lines = text.trim().split('\n');
    if (lines.length < 2) {
      throw new Error('CSV file must have at least a header row and one data row');
    }

    const parseCSVLine = (line: string): string[] => {
      const result: string[] = [];
      let current = '';
      let inQuotes = false;

      for (let i = 0; i < line.length; i++) {
        const char = line[i];
        if (char === '"') {
          inQuotes = !inQuotes;
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
    const data: any[] = [];

    for (let i = 1; i < lines.length; i++) {
      const values = parseCSVLine(lines[i]).map(v => v.replace(/^"|"$/g, ''));
      if (values.length !== headers.length) continue;

      const row: any = {};
      headers.forEach((header, index) => {
        const value = values[index];
        // Skip label field - it's not used for prediction
        if (header.toLowerCase() === 'label') {
          return;
        }
        // Normalize empty values: empty string, whitespace, or null -> empty string for text fields
        // For numeric fields, keep as null
        const trimmedValue = value ? value.trim() : '';
        if (trimmedValue === '') {
          row[header] = '';
        } else {
          const numValue = Number(trimmedValue);
          row[header] = isNaN(numValue) ? trimmedValue : numValue;
        }
      });
      // Only add row if it has at least one non-label field
      if (Object.keys(row).length > 0) {
        data.push(row);
      }
    }

    return data;
  };

  const parseInputData = (text: string): any[] => {
    try {
      const parsed = JSON.parse(text);
      let data: any[] = [];
      
      // Handle different JSON structures
      if (Array.isArray(parsed)) {
        data = parsed;
      } else if (typeof parsed === 'object' && parsed !== null) {
        // Check if data is in a "data" field (like nomenclature_dataset_7000.json)
        if ('data' in parsed && Array.isArray(parsed.data)) {
          data = parsed.data;
        } else {
          // Single object
          data = [parsed];
        }
      } else {
        throw new Error('Invalid JSON format. Expected array or object.');
      }
      
      // Remove label field from all items and normalize empty values
      return data.map(item => {
        const cleaned: any = {};
        for (const [key, value] of Object.entries(item)) {
          // Skip label field
          if (key.toLowerCase() === 'label') {
            continue;
          }
          // Normalize empty values
          if (value === null || value === undefined || value === '') {
            cleaned[key] = '';
          } else {
            cleaned[key] = value;
          }
        }
        return cleaned;
      });
    } catch (e) {
      throw new Error('Invalid JSON format. Please provide valid JSON array or object.');
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string;
        let data: any[] = [];

        if (file.name.endsWith('.csv')) {
          data = parseCSV(text);
        } else if (file.name.endsWith('.json')) {
          data = parseInputData(text);
        } else {
          setError('Unsupported file format. Please upload CSV or JSON file.');
          return;
        }

        if (data.length === 0) {
          setError('File is empty or contains no valid data.');
          return;
        }

        setInputData(JSON.stringify(data, null, 2));
        setError(null);
      } catch (error) {
        const errorMessage = (error as Error).message;
        setError(`Failed to parse file: ${errorMessage}`);
      }
    };

    reader.onerror = () => {
      setError('Failed to read file.');
    };

    reader.readAsText(file);
  };

  const handlePredict = async () => {
    if (!selectedModelKey) {
      setError('Please select a model');
      return;
    }

    if (!inputData.trim()) {
      setError('Please provide input data');
      return;
    }

    setIsPredicting(true);
    setError(null);
    setResults([]);
    setCurrentJobId(null);
    setJobStatus(null);
    setJobStage(null);

    try {
      const data = parseInputData(inputData);
      const response = await api.predict(selectedModelKey, data, selectedModelVersion);
      
      // Job created, start polling for results
      setCurrentJobId(response.job_id);
      setJobStatus(response.status);
      setJobStage('queued');
      
      // Start polling for job completion
      pollPredictResult(response.job_id);
    } catch (error) {
      const errorMessage = (error as Error).message;
      setError(errorMessage);
      console.error('Prediction error:', error);
      setIsPredicting(false);
    }
  };

  const pollPredictResult = async (jobId: string) => {
    const maxAttempts = 300; // 5 minutes max (1 second intervals)
    let attempts = 0;

    const poll = async () => {
      try {
        const result = await api.getPredictResult(jobId);
        setJobStatus(result.status);
        
        // Update stage from job details if available
        try {
          const jobDetails = await api.getJobStatus(jobId);
          setJobStage(jobDetails.stage || result.status);
        } catch {
          // Ignore errors getting job details
        }

        if (result.status === 'completed') {
          // Job completed, get results
          if (result.predictions) {
            setResults(result.predictions);
            setError(null);
          } else {
            setError('Prediction completed but no results available');
          }
          setIsPredicting(false);
          setCurrentJobId(null);
        } else if (result.status === 'failed') {
          // Job failed
          setError(result.error_message || 'Prediction job failed');
          setIsPredicting(false);
          setCurrentJobId(null);
        } else if (result.status === 'running' || result.status === 'queued') {
          // Still processing, continue polling
          attempts++;
          if (attempts < maxAttempts) {
            setTimeout(poll, 1000); // Poll every second
          } else {
            setError('Prediction job is taking too long. Please check job status manually.');
            setIsPredicting(false);
          }
        }
      } catch (error) {
        const errorMessage = (error as Error).message;
        if (!errorMessage.includes('Unable to connect to backend')) {
          setError(`Failed to get prediction result: ${errorMessage}`);
          console.error('Polling error:', error);
        }
        setIsPredicting(false);
        setCurrentJobId(null);
      }
    };

    // Start polling
    poll();
  };

  const handleExample = () => {
    if (modelDetails && modelDetails.versions && modelDetails.versions.length > 0) {
      const currentVersion = modelDetails.versions.find((v: any) => v.version === (modelDetails.current_version || selectedModelVersion));
      const featureFields = currentVersion?.feature_fields;
      
      if (featureFields && featureFields.length > 0) {
        // Generate example with proper feature fields
        const example: Record<string, any> = {};
        featureFields.forEach((field: string) => {
          // Use appropriate default values based on field name
          if (field.toLowerCase().includes('id') || field.toLowerCase().includes('index')) {
            example[field] = 1;
          } else if (field.toLowerCase().includes('count') || field.toLowerCase().includes('num')) {
            example[field] = 0;
          } else if (field.toLowerCase().includes('flag') || field.toLowerCase().includes('is_')) {
            example[field] = false;
          } else {
            // Default to 0 for numeric, empty string for text
            example[field] = 0;
          }
        });
        setInputData(JSON.stringify([example], null, 2));
        setError(null);
      } else {
        setInputData(JSON.stringify([{ feature1: 0, feature2: 0 }], null, 2));
      }
    } else {
      setInputData(JSON.stringify([{ feature1: 0, feature2: 0 }], null, 2));
    }
  };

  const exportToJSON = () => {
    if (results.length === 0) return;

    const exportData = results.map((result, index) => ({
      index: index + 1,
      reference: result.input,
      prediction: result.prediction,
      confidence: result.confidence,
      all_scores: result.all_scores
    }));

    const jsonString = JSON.stringify(exportData, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `predictions_${selectedModelKey}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const exportToCSV = () => {
    if (results.length === 0) return;

    // Get all unique keys from input data (reference fields)
    const referenceKeys = new Set<string>();
    results.forEach(result => {
      Object.keys(result.input).forEach(key => referenceKeys.add(key));
    });

    // Get all score keys
    const scoreKeys = new Set<string>();
    results.forEach(result => {
      Object.keys(result.all_scores).forEach(key => scoreKeys.add(key));
    });

    // Create header row: index, reference fields (with prefix), prediction, confidence, scores
    const headers: string[] = ['index'];
    Array.from(referenceKeys).forEach(key => {
      headers.push(`reference_${key}`);
    });
    headers.push('prediction', 'confidence');
    Array.from(scoreKeys).forEach(key => {
      headers.push(`score_${key}`);
    });

    const csvRows: string[] = [headers.join(',')];

    // Create data rows
    results.forEach((result, index) => {
      const row: string[] = [];
      
      // Index
      row.push(String(index + 1));
      
      // Reference fields
      Array.from(referenceKeys).forEach(key => {
        const value = result.input[key] || '';
        row.push(escapeCSVValue(value));
      });
      
      // Prediction
      row.push(escapeCSVValue(result.prediction));
      
      // Confidence
      row.push(escapeCSVValue(result.confidence));
      
      // Scores
      Array.from(scoreKeys).forEach(key => {
        const value = result.all_scores[key] || '';
        row.push(escapeCSVValue(value));
      });
      
      csvRows.push(row.join(','));
    });

    const csvString = csvRows.join('\n');
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `predictions_${selectedModelKey}_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const escapeCSVValue = (value: any): string => {
    if (value === null || value === undefined) {
      return '';
    }
    
    const stringValue = String(value);
    
    // Escape CSV values (handle commas, quotes, newlines)
    if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
      return `"${stringValue.replace(/"/g, '""')}"`;
    }
    
    return stringValue;
  };

  const selectedModel = state.models.find(m => m.model_key === selectedModelKey);

  return (
    <div className={styles.predictor}>
      <div className={styles.header}>
        <h2 className={styles.title}>Model Prediction</h2>
        <p className={styles.subtitle}>Make predictions using trained models</p>
      </div>

      <div className={styles.content}>
        <div className={styles.formSection}>
          <div className={styles.inputGroup}>
            <label htmlFor="model-select">Select Model</label>
            <select
              id="model-select"
              value={selectedModelKey}
              onChange={(e) => setSelectedModelKey(e.target.value)}
              className={styles.select}
            >
              <option value="">-- Select a model --</option>
              {state.models.map(model => (
                <option key={model.model_key} value={model.model_key}>
                  {model.model_key} (v{model.active_version})
                </option>
              ))}
            </select>
          </div>

          {isLoadingDetails && (
            <div className={styles.loadingInfo}>Loading model details...</div>
          )}

          {modelDetails && !isLoadingDetails && (
            <div className={styles.modelInfo}>
              <h3 className={styles.infoTitle}>Model Information</h3>
              <div className={styles.infoGrid}>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Version:</span>
                  <span className={styles.infoValue}>
                    {modelDetails.current_version || selectedModelVersion || 'N/A'}
                  </span>
                </div>
                {modelDetails.versions && modelDetails.versions.length > 0 && (
                  <div className={styles.infoItem}>
                    <span className={styles.infoLabel}>Available Versions:</span>
                    <span className={styles.infoValue}>
                      {modelDetails.versions.map((v: any) => v.version).join(', ')}
                    </span>
                  </div>
                )}
                {modelDetails.versions && modelDetails.versions.length > 0 && (
                  <div className={styles.infoItem}>
                    <span className={styles.infoLabel}>Status:</span>
                    <span className={styles.infoValue}>
                      {modelDetails.versions.find((v: any) => v.version === (modelDetails.current_version || selectedModelVersion))?.status || 'unknown'}
                    </span>
                  </div>
                )}
                {modelDetails.versions && modelDetails.versions.length > 0 && (
                  <div className={styles.infoItem}>
                    <span className={styles.infoLabel}>Accuracy:</span>
                    <span className={styles.infoValue}>
                      {(() => {
                        const currentVersion = modelDetails.versions.find((v: any) => v.version === (modelDetails.current_version || selectedModelVersion));
                        const accuracy = currentVersion?.accuracy;
                        return accuracy !== null && accuracy !== undefined 
                          ? `${(accuracy * 100).toFixed(2)}%`
                          : 'N/A';
                      })()}
                    </span>
                  </div>
                )}
                {modelDetails.versions && modelDetails.versions.length > 0 && (() => {
                  const currentVersion = modelDetails.versions.find((v: any) => v.version === (modelDetails.current_version || selectedModelVersion));
                  const featureFields = currentVersion?.feature_fields;
                  return featureFields && featureFields.length > 0 ? (
                    <div className={styles.infoItem}>
                      <span className={styles.infoLabel}>Features ({featureFields.length}):</span>
                      <span className={styles.infoValue}>
                        {featureFields.join(', ')}
                      </span>
                    </div>
                  ) : null;
                })()}
              </div>
            </div>
          )}

          <div className={styles.inputGroup}>
            <label>Input Mode</label>
            <div className={styles.radioGroup}>
              <label className={styles.radioLabel}>
                <input
                  type="radio"
                  value="manual"
                  checked={inputMode === 'manual'}
                  onChange={(e) => setInputMode(e.target.value as InputMode)}
                />
                <span>Manual Input</span>
              </label>
              <label className={styles.radioLabel}>
                <input
                  type="radio"
                  value="file"
                  checked={inputMode === 'file'}
                  onChange={(e) => setInputMode(e.target.value as InputMode)}
                />
                <span>Upload File</span>
              </label>
            </div>
          </div>

          {inputMode === 'file' && (
            <div className={styles.inputGroup}>
              <label htmlFor="file-upload">Upload Data File (CSV or JSON)</label>
              <input
                id="file-upload"
                type="file"
                accept=".csv,.json"
                onChange={handleFileUpload}
                className={styles.fileInput}
              />
              <p className={styles.helpText}>
                Upload a CSV or JSON file. CSV should have headers matching feature field names.
              </p>
            </div>
          )}

          {inputMode === 'manual' && (
            <div className={styles.inputGroup}>
              <div className={styles.labelRow}>
                <label htmlFor="input-data">Input Data (JSON)</label>
                <button
                  type="button"
                  onClick={handleExample}
                  className={styles.exampleButton}
                  disabled={!selectedModelKey || !modelDetails}
                >
                  Load Example
                </button>
              </div>
              <textarea
                id="input-data"
                value={inputData}
                onChange={(e) => setInputData(e.target.value)}
                placeholder='[{"feature1": 1.0, "feature2": 2.0}, ...]'
                className={styles.textarea}
                rows={10}
              />
              <p className={styles.helpText}>
                Provide JSON array of objects. Each object should contain the feature fields.
              </p>
            </div>
          )}

          {inputData && inputMode === 'manual' && (
            <div className={styles.inputPreview}>
              <strong>Preview:</strong> {JSON.parse(inputData).length} item(s) loaded
            </div>
          )}

          {error && (
            <div className={styles.errorMessage}>
              <strong>Error:</strong> {error}
            </div>
          )}

          <button
            onClick={handlePredict}
            disabled={isPredicting || !selectedModelKey || !inputData.trim()}
            className={styles.predictButton}
          >
            {isPredicting ? (jobStage ? `Predicting... (${jobStage})` : 'Predicting...') : 'Make Prediction'}
          </button>

          {currentJobId && (
            <div className={styles.jobInfo}>
              <p><strong>Job ID:</strong> {currentJobId}</p>
              <p><strong>Status:</strong> {jobStatus}</p>
              {jobStage && <p><strong>Stage:</strong> {jobStage}</p>}
              <p className={styles.helpText}>
                Prediction is being processed. Results will appear here when ready.
              </p>
            </div>
          )}
        </div>

        {results.length > 0 && (
          <div className={styles.resultsSection}>
            <div className={styles.resultsHeader}>
              <h3 className={styles.resultsTitle}>Prediction Results</h3>
              <div className={styles.exportButtons}>
                <button
                  onClick={exportToJSON}
                  className={styles.exportButton}
                  title="Export to JSON"
                >
                  Export JSON
                </button>
                <button
                  onClick={exportToCSV}
                  className={styles.exportButton}
                  title="Export to CSV"
                >
                  Export CSV
                </button>
              </div>
            </div>
            <div className={styles.resultsGrid}>
              {results.map((result, index) => (
                <div key={index} className={styles.resultCard}>
                  <div className={styles.resultHeader}>
                    <span className={styles.resultIndex}>#{index + 1}</span>
                    <span className={styles.resultPrediction}>
                      {result.prediction}
                    </span>
                    <span className={styles.resultConfidence}>
                      {(result.confidence * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className={styles.resultInput}>
                    <strong>Input:</strong>
                    <pre className={styles.resultInputJson}>
                      {JSON.stringify(result.input, null, 2)}
                    </pre>
                  </div>
                  {Object.keys(result.all_scores).length > 1 && (
                    <div className={styles.resultScores}>
                      <strong>All Scores:</strong>
                      <div className={styles.scoresList}>
                        {Object.entries(result.all_scores)
                          .sort(([, a], [, b]) => b - a)
                          .map(([label, score]) => (
                            <div key={label} className={styles.scoreItem}>
                              <span className={styles.scoreLabel}>{label}:</span>
                              <span className={styles.scoreValue}>
                                {(score * 100).toFixed(2)}%
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
