import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { tenantApi } from '@/api/tenants'
import type { Tenant } from '@/api/types'

interface TenantContextValue {
  tenants: Tenant[]
  activeTenant: Tenant | null
  setActiveTenant: (t: Tenant) => void
  refreshTenants: () => void
  isLoading: boolean
}

const TenantContext = createContext<TenantContextValue | null>(null)

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient()
  const [activeSlug, setActiveSlug] = useState<string | null>(
    () => localStorage.getItem('activeSlug')
  )

  const { data: tenants = [], isLoading } = useQuery({
    queryKey: ['tenants'],
    queryFn: tenantApi.list,
  })

  const activeTenant = tenants.find((t) => t.slug === activeSlug) ?? tenants[0] ?? null

  // Inject brand color CSS variable
  useEffect(() => {
    if (activeTenant) {
      document.documentElement.style.setProperty('--brand-color', activeTenant.primary_color)
    }
  }, [activeTenant?.primary_color])

  const setActiveTenant = useCallback((t: Tenant) => {
    setActiveSlug(t.slug)
    localStorage.setItem('activeSlug', t.slug)
  }, [])

  const refreshTenants = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['tenants'] })
  }, [qc])

  return (
    <TenantContext.Provider
      value={{ tenants, activeTenant, setActiveTenant, refreshTenants, isLoading }}
    >
      {children}
    </TenantContext.Provider>
  )
}

export function useTenant() {
  const ctx = useContext(TenantContext)
  if (!ctx) throw new Error('useTenant must be used within TenantProvider')
  return ctx
}
