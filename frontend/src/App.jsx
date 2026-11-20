import { useEffect, useState } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'
const REFRESH_TOKEN_KEY = 'contractcommand.refreshToken'
const AUTH_REQUIRED_EVENT = 'contractcommand:auth-required'
let accessToken = null
let refreshRequest = null

const MODULES = [
  { name: 'Contracts', endpoint: 'contracts', reference: 'contract_number', singular: 'Contract' },
  { name: 'Requisitions', endpoint: 'requisitions', reference: 'requisition_number', singular: 'Requisition' },
  { name: 'Vendors', endpoint: 'vendors', reference: 'name', singular: 'Vendor' },
  { name: 'Invoices', endpoint: 'invoices', reference: 'invoice_number', singular: 'Invoice' },
  { name: 'Quotation Requests', endpoint: 'quotation-requests', reference: 'request_number', singular: 'Quotation Request' },
  { name: 'Vendor Quotes', endpoint: 'vendor-quotes', reference: 'request_number', singular: 'Vendor Quote' },
  { name: 'Purchase Orders', endpoint: 'purchase-orders', reference: 'po_number', singular: 'Purchase Order' },
  { name: 'Approvals', endpoint: 'approvals', reference: 'po_number', singular: 'Approval' },
  { name: 'Deliveries', endpoint: 'deliveries', reference: 'delivery_number', singular: 'Delivery' },
  { name: 'Payment Sessions', endpoint: 'payment-sessions', reference: 'session_id', singular: 'Payment Session' },
  { name: 'Documents', endpoint: 'documents', reference: 'original_filename', singular: 'Document' },
  { name: 'Notifications', endpoint: 'notifications', reference: 'notification_type', singular: 'Notification' },
  { name: 'Audit History', endpoint: 'audit-logs', reference: 'object_label', singular: 'Audit Event' },
  { name: 'Reports', endpoint: 'reports', reference: 'status', singular: 'Report' },
]

function modulesFor(user) {
  return MODULES.filter(module => user?.capabilities?.[module.endpoint]?.includes('read'))
}

function dataModulesFor(user) {
  return modulesFor(user).filter(module => module.name !== 'Reports')
}

function canAccess(user, module, action) {
  return Boolean(user?.capabilities?.[module.endpoint]?.includes(action))
}

function moduleFor(name) {
  return MODULES.find(module => module.name === name)
}

function saveTokens(tokens) {
  accessToken = tokens.access
  sessionStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh)
}

function clearTokens() {
  accessToken = null
  refreshRequest = null
  sessionStorage.removeItem(REFRESH_TOKEN_KEY)
}

async function refreshAccessToken() {
  const refresh = sessionStorage.getItem(REFRESH_TOKEN_KEY)
  if (!refresh) return null
  if (!refreshRequest) {
    refreshRequest = fetch(`${API_BASE_URL}/auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    }).then(async response => {
      if (!response.ok) {
        clearTokens()
        throw new Error(await responseError(response))
      }
      const tokens = await response.json()
      accessToken = tokens.access
      return accessToken
    }).finally(() => {
      refreshRequest = null
    })
  }
  return refreshRequest
}

async function apiFetch(path, { method = 'GET', body, signal } = {}) {
  const headers = {}
  const isFormData = body instanceof FormData
  if (body !== undefined && !isFormData) headers['Content-Type'] = 'application/json'
  const request = token => fetch(`${API_BASE_URL}${path}`, {
    method,
    body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
    headers: token ? { ...headers, Authorization: `Bearer ${token}` } : headers,
    signal,
  })
  let response = await request(accessToken)
  if (response.status === 401 && !path.includes('/auth/token')) {
    try {
      const refreshedAccess = await refreshAccessToken()
      if (refreshedAccess) {
        response = await request(refreshedAccess)
        if (response.status === 401) {
          clearTokens()
          window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT))
        }
      } else {
        window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT))
      }
    } catch {
      if (!sessionStorage.getItem(REFRESH_TOKEN_KEY)) {
        window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT))
      }
      return response
    }
  }
  return response
}

async function responseError(response) {
  const payload = await response.json().catch(() => ({}))
  if (payload.detail) return payload.detail
  const errors = Object.entries(payload).flatMap(([field, messages]) =>
    (Array.isArray(messages) ? messages : [messages]).map(message => `${field}: ${message}`),
  )
  return errors.join(' ') || `Request failed (${response.status}).`
}

function referenceFor(record, moduleName) {
  const module = MODULES.find(item => item.name === moduleName)
  return record[module?.reference] || record.registration_number || `Record ${record.id}`
}

function statusFor(record) {
  if (record.read_at !== undefined) return record.read_at ? 'Read' : 'Unread'
  if (record.document_type) return 'Stored'
  if (record.action) return record.action
  if (record.status) return record.status
  return record.approved ? 'Approved' : 'Pending review'
}

function ownerFor(record, moduleName) {
  if (moduleName === 'Contracts') return record.owner_username || '—'
  if (moduleName === 'Requisitions') return record.requested_by_username || '—'
  if (moduleName === 'Vendors') return record.registration_number || '—'
  if (moduleName === 'Quotation Requests') return record.requisition_number || '—'
  if (moduleName === 'Approvals') return record.approver_username || '—'
  if (moduleName === 'Deliveries') return record.po_number || '—'
  if (moduleName === 'Payment Sessions') return record.invoice_number || '—'
  if (moduleName === 'Documents') return record.uploaded_by_username || '—'
  if (moduleName === 'Audit History') return record.username || '—'
  return record.vendor_name || '—'
}

function App() {
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loginPending, setLoginPending] = useState(false)
  const [active, setActive] = useState('Overview')
  const [records, setRecords] = useState([])
  const [overviewRecords, setOverviewRecords] = useState([])
  const [counts, setCounts] = useState({})
  const [lookups, setLookups] = useState({
    vendors: [],
    contracts: [],
    requisitions: [],
    quotationRequests: [],
    vendorQuotes: [],
    purchaseOrders: [],
    invoices: [],
    deliveries: [],
  })
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [pageError, setPageError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [modal, setModal] = useState(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [reportData, setReportData] = useState(null)
  const [reportFilters, setReportFilters] = useState({
    date_from: '',
    date_to: '',
    status: '',
  })

  useEffect(() => {
    const handleAuthRequired = () => {
      setUser(null)
      setActive('Overview')
      setRecords([])
      setOverviewRecords([])
      setCounts({})
      setPageError('')
      setAuthError('Your session expired. Please sign in again.')
    }
    window.addEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired)
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired)
  }, [])

  useEffect(() => {
    let cancelled = false
    async function restoreSession() {
      try {
        if (!sessionStorage.getItem(REFRESH_TOKEN_KEY)) return
        const restoredAccess = await refreshAccessToken()
        if (!restoredAccess) return
        const response = await apiFetch('/auth/me/')
        if (cancelled) return
        if (response.status === 401) {
          clearTokens()
          setUser(null)
          return
        }
        if (!response.ok) throw new Error(await responseError(response))
        setUser(await response.json())
      } catch {
        if (!cancelled) {
          if (sessionStorage.getItem(REFRESH_TOKEN_KEY)) {
            setAuthError('Could not connect to ContractCommand. Check that the backend is running.')
          }
        }
      } finally {
        if (!cancelled) setAuthLoading(false)
      }
    }
    restoreSession()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!user) return undefined
    let cancelled = false
    Promise.all(dataModulesFor(user).map(async module => {
      const response = await apiFetch(`/${module.endpoint}/`)
      if (!response.ok) throw new Error(await responseError(response))
      return { module, records: await response.json() }
    })).then(results => {
      if (cancelled) return
      const nextCounts = {}
      const recent = []
      for (const { module, records: moduleRecords } of results) {
        nextCounts[module.name] = moduleRecords.length
        recent.push(...moduleRecords.map(record => ({ ...record, module: module.name })))
      }
      setCounts(nextCounts)
      setOverviewRecords(recent.slice(0, 8))
      const vendorResult = results.find(item => item.module.name === 'Vendors')
      const contractResult = results.find(item => item.module.name === 'Contracts')
      const requisitionResult = results.find(item => item.module.name === 'Requisitions')
      const quotationRequestResult = results.find(item => item.module.name === 'Quotation Requests')
      const quoteResult = results.find(item => item.module.name === 'Vendor Quotes')
      const purchaseOrderResult = results.find(item => item.module.name === 'Purchase Orders')
      const invoiceResult = results.find(item => item.module.name === 'Invoices')
      const deliveryResult = results.find(item => item.module.name === 'Deliveries')
      setLookups({
        vendors: vendorResult?.records || [],
        contracts: contractResult?.records || [],
        requisitions: requisitionResult?.records || [],
        quotationRequests: quotationRequestResult?.records || [],
        vendorQuotes: quoteResult?.records || [],
        purchaseOrders: purchaseOrderResult?.records || [],
        invoices: invoiceResult?.records || [],
        deliveries: deliveryResult?.records || [],
      })
    }).catch(error => {
      if (!cancelled) setPageError(error.message)
    })
    return () => { cancelled = true }
  }, [user, refresh])

  useEffect(() => {
    const module = dataModulesFor(user).find(item => item.name === active)
    if (!user || !module) return undefined
    const controller = new AbortController()
    const query = search ? `?search=${encodeURIComponent(search)}` : ''
    apiFetch(`/${module.endpoint}/${query}`, {
      signal: controller.signal,
    }).then(async response => {
      if (!response.ok) throw new Error(await responseError(response))
      return response.json()
    }).then(setRecords).catch(error => {
      if (error.name !== 'AbortError') setPageError(error.message)
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [active, search, user, refresh])

  useEffect(() => {
    if (!user || active !== 'Reports') return undefined
    let cancelled = false
    const query = new URLSearchParams(
      Object.entries(reportFilters).filter(([, value]) => value),
    )
    apiFetch(`/reports/?${query}`).then(async response => {
      if (!response.ok) throw new Error(await responseError(response))
      return response.json()
    }).then(data => {
      if (!cancelled) setReportData(data)
    }).catch(error => {
      if (!cancelled) setPageError(error.message)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [active, user, reportFilters, refresh])

  const navigate = name => {
    if (name !== 'Overview' && !modulesFor(user).some(module => module.name === name)) return
    setActive(name)
    setSearch('')
    setRecords([])
    setPageError('')
    if (name !== 'Overview') setLoading(true)
  }

  const handleLogin = async event => {
    event.preventDefault()
    setLoginPending(true)
    setLoginError('')
    const form = new FormData(event.currentTarget)
    try {
      const response = await apiFetch('/auth/token/', {
        method: 'POST',
        body: {
          username: form.get('username'),
          password: form.get('password'),
        },
      })
      if (!response.ok) throw new Error(await responseError(response))
      const signedIn = await response.json()
      saveTokens(signedIn)
      setUser(signedIn.user)
      setActive('Overview')
      setRefresh(value => value + 1)
      setAuthError('')
    } catch (error) {
      setLoginError(error.message)
    } finally {
      setLoginPending(false)
    }
  }

  const handleLogout = async () => {
    const refresh = sessionStorage.getItem(REFRESH_TOKEN_KEY)
    let logoutError = ''
    if (refresh) {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/token/blacklist/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh }),
        })
        if (!response.ok) {
          throw new Error(await responseError(response))
        }
      } catch (error) {
        logoutError = `Signed out locally, but server token revocation failed: ${error.message}`
      }
    }
    clearTokens()
    setUser(null)
    setActive('Overview')
    setRecords([])
    setOverviewRecords([])
    setCounts({})
    setPageError(logoutError)
  }

  const openModal = (mode, record = null, moduleName = active) => {
    setActive(moduleName)
    setFormError('')
    setModal({ mode, record, moduleName })
  }

  const handleSave = async event => {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    const form = new FormData(event.currentTarget)
    if (modal.moduleName === 'Documents') {
      try {
        for (const field of [
          'contract',
          'quotation_request',
          'vendor_quote',
          'purchase_order',
          'invoice',
          'delivery',
        ]) {
          if (!form.get(field)) form.delete(field)
        }
        const response = await apiFetch('/documents/', {
          method: 'POST',
          body: form,
        })
        if (!response.ok) throw new Error(await responseError(response))
        setModal(null)
        setRefresh(value => value + 1)
      } catch (error) {
        setFormError(error.message)
      } finally {
        setSaving(false)
      }
      return
    }
    const payload = Object.fromEntries(form.entries())
    const module = MODULES.find(item => item.name === modal.moduleName)
    if (modal.moduleName === 'Vendors') {
      payload.approved = payload.approved === 'true'
      payload.compliance_score = Number(payload.compliance_score)
    }
    if (modal.moduleName === 'Requisitions') {
      payload.contract = payload.contract ? Number(payload.contract) : null
    }
    if (modal.moduleName === 'Invoices') {
      payload.vendor = Number(payload.vendor)
      payload.contract = Number(payload.contract)
      payload.purchase_order = payload.purchase_order
        ? Number(payload.purchase_order)
        : null
    }
    if (modal.moduleName === 'Quotation Requests') {
      payload.requisition = Number(payload.requisition)
      payload.invited_vendors = form.getAll('invited_vendors').map(Number)
      payload.close_date = payload.close_date || null
    }
    if (modal.moduleName === 'Vendor Quotes') {
      payload.quotation_request = Number(payload.quotation_request)
      payload.valid_until = payload.valid_until || null
    }
    if (modal.moduleName === 'Purchase Orders') {
      payload.requisition = Number(payload.requisition)
      payload.vendor = Number(payload.vendor)
      payload.quote = payload.quote ? Number(payload.quote) : null
      payload.contract = payload.contract ? Number(payload.contract) : null
      payload.expected_delivery_date = payload.expected_delivery_date || null
    }
    if (modal.moduleName === 'Deliveries') {
      payload.purchase_order = Number(payload.purchase_order)
      payload.expected_date = payload.expected_date || null
      payload.delivered_date = payload.delivered_date || null
    }
    if (modal.moduleName === 'Payment Sessions') {
      payload.invoice = Number(payload.invoice)
    }

    try {
      const editing = modal.mode === 'edit'
      const suffix = editing ? `${modal.record.id}/` : ''
      const response = await apiFetch(`/${module.endpoint}/${suffix}`, {
        method: editing ? 'PUT' : 'POST',
        body: payload,
      })
      if (!response.ok) throw new Error(await responseError(response))
      setModal(null)
      setSearch('')
      setRefresh(value => value + 1)
    } catch (error) {
      setFormError(error.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (record, moduleName) => {
    if (!window.confirm(`Delete ${referenceFor(record, moduleName)}?`)) return
    const module = MODULES.find(item => item.name === moduleName)
    try {
      const response = await apiFetch(`/${module.endpoint}/${record.id}/`, {
        method: 'DELETE',
      })
      if (!response.ok) throw new Error(await responseError(response))
      setRefresh(value => value + 1)
    } catch (error) {
      setPageError(error.message)
    }
  }

  const handlePurchaseOrderSubmit = async record => {
    try {
      const response = await apiFetch(`/purchase-orders/${record.id}/submit/`, {
        method: 'POST',
        body: {},
      })
      if (!response.ok) throw new Error(await responseError(response))
      setRefresh(value => value + 1)
    } catch (error) {
      setPageError(error.message)
    }
  }

  const handleApprovalDecision = async (record, decision) => {
    try {
      const response = await apiFetch(`/approvals/${record.id}/decide/`, {
        method: 'POST',
        body: { decision },
      })
      if (!response.ok) throw new Error(await responseError(response))
      setRefresh(value => value + 1)
    } catch (error) {
      setPageError(error.message)
    }
  }

  const handleDemoPaymentComplete = async record => {
    try {
      const response = await apiFetch(`/payment-sessions/${record.id}/complete/`, {
        method: 'POST',
        body: {},
      })
      if (!response.ok) {
        const message = await responseError(response)
        setRefresh(value => value + 1)
        throw new Error(message)
      }
      setRefresh(value => value + 1)
    } catch (error) {
      setPageError(error.message)
    }
  }

  const handleDocumentDownload = async record => {
    try {
      const response = await apiFetch(`/documents/${record.id}/download/`)
      if (!response.ok) throw new Error(await responseError(response))
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = url
      link.download = record.original_filename
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) {
      setPageError(error.message)
    }
  }

  const handleNotificationRead = async record => {
    try {
      const response = await apiFetch(`/notifications/${record.id}/mark-read/`, {
        method: 'PATCH',
        body: {},
      })
      if (!response.ok) throw new Error(await responseError(response))
      setRefresh(value => value + 1)
    } catch (error) {
      setPageError(error.message)
    }
  }

  const handleReportExport = async () => {
    try {
      const query = new URLSearchParams(
        Object.entries(reportFilters).filter(([, value]) => value),
      )
      query.set('report', 'summary')
      const response = await apiFetch(`/reports/export/?${query}`)
      if (!response.ok) throw new Error(await responseError(response))
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = url
      link.download = 'contractcommand-summary.csv'
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) {
      setPageError(error.message)
    }
  }

  if (authLoading) {
    return <div className="auth-page"><div className="auth-card">Checking your session…</div></div>
  }

  if (!user) {
    return (
      <div className="auth-page">
        <form className="auth-card" onSubmit={handleLogin}>
          <div className="brand auth-brand">C<span>ContractCommand</span></div>
          <p className="eyebrow">SECURE WORKSPACE</p>
          <h1>Sign in</h1>
          <p className="muted">Use your assigned ContractCommand account.</p>
          {(authError || loginError) && <div className="error-message" role="alert">{authError || loginError}</div>}
          <label>Username<input name="username" autoComplete="username" required /></label>
          <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
          <button className="primary" type="submit" disabled={loginPending}>
            {loginPending ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    )
  }

  const activeModule = modulesFor(user).find(module => module.name === active)
  const canCreateActiveRecord = activeModule
    && !['Notifications', 'Audit History', 'Reports'].includes(active)
    && canAccess(user, activeModule, 'create')
  const displayedRecords = active === 'Overview'
    ? overviewRecords
    : records.map(record => ({ ...record, module: active }))
  return (
    <div className="app-shell">
      <aside>
        <button className="brand brand-button" onClick={() => navigate('Overview')}>C<span>ContractCommand</span></button>
        <nav aria-label="Main navigation">
          {['Overview', ...modulesFor(user).map(module => module.name)].map(item =>
            <button key={item} className={active === item ? 'active' : ''} onClick={() => navigate(item)}>{item}</button>
          )}
        </nav>
        <div className="user">
          <b>{user.displayName.slice(0, 2).toUpperCase()}</b>
          <span>{user.displayName}<br /><small>{user.roles.join(' / ') || 'Administrator'}</small></span>
          <button className="logout-button" onClick={handleLogout}>Sign out</button>
        </div>
      </aside>
      <main>
        <header>
          <div><p>OPERATIONS</p><h1>{active}</h1></div>
          {canCreateActiveRecord && (
            <button className="primary" onClick={() => openModal('create')}>
              {active === 'Documents' ? '+ Upload document' : '+ New record'}
            </button>
          )}
        </header>
        {pageError && <div className="error-message" role="alert">{pageError}<button onClick={() => setPageError('')}>Dismiss</button></div>}
        {activeModule && active !== 'Reports' && (
          <div className="toolbar">
            <input
              value={search}
              onChange={event => {
                setSearch(event.target.value)
                setLoading(true)
              }}
              placeholder={`Search ${active.toLowerCase()}...`}
              aria-label={`Search ${active.toLowerCase()}`}
            />
          </div>
        )}
        {active === 'Reports' && (
          <form
            className="report-filters"
            onSubmit={event => {
              event.preventDefault()
              setLoading(true)
              setRefresh(value => value + 1)
            }}
          >
            <label>From<input type="date" value={reportFilters.date_from} onChange={event => { setLoading(true); setReportFilters(filters => ({ ...filters, date_from: event.target.value })) }} /></label>
            <label>To<input type="date" value={reportFilters.date_to} onChange={event => { setLoading(true); setReportFilters(filters => ({ ...filters, date_to: event.target.value })) }} /></label>
            <label>Status<input value={reportFilters.status} onChange={event => { setLoading(true); setReportFilters(filters => ({ ...filters, status: event.target.value })) }} placeholder="Any status" /></label>
            <button className="primary" type="submit">Apply filters</button>
          </form>
        )}
        <section className="cards" aria-label="Project modules">
          {modulesFor(user).map(module => (
            <button
              className={`module-card ${active === module.name ? 'selected' : ''}`}
              key={module.name}
              onClick={() => navigate(module.name)}
            >
              <span>{module.name}</span>
              <strong>{counts[module.name] ?? '—'}</strong>
              <small>View module →</small>
            </button>
          ))}
        </section>
        <section className="panel">
          <div className="panel-title">
            <h2>{active === 'Overview' ? 'Recent activity' : active === 'Reports' ? 'Reports and analytics' : `${active} records`}</h2>
            {active === 'Reports'
              ? <button onClick={handleReportExport}>Export summary CSV</button>
              : <button onClick={() => setRefresh(value => value + 1)}>
                {active === 'Overview' ? 'Refresh' : 'Refresh records'}
              </button>}
          </div>
          {active === 'Reports' ? (
            <div className="reports-grid">
              {loading && <div className="table-message"><b>Loading reports…</b></div>}
              {!loading && reportData && Object.entries(reportData)
                .filter(([section]) => section !== 'filters')
                .map(([section, values]) => (
                  <article className="report-card" key={section}>
                    <h3>{section.replaceAll('_', ' ')}</h3>
                    {Array.isArray(values) ? (
                      values.length ? values.map((row, index) => (
                        <dl className="report-row" key={`${section}-${row.vendor_id || row.status || index}`}>
                          {Object.entries(row).map(([label, value]) => (
                            <div key={label}>
                              <dt>{label.replaceAll('_', ' ')}</dt>
                              <dd>{value ?? '—'}</dd>
                            </div>
                          ))}
                        </dl>
                      )) : <p className="muted">No matching records.</p>
                    ) : (
                      <dl className="report-row">
                        {Object.entries(values).map(([label, value]) => (
                          <div key={label}>
                            <dt>{label.replaceAll('_', ' ')}</dt>
                            <dd>{value ?? '—'}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                  </article>
                ))}
            </div>
          ) : <div className="table">
            <div className="table-head">
              <span>Reference</span><span>Type</span><span>Status</span><span>Owner / supplier</span><span>Actions</span>
            </div>
            {loading && <div className="table-message"><b>Loading records…</b></div>}
            {!loading && displayedRecords.length === 0 && (
              <div className="table-message">
                <b>{active === 'Overview' ? 'No recent records yet.' : 'No matching records.'}</b>
                {active === 'Overview' && <span>Choose a module above to view and manage its records.</span>}
              </div>
            )}
            {!loading && displayedRecords.map(record => {
              const recordModule = record.module
              const recordModuleDefinition = moduleFor(recordModule)
              const canDecideApproval = recordModule === 'Approvals'
                && record.status === 'PENDING'
                && (user.isStaff || (user.roles.includes('Approver') && record.approver === user.id))
              const canSubmitOrder = recordModule === 'Purchase Orders'
                && record.status === 'DRAFT'
                && canAccess(user, recordModuleDefinition, 'create')
              const canCompleteDemoPayment = recordModule === 'Payment Sessions'
                && record.status === 'PENDING'
                && canAccess(user, recordModuleDefinition, 'create')
              return (
                <div className="table-row" key={`${recordModule}-${record.id}`}>
                  <b>{referenceFor(record, recordModule)}</b>
                  <span>{recordModuleDefinition?.singular || recordModule}</span>
                  <em className={statusFor(record).toLowerCase().includes('pending') ? 'pending-status' : 'active-status'}>{statusFor(record)}</em>
                  <span>{ownerFor(record, recordModule)}</span>
                  <span className="row-actions">
                    <button onClick={() => openModal('view', record, recordModule)}>View</button>
                    {recordModule === 'Documents' && <button onClick={() => handleDocumentDownload(record)}>Download</button>}
                    {recordModule === 'Notifications' && !record.read_at && canAccess(user, recordModuleDefinition, 'update') && <button onClick={() => handleNotificationRead(record)}>Mark read</button>}
                    {!['Notifications', 'Audit History'].includes(recordModule) && canAccess(user, recordModuleDefinition, 'update') && <button onClick={() => openModal('edit', record, recordModule)}>Edit</button>}
                    {canSubmitOrder && <button onClick={() => handlePurchaseOrderSubmit(record)}>Submit for approval</button>}
                    {canDecideApproval && <>
                      <button onClick={() => handleApprovalDecision(record, 'APPROVED')}>Approve</button>
                      <button className="danger-link" onClick={() => handleApprovalDecision(record, 'REJECTED')}>Reject</button>
                    </>}
                    {canCompleteDemoPayment && <button onClick={() => handleDemoPaymentComplete(record)}>Complete demo payment</button>}
                    {!['Notifications', 'Audit History'].includes(recordModule) && canAccess(user, recordModuleDefinition, 'delete') && <button className="danger-link" onClick={() => handleDelete(record, recordModule)}>Delete</button>}
                  </span>
                </div>
              )
            })}
          </div>}
        </section>
        {modal && (
          <div className="modal-backdrop" onMouseDown={() => setModal(null)}>
            {modal.mode === 'view' ? (
              <section className="record-form" onMouseDown={event => event.stopPropagation()}>
                <h2>{referenceFor(modal.record, modal.moduleName)}</h2>
                <dl className="record-details">
                  {Object.entries(modal.record)
                    .filter(([key]) => key !== 'id' && key !== 'module')
                    .map(([key, value]) => (
                      <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value && typeof value === 'object' ? JSON.stringify(value) : String(value ?? '—')}</dd></div>
                    ))}
                </dl>
                <div className="form-actions">
                  <button onClick={() => setModal(null)}>Close</button>
                  {canAccess(user, moduleFor(modal.moduleName), 'update') && <button className="primary" onClick={() => openModal('edit', modal.record, modal.moduleName)}>Edit record</button>}
                </div>
              </section>
            ) : (
              <form className="record-form" key={`${modal.moduleName}-${modal.mode}-${modal.record?.id || 'new'}`} onSubmit={handleSave} onMouseDown={event => event.stopPropagation()}>
                <h2>{modal.mode === 'edit' ? 'Edit' : 'New'} {moduleFor(modal.moduleName)?.singular || modal.moduleName}</h2>
                {modal.moduleName === 'Contracts' && <>
                  <input name="contract_number" placeholder="Contract number" defaultValue={modal.record?.contract_number || ''} required />
                  <input name="title" placeholder="Title" defaultValue={modal.record?.title || ''} required />
                  <textarea name="description" placeholder="Description" defaultValue={modal.record?.description || ''} />
                  <input name="value" type="number" step="0.01" min="0.01" placeholder="Contract value" defaultValue={modal.record?.value || ''} required />
                  <select name="status" defaultValue={modal.record?.status || 'DRAFT'}><option>DRAFT</option><option>ACTIVE</option><option>PENDING</option><option>CLOSED</option></select>
                  <input name="start_date" type="date" defaultValue={modal.record?.start_date || ''} required />
                  <input name="end_date" type="date" defaultValue={modal.record?.end_date || ''} required />
                </>}
                {modal.moduleName === 'Requisitions' && <>
                  <input name="requisition_number" placeholder="Requisition number" defaultValue={modal.record?.requisition_number || ''} required />
                  <input name="title" placeholder="Title" defaultValue={modal.record?.title || ''} required />
                  <textarea name="justification" placeholder="Business justification" defaultValue={modal.record?.justification || ''} required />
                  <input name="estimated_value" type="number" step="0.01" min="0.01" placeholder="Estimated value" defaultValue={modal.record?.estimated_value || ''} required />
                  <select name="status" defaultValue={modal.record?.status || 'DRAFT'}><option>DRAFT</option><option>SUBMITTED</option><option>APPROVED</option><option>REJECTED</option></select>
                  <select name="contract" defaultValue={modal.record?.contract || ''}><option value="">No contract linked</option>{lookups.contracts.map(contract => <option key={contract.id} value={contract.id}>{contract.contract_number}</option>)}</select>
                </>}
                {modal.moduleName === 'Vendors' && <>
                  <input name="name" placeholder="Vendor name" defaultValue={modal.record?.name || ''} required />
                  <input name="registration_number" placeholder="Registration number" defaultValue={modal.record?.registration_number || ''} required />
                  <input name="contact_email" type="email" placeholder="Contact email" defaultValue={modal.record?.contact_email || ''} required />
                  <input name="phone" placeholder="Phone number" defaultValue={modal.record?.phone || ''} />
                  <input name="compliance_score" type="number" min="0" max="100" placeholder="Compliance score (0-100)" defaultValue={modal.record?.compliance_score ?? 0} required />
                  <select name="approved" defaultValue={String(modal.record?.approved ?? false)}><option value="false">Pending approval</option><option value="true">Approved</option></select>
                </>}
                {modal.moduleName === 'Invoices' && <>
                  <input name="invoice_number" placeholder="Invoice number" defaultValue={modal.record?.invoice_number || ''} required />
                  <select name="vendor" defaultValue={modal.record?.vendor || ''} required><option value="">Select vendor</option>{lookups.vendors.map(vendor => <option key={vendor.id} value={vendor.id}>{vendor.name}</option>)}</select>
                  <select name="contract" defaultValue={modal.record?.contract || ''} required><option value="">Select contract</option>{lookups.contracts.map(contract => <option key={contract.id} value={contract.id}>{contract.contract_number} - {contract.title}</option>)}</select>
                  <select name="purchase_order" defaultValue={modal.record?.purchase_order || ''}><option value="">No purchase order linked</option>{lookups.purchaseOrders.map(order => <option key={order.id} value={order.id}>{order.po_number}</option>)}</select>
                  <input name="amount" type="number" step="0.01" min="0.01" placeholder="Invoice amount" defaultValue={modal.record?.amount || ''} required />
                  <select name="status" defaultValue={modal.record?.status || 'PENDING'}><option>PENDING</option><option>APPROVED</option><option>PAID</option><option>DISPUTED</option></select>
                  <input name="invoice_date" type="date" defaultValue={modal.record?.invoice_date || ''} required />
                  <input name="due_date" type="date" defaultValue={modal.record?.due_date || ''} required />
                </>}
                {modal.moduleName === 'Quotation Requests' && <>
                  <input name="request_number" placeholder="Request number" defaultValue={modal.record?.request_number || ''} required />
                  <select name="requisition" defaultValue={modal.record?.requisition || ''} required><option value="">Select approved requisition</option>{lookups.requisitions.filter(item => item.status === 'APPROVED').map(item => <option key={item.id} value={item.id}>{item.requisition_number} - {item.title}</option>)}</select>
                  <input name="title" placeholder="Title" defaultValue={modal.record?.title || ''} required />
                  <textarea name="description" placeholder="Scope and proposal instructions" defaultValue={modal.record?.description || ''} />
                  <input name="close_date" type="date" defaultValue={modal.record?.close_date || ''} />
                  <select name="status" defaultValue={modal.record?.status || 'DRAFT'}><option>DRAFT</option><option>OPEN</option><option>CLOSED</option><option>CANCELLED</option></select>
                  <label>Invited vendors<select name="invited_vendors" multiple size="4" defaultValue={modal.record?.invited_vendors || []} required>{lookups.vendors.map(vendor => <option key={vendor.id} value={vendor.id}>{vendor.name}</option>)}</select></label>
                </>}
                {modal.moduleName === 'Vendor Quotes' && <>
                  <select name="quotation_request" defaultValue={modal.record?.quotation_request || ''} required><option value="">Select open request</option>{lookups.quotationRequests.filter(item => item.status === 'OPEN').map(item => <option key={item.id} value={item.id}>{item.request_number} - {item.title}</option>)}</select>
                  <input name="amount" type="number" step="0.01" min="0.01" placeholder="Quote amount" defaultValue={modal.record?.amount || ''} required />
                  <textarea name="proposal" placeholder="Proposal details" defaultValue={modal.record?.proposal || ''} />
                  <input name="valid_until" type="date" defaultValue={modal.record?.valid_until || ''} />
                </>}
                {modal.moduleName === 'Purchase Orders' && <>
                  <input name="po_number" placeholder="Purchase order number" defaultValue={modal.record?.po_number || ''} required />
                  <select name="requisition" defaultValue={modal.record?.requisition || ''} required><option value="">Select approved requisition</option>{lookups.requisitions.filter(item => item.status === 'APPROVED').map(item => <option key={item.id} value={item.id}>{item.requisition_number} - {item.title}</option>)}</select>
                  <select name="vendor" defaultValue={modal.record?.vendor || ''} required><option value="">Select approved vendor</option>{lookups.vendors.filter(item => item.approved).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
                  <select name="quote" defaultValue={modal.record?.quote || ''}><option value="">Direct award / no quote</option>{lookups.vendorQuotes.filter(item => item.status === 'SUBMITTED').map(item => <option key={item.id} value={item.id}>{item.request_number} - {item.vendor_name} - {item.amount}</option>)}</select>
                  <select name="contract" defaultValue={modal.record?.contract || ''}><option value="">No contract linked</option>{lookups.contracts.map(contract => <option key={contract.id} value={contract.id}>{contract.contract_number}</option>)}</select>
                  <input name="amount" type="number" step="0.01" min="0.01" placeholder="Order amount" defaultValue={modal.record?.amount || ''} required />
                  <input name="expected_delivery_date" type="date" defaultValue={modal.record?.expected_delivery_date || ''} />
                </>}
                {modal.moduleName === 'Deliveries' && <>
                  <input name="delivery_number" placeholder="Delivery number" defaultValue={modal.record?.delivery_number || ''} required />
                  <select name="purchase_order" defaultValue={modal.record?.purchase_order || ''} required><option value="">Select purchase order</option>{lookups.purchaseOrders.map(order => <option key={order.id} value={order.id}>{order.po_number}</option>)}</select>
                  <input name="tracking_number" placeholder="Tracking number" defaultValue={modal.record?.tracking_number || ''} />
                  <select name="status" defaultValue={modal.record?.status || 'EXPECTED'}><option>EXPECTED</option><option>PARTIAL</option><option>DELIVERED</option><option>REJECTED</option></select>
                  <input name="expected_date" type="date" defaultValue={modal.record?.expected_date || ''} />
                  <input name="delivered_date" type="date" defaultValue={modal.record?.delivered_date || ''} />
                  <textarea name="notes" placeholder="Delivery notes" defaultValue={modal.record?.notes || ''} />
                </>}
                {modal.moduleName === 'Payment Sessions' && <>
                  <select name="invoice" defaultValue={modal.record?.invoice || ''} required><option value="">Select approved invoice</option>{lookups.invoices.filter(invoice => invoice.status === 'APPROVED').map(invoice => <option key={invoice.id} value={invoice.id}>{invoice.invoice_number} - {invoice.amount}</option>)}</select>
                </>}
                {modal.moduleName === 'Documents' && <>
                  <select name="document_type" required defaultValue="">
                    <option value="">Select document type</option>
                    <option value="CONTRACT">Contract</option>
                    <option value="QUOTATION">Quotation</option>
                    <option value="PURCHASE_ORDER">Purchase order</option>
                    <option value="INVOICE">Invoice</option>
                    <option value="DELIVERY_RECEIPT">Delivery receipt</option>
                  </select>
                  <label>Contract<select name="contract" defaultValue=""><option value="">Not linked</option>{lookups.contracts.map(item => <option key={item.id} value={item.id}>{item.contract_number}</option>)}</select></label>
                  <label>Quotation request<select name="quotation_request" defaultValue=""><option value="">Not linked</option>{lookups.quotationRequests.map(item => <option key={item.id} value={item.id}>{item.request_number}</option>)}</select></label>
                  <label>Vendor quote<select name="vendor_quote" defaultValue=""><option value="">Not linked</option>{lookups.vendorQuotes.map(item => <option key={item.id} value={item.id}>{item.request_number} - {item.vendor_name}</option>)}</select></label>
                  <label>Purchase order<select name="purchase_order" defaultValue=""><option value="">Not linked</option>{lookups.purchaseOrders.map(item => <option key={item.id} value={item.id}>{item.po_number}</option>)}</select></label>
                  <label>Invoice<select name="invoice" defaultValue=""><option value="">Not linked</option>{lookups.invoices.map(item => <option key={item.id} value={item.id}>{item.invoice_number}</option>)}</select></label>
                  <label>Delivery receipt<select name="delivery" defaultValue=""><option value="">Not linked</option>{lookups.deliveries.map(item => <option key={item.id} value={item.id}>{item.delivery_number}</option>)}</select></label>
                  <p className="muted">Attach to exactly one record matching the selected document type. Accepted files: PDF, DOCX, XLSX, PNG, JPG, or TXT (up to 10 MB).</p>
                  <label>File<input name="file" type="file" accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.txt" required /></label>
                </>}
                {formError && <div className="error-message" role="alert">{formError}</div>}
                <div className="form-actions">
                  <button type="button" onClick={() => setModal(null)}>Cancel</button>
                  <button className="primary" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save record'}</button>
                </div>
              </form>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

export default App