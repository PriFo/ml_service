import { render, screen } from '@testing-library/react'
import Dashboard from '../Dashboard'
import { AppProvider } from '@/lib/store'

describe('Dashboard', () => {
  it('renders dashboard title', () => {
    render(
      <AppProvider>
        <Dashboard />
      </AppProvider>
    )
    
    expect(screen.getByText('ML Service v3.2')).toBeInTheDocument()
  })
})

