'use client';

import { useState, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import { useModal } from '@/lib/hooks/useModal';
import Modal from './Modal';
import styles from './AdminPanel.module.css';

interface Database {
  name: string;
  path: string;
  status: string;
  tables: string[];
}

interface TableData {
  table: string;
  columns: string[];
  data: any[];
  total: number;
  limit: number;
  offset: number;
}

function DatabaseManager() {
  const { state } = useAppStore();
  const { modal, showAlert, showError, showSuccess, showConfirm } = useModal();
  const [databases, setDatabases] = useState<Database[]>([]);
  const [selectedDb, setSelectedDb] = useState<string | null>(null);
  const [tables, setTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableData, setTableData] = useState<TableData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingRow, setEditingRow] = useState<any | null>(null);

  useEffect(() => {
    if (state.isAuthenticated && (state.userTier === 'admin' || state.userTier === 'system_admin')) {
      loadDatabases();
    }
  }, [state.isAuthenticated, state.userTier]);

  const loadDatabases = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.listDatabases();
      setDatabases(result.databases);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadTables = async (dbName: string) => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.listTables(dbName);
      setTables(result.tables.map(t => t.name));
      setSelectedTable(null);
      setTableData(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadTableData = async (dbName: string, tableName: string, offset: number = 0) => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getTableData(dbName, tableName, 100, offset);
      setTableData(result);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleDbSelect = (dbName: string) => {
    setSelectedDb(dbName);
    loadTables(dbName);
  };

  const handleTableSelect = (tableName: string) => {
    setSelectedTable(tableName);
    if (selectedDb) {
      loadTableData(selectedDb, tableName);
    }
  };

  const handleReconnect = async (dbName: string) => {
    try {
      setLoading(true);
      await api.reconnectDatabase(dbName);
      await loadDatabases();
      await showSuccess(`Database ${dbName} reconnected successfully`);
    } catch (err) {
      await showError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!selectedDb || !selectedTable || !editingRow) return;
    
    if (state.userTier !== 'system_admin' && state.userTier !== 'admin') {
      await showError('Only administrators can edit database data');
      return;
    }

    try {
      setLoading(true);
      await api.updateTableData(selectedDb, selectedTable, editingRow);
      await showSuccess('Data updated successfully');
      setEditingRow(null);
      if (selectedDb && selectedTable) {
        loadTableData(selectedDb, selectedTable, tableData?.offset || 0);
      }
    } catch (err) {
      await showError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (!state.isAuthenticated || (state.userTier !== 'admin' && state.userTier !== 'system_admin')) {
    return null;
  }

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
      <div className={styles.databaseManager}>
      <h4>Database Management</h4>
      
      {error && (
        <div className={styles.error} style={{ color: '#ef4444', marginBottom: '1rem' }}>
          Error: {error}
        </div>
      )}

      <div style={{ marginBottom: '1rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>
          Select Database:
        </label>
        <select
          value={selectedDb || ''}
          onChange={(e) => handleDbSelect(e.target.value)}
          style={{
            width: '100%',
            padding: '0.5rem',
            borderRadius: '4px',
            border: '1px solid var(--border-color)',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
          }}
        >
          <option value="">-- Select Database --</option>
          {databases.map(db => (
            <option key={db.name} value={db.name}>
              {db.name} ({db.status})
            </option>
          ))}
        </select>
      </div>

      {selectedDb && (
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <label style={{ fontWeight: 600 }}>Select Table:</label>
            <button
              onClick={() => handleReconnect(selectedDb)}
              style={{
                padding: '0.25rem 0.5rem',
                fontSize: '0.8rem',
                background: '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Reconnect
            </button>
          </div>
          <select
            value={selectedTable || ''}
            onChange={(e) => handleTableSelect(e.target.value)}
            style={{
              width: '100%',
              padding: '0.5rem',
              borderRadius: '4px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-primary)',
              color: 'var(--text-primary)',
            }}
          >
            <option value="">-- Select Table --</option>
            {tables.map(table => (
              <option key={table} value={table}>{table}</option>
            ))}
          </select>
        </div>
      )}

      {tableData && (
        <div style={{ marginTop: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <h5>Table: {tableData.table} ({tableData.total} rows)</h5>
            {(state.userTier === 'system_admin' || state.userTier === 'admin') && (
              <button
                onClick={() => setEditingRow(null)}
                style={{
                  padding: '0.25rem 0.5rem',
                  fontSize: '0.8rem',
                  background: '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                {editingRow ? 'Cancel Edit' : 'New Row'}
              </button>
            )}
          </div>
          
          <div style={{ overflowX: 'auto', maxHeight: '400px', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ background: 'var(--bg-primary)', position: 'sticky', top: 0 }}>
                  {tableData.columns.map(col => (
                    <th key={col} style={{ padding: '0.5rem', border: '1px solid var(--border-color)', textAlign: 'left' }}>
                      {col}
                    </th>
                  ))}
                  {(state.userTier === 'system_admin' || state.userTier === 'admin') && (
                    <th style={{ padding: '0.5rem', border: '1px solid var(--border-color)' }}>Actions</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {tableData.data.map((row, idx) => (
                  <tr key={idx}>
                    {tableData.columns.map(col => (
                      <td key={col} style={{ padding: '0.5rem', border: '1px solid var(--border-color)' }}>
                        {editingRow === row ? (
                          <input
                            type="text"
                            value={editingRow[col] || ''}
                            onChange={(e) => setEditingRow({ ...editingRow, [col]: e.target.value })}
                            style={{
                              width: '100%',
                              padding: '0.25rem',
                              border: '1px solid var(--border-color)',
                              borderRadius: '2px',
                            }}
                          />
                        ) : (
                          String(row[col] || '')
                        )}
                      </td>
                    ))}
                    {(state.userTier === 'system_admin' || state.userTier === 'admin') && (
                      <td style={{ padding: '0.5rem', border: '1px solid var(--border-color)' }}>
                        {editingRow === row ? (
                          <button
                            onClick={handleSaveEdit}
                            style={{
                              padding: '0.25rem 0.5rem',
                              fontSize: '0.75rem',
                              background: '#10b981',
                              color: 'white',
                              border: 'none',
                              borderRadius: '2px',
                              cursor: 'pointer',
                              marginRight: '0.25rem',
                            }}
                          >
                            Save
                          </button>
                        ) : (
                          <button
                            onClick={() => setEditingRow(row)}
                            style={{
                              padding: '0.25rem 0.5rem',
                              fontSize: '0.75rem',
                              background: '#3b82f6',
                              color: 'white',
                              border: 'none',
                              borderRadius: '2px',
                              cursor: 'pointer',
                            }}
                          >
                            Edit
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {tableData.total > tableData.limit && (
            <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
              <button
                onClick={() => selectedDb && selectedTable && loadTableData(selectedDb, selectedTable, Math.max(0, (tableData.offset || 0) - tableData.limit))}
                disabled={(tableData.offset || 0) === 0}
                style={{
                  padding: '0.5rem 1rem',
                  background: '#3b82f6',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: (tableData.offset || 0) === 0 ? 'not-allowed' : 'pointer',
                  opacity: (tableData.offset || 0) === 0 ? 0.5 : 1,
                }}
              >
                Previous
              </button>
              <span style={{ padding: '0.5rem', alignSelf: 'center' }}>
                Showing {tableData.offset + 1}-{Math.min(tableData.offset + tableData.limit, tableData.total)} of {tableData.total}
              </span>
              <button
                onClick={() => selectedDb && selectedTable && loadTableData(selectedDb, selectedTable, (tableData.offset || 0) + tableData.limit)}
                disabled={(tableData.offset || 0) + tableData.limit >= tableData.total}
                style={{
                  padding: '0.5rem 1rem',
                  background: '#3b82f6',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: (tableData.offset || 0) + tableData.limit >= tableData.total ? 'not-allowed' : 'pointer',
                  opacity: (tableData.offset || 0) + tableData.limit >= tableData.total ? 0.5 : 1,
                }}
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-secondary)' }}>
          Loading...
        </div>
      )}
      </div>
    </>
  );
}

export default function AdminPanel() {
  const { state } = useAppStore();
  const { modal, showConfirm, showSuccess, showError } = useModal();

  if (!state.isAuthenticated) {
    return null;
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8085';
  const docsUrl = `${apiUrl}/docs`;
  const redocUrl = `${apiUrl}/redoc`;

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
      <div className={styles.adminPanel}>
        <h3>Administrator Tools</h3>
        
        <div className={styles.tools}>
          <a
            href={docsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.toolLink}
          >
            📚 API Documentation (Swagger)
          </a>
          
          <a
            href={redocUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.toolLink}
          >
            📖 API Documentation (ReDoc)
          </a>
          
          <div className={styles.info}>
            <p><strong>Note:</strong> API documentation is only accessible to authenticated administrators.</p>
            <p>These pages provide interactive documentation for all API endpoints, including:</p>
            <ul>
              <li>Request/response schemas</li>
              <li>Try-it-out functionality</li>
              <li>Authentication requirements</li>
              <li>Error codes and messages</li>
            </ul>
          </div>

          <DatabaseManager />

          <div className={styles.dangerZone}>
            <h4>Danger Zone</h4>
            <button
              className={styles.dangerButton}
              onClick={async () => {
                const backup = await showConfirm('Create backup before recreating database?');
                const restore = backup && await showConfirm('Restore data from backup after recreation?');
                
                const confirmed = await showConfirm(
                  `WARNING: This will ${restore ? 'recreate' : 'DELETE ALL DATA'} in the database!\n\n` +
                  `Are you absolutely sure you want to proceed?`
                );
                
                if (!confirmed) {
                  return;
                }

                try {
                  const result = await api.recreateDatabase(backup, restore);
                  await showSuccess(
                    `Database recreated successfully!\n` +
                    (result.backup_path ? `Backup saved at: ${result.backup_path}` : '')
                  );
                  // Reload page to refresh data
                  window.location.reload();
                } catch (error) {
                  console.error('Failed to recreate database:', error);
                  await showError(`Failed to recreate database: ${(error as Error).message}`);
                }
              }}
            >
              🔄 Recreate Database
            </button>
            <p className={styles.warning}>
              This will delete all data and recreate the database schema. 
              Make sure to create a backup first!
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

