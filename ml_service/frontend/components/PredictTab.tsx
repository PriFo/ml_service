'use client';

import React, { useState, useEffect } from 'react';
import { useJob } from '@/lib/hooks/useJob';
import { api } from '@/lib/api';
import ProgressBar from './ProgressBar';
import styles from './PredictTab.module.css';

interface Model {
  model_key: string;
  versions: string[];
  active_version: string;
}

export default function PredictTab() {
  const [step, setStep] = useState(1);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedVersion, setSelectedVersion] = useState('');
  const [dataSource, setDataSource] = useState('manual');
  const [jobId, setJobId] = useState<string | null>(null);
  const [data, setData] = useState<any[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  const { job } = useJob(jobId);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    setLoadingModels(true);
    try {
      const response = await api.getModels();
      setModels(response.models || []);
    } catch (error) {
      console.error('Failed to load models:', error);
    } finally {
      setLoadingModels(false);
    }
  };

  const selectedModelData = models.find(m => m.model_key === selectedModel);

  const handlePredict = async () => {
    try {
      const version = selectedVersion || selectedModelData?.active_version;
      const response = await api.predict(selectedModel, data, version);
      setJobId(response.job_id);
      setStep(5);
    } catch (error) {
      console.error('Failed to start prediction:', error);
      alert(`Failed to start prediction: ${(error as Error).message}`);
    }
  };

  return (
    <div className={styles.predictTab}>
      {step === 1 && (
        <div>
          <h2>Step 1: Select Model</h2>
          {loadingModels ? (
            <div>Loading models...</div>
          ) : (
            <>
              <select
                value={selectedModel}
                onChange={(e) => {
                  setSelectedModel(e.target.value);
                  setSelectedVersion('');
                  if (e.target.value) setStep(2);
                }}
                className={styles.select}
              >
                <option value="">Select model...</option>
                {models.map((model) => (
                  <option key={model.model_key} value={model.model_key}>
                    {model.model_key} ({model.active_version})
                  </option>
                ))}
              </select>
              {selectedModelData && selectedModelData.versions.length > 1 && (
                <div className={styles.versionSelect}>
                  <label>Version:</label>
                  <select
                    value={selectedVersion}
                    onChange={(e) => setSelectedVersion(e.target.value)}
                    className={styles.select}
                  >
                    <option value="">Use active version ({selectedModelData.active_version})</option>
                    {selectedModelData.versions.map((version) => (
                      <option key={version} value={version}>
                        {version}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {step === 2 && (
        <div>
          <h2>Step 2: Select Data Source</h2>
          <div>
            <label>
              <input
                type="radio"
                value="manual"
                checked={dataSource === 'manual'}
                onChange={(e) => setDataSource(e.target.value)}
              />
              Manual
            </label>
            <label>
              <input
                type="radio"
                value="json"
                checked={dataSource === 'json'}
                onChange={(e) => setDataSource(e.target.value)}
              />
              JSON File
            </label>
          </div>
          <button onClick={() => setStep(3)}>Next</button>
        </div>
      )}

      {step === 3 && (
        <div>
          <h2>Step 3: Input Data</h2>
          {/* Data input UI would go here */}
          <button onClick={handlePredict}>Predict</button>
        </div>
      )}

      {step === 5 && job && (
        <div>
          <h2>Prediction Results</h2>
          <ProgressBar
            progress={job.progress?.percent || 0}
            status={job.status as any}
          />
          {job.status === 'completed' && (
            <div>Results: {JSON.stringify(job.result_payload)}</div>
          )}
        </div>
      )}
    </div>
  );
}

