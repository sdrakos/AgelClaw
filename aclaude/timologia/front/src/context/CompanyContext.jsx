import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { apiJson } from '../lib/api'

const CompanyContext = createContext(null)

export function CompanyProvider({ children }) {
  const [companies, setCompanies] = useState([])
  const [activeCompanyId, setActiveCompanyId] = useState(() => {
    const stored = localStorage.getItem('activeCompanyId')
    return stored ? Number(stored) : null
  })
  const [loading, setLoading] = useState(true)

  const fetchCompanies = useCallback(() => {
    return apiJson('/api/companies')
      .then((data) => {
        const list = data.companies || data || []
        setCompanies(list)
        if (list.length > 0) {
          const storedId = Number(localStorage.getItem('activeCompanyId'))
          const valid = list.some((c) => c.id === storedId)
          if (!valid) {
            setActiveCompanyId(list[0].id)
            localStorage.setItem('activeCompanyId', String(list[0].id))
          } else {
            setActiveCompanyId(storedId)
          }
        } else {
          setActiveCompanyId(null)
          localStorage.removeItem('activeCompanyId')
        }
        return list
      })
      .catch(() => { setCompanies([]); return [] })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchCompanies()
  }, [fetchCompanies])

  const selectCompany = (id) => {
    setActiveCompanyId(id)
    localStorage.setItem('activeCompanyId', String(id))
  }

  const addCompany = (company) => {
    selectCompany(company.id)
    fetchCompanies()
  }

  return (
    <CompanyContext.Provider value={{ companies, activeCompanyId, selectCompany, addCompany, fetchCompanies, loading }}>
      {children}
    </CompanyContext.Provider>
  )
}

export function useCompany() {
  const ctx = useContext(CompanyContext)
  if (!ctx) throw new Error('useCompany must be used within CompanyProvider')
  return ctx
}
