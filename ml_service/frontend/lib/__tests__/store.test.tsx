import { renderHook, act } from '@testing-library/react'
import { AppProvider, useAppStore } from '../store'

describe('AppStore', () => {
  it('initializes with default state', () => {
    const { result } = renderHook(() => useAppStore(), {
      wrapper: AppProvider,
    })
    
    expect(result.current.state.theme).toBe('system')
    expect(result.current.state.models).toEqual([])
    expect(result.current.state.alerts).toEqual([])
  })
  
  it('updates theme', () => {
    const { result } = renderHook(() => useAppStore(), {
      wrapper: AppProvider,
    })
    
    act(() => {
      result.current.dispatch({ type: 'SET_THEME', payload: 'dark' })
    })
    
    expect(result.current.state.theme).toBe('dark')
  })
  
  it('adds and removes alerts', () => {
    const { result } = renderHook(() => useAppStore(), {
      wrapper: AppProvider,
    })
    
    const alert = {
      alert_id: 'test-1',
      type: 'test',
      severity: 'info' as const,
      message: 'Test alert',
      created_at: new Date().toISOString(),
      dismissible: true,
    }
    
    act(() => {
      result.current.dispatch({ type: 'ADD_ALERT', payload: alert })
    })
    
    expect(result.current.state.alerts).toHaveLength(1)
    
    act(() => {
      result.current.dispatch({ type: 'REMOVE_ALERT', payload: 'test-1' })
    })
    
    expect(result.current.state.alerts).toHaveLength(0)
  })
})

