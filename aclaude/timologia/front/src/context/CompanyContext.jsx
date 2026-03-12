import { createContext, useContext, useState, useEffect } from 'react'
import { apiJson } from '../lib/api'

const CompanyContext = createContext(null)

export function CompanyProvider({ children }) {
  const [companies, setCompanies] = useState([])
  const [activeCompanyId, setActiveCompanyId] = useState(() => {
    const stored = localStorage.getItem('activeCompanyId')
    return stored ? Number(stored) : null
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiJson('/api/companies')
      .then((data) => {
        const list = data.companies || data || []
        setCompanies(list)
        if (!activeCompanyId && list.length > 0) {
          setActiveCompanyId(list[0].id)
          localStorage.setItem('activeCompanyId', String(list[0].id))
        }
      })
      .catch(() => setCompanies([]))
      .finally(() => setLoading(false))
  }, [])

  const selectCompany = (id) => {
    setActiveCompanyId(id)
    localStorage.setItem('activeCompanyId', String(id))
  }

  return (
    <CompanyContext.Provider value={{ companies, activeCompanyId, selectCompany, loading }}>
      {children}
    </CompanyContext.Provider>
  )
}

export function useCompany() {
  const ctx = useContext(CompanyContext)
  if (!ctx) throw new Error('useCompany must be used within CompanyProvider')
  return ctx
}
