import { useEffect, useState } from 'react'
import './App.css'

function App() {
  const [active, setActive] = useState('Overview')
  const [records, setRecords] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const [vendors, setVendors] = useState([])
  const [contracts, setContracts] = useState([])
  const modules = [
    ['Contracts', '8 active'],
    ['Requisitions', '12 pending'],
    ['Vendors', '24 registered'],
    ['Invoices', '5 awaiting'],
  ]

  const endpoints = {
    Contracts: 'contracts',
    Requisitions: 'requisitions',
    Vendors: 'vendors',
    Invoices: 'invoices',
  }

  useEffect(() => {
    const endpoint = endpoints[active]
    if (!endpoint) {
      setRecords([])
      return
    }
    setLoading(true)
    const query = search ? `?search=${encodeURIComponent(search)}` : ''
    fetch(`http://127.0.0.1:8000/api/${endpoint}/${query}`)
      .then(response => {
        if (!response.ok) throw new Error('Unable to load records')
        return response.json()
      })
      .then(setRecords)
      .catch(() => setRecords([]))
      .finally(() => setLoading(false))
  }, [active, search, refresh])

  useEffect(() => {
    Promise.all([
      fetch('http://127.0.0.1:8000/api/vendors/').then(response => response.json()),
      fetch('http://127.0.0.1:8000/api/contracts/').then(response => response.json()),
    ]).then(([vendorRecords, contractRecords]) => {
      setVendors(vendorRecords)
      setContracts(contractRecords)
    }).catch(() => {
      setVendors([])
      setContracts([])
    })
  }, [refresh])

  const submitRecord = async event => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const payload = Object.fromEntries(form.entries())
    const endpoint = endpoints[active]
    if (!endpoint) return
    const requiredIds = active === 'Contracts'
      ? ['contract_number', 'title', 'value', 'start_date', 'end_date']
      : []
    const missing = requiredIds.filter(field => !payload[field])
    if (missing.length) return
    if (active === 'Contracts') payload.owner = 1
    if (active === 'Requisitions') {
      payload.requested_by = 1
      payload.contract = payload.contract || null
    }
    if (active === 'Vendors') {
      payload.approved = payload.approved === 'true'
      payload.compliance_score = Number(payload.compliance_score)
    }
    const response = await fetch(`http://127.0.0.1:8000/api/${endpoint}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (response.ok) {
      setShowForm(false)
      setSearch('')
      setRefresh(value => value + 1)
    } else {
      alert('Please check the required fields and try again.')
    }
  }

  const recordRows = records.map(record => ({
    key: record.contract_number || record.requisition_number || record.invoice_number || record.name || record.registration_number,
    type: active.replace(/s$/, ''),
    status: record.status || (record.approved ? 'Approved' : 'Pending review'),
    owner: record.owner_name || record.owner || record.registration_number || 'Team',
  }))

  return (
    <div className="app-shell">
      <aside>
        <div className="brand">C<span>ContractCommand</span></div>
        <nav>
          {['Overview', 'Contracts', 'Requisitions', 'Vendors', 'Invoices'].map(item =>
            <button key={item} className={active === item ? 'active' : ''} onClick={() => setActive(item)}>{item}</button>
          )}
        </nav>
        <div className="user"><b>AM</b><span>Alex Morgan<br /><small>Contracts Manager</small></span></div>
      </aside>
      <main>
        <header><div><p>OPERATIONS</p><h1>{active}</h1></div><button className="primary" onClick={() => setShowForm(true)}>+ New record</button></header>
        {active !== 'Overview' && <div className="toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder={`Search ${active.toLowerCase()}...`} /></div>}
        <section className="cards">
          {modules.map(([name, value]) => <article key={name}><span>{name}</span><strong>{value}</strong><small>View module →</small></article>)}
        </section>
        <section className="panel">
          <div className="panel-title"><h2>Recent activity</h2><button>View all</button></div>
          <div className="table">
            <div className="table-head"><span>Reference</span><span>Type</span><span>Status</span><span>Owner</span></div>
            {loading && <div><b>Loading...</b></div>}
            {!loading && recordRows.length === 0 && <div><b>{active === 'Overview' ? 'No live module selected' : 'No matching records'}</b></div>}
            {recordRows.map(row => <div key={row.key}><b>{row.key}</b><span>{row.type}</span><em className={String(row.status).toLowerCase().includes('pending') ? 'pending-status' : 'active-status'}>{row.status}</em><span>{row.owner}</span></div>)}
            {active === 'Overview' && <>
              <div><b>CTR-2026-018</b><span>Contract</span><em className="active-status">Active</em><span>A. Morgan</span></div>
              <div><b>REQ-2026-042</b><span>Requisition</span><em className="pending-status">Pending</em><span>J. Chen</span></div>
              <div><b>INV-2026-109</b><span>Invoice</span><em className="active-status">Approved</em><span>S. Patel</span></div>
            </>}
          </div>
        </section>
        {showForm && <div className="modal-backdrop" onMouseDown={() => setShowForm(false)}>
          <form className="record-form" onSubmit={submitRecord} onMouseDown={event => event.stopPropagation()}>
            <h2>New {active.replace(/s$/, '')}</h2>
            {active === 'Contracts' && <>
              <input name="contract_number" placeholder="Contract number" required />
              <input name="title" placeholder="Title" required />
              <textarea name="description" placeholder="Description" />
              <input name="value" type="number" step="0.01" placeholder="Contract value" required />
              <select name="status"><option>DRAFT</option><option>ACTIVE</option><option>PENDING</option><option>CLOSED</option></select>
              <input name="start_date" type="date" required />
              <input name="end_date" type="date" required />
            </>}
            {active === 'Requisitions' && <>
              <input name="requisition_number" placeholder="Requisition number" required />
              <input name="title" placeholder="Title" required />
              <textarea name="justification" placeholder="Business justification" required />
              <input name="estimated_value" type="number" step="0.01" placeholder="Estimated value" required />
              <select name="status"><option>DRAFT</option><option>SUBMITTED</option><option>APPROVED</option><option>REJECTED</option></select>
            </>}
            {active === 'Vendors' && <>
              <input name="name" placeholder="Vendor name" required />
              <input name="registration_number" placeholder="Registration number" required />
              <input name="contact_email" type="email" placeholder="Contact email" required />
              <input name="phone" placeholder="Phone number" />
              <input name="compliance_score" type="number" min="0" max="100" placeholder="Compliance score (0-100)" required />
              <select name="approved"><option value="false">Pending approval</option><option value="true">Approved</option></select>
            </>}
            {active === 'Invoices' && <>
              <input name="invoice_number" placeholder="Invoice number" required />
              <select name="vendor" required>
                <option value="">Select vendor</option>
                {vendors.map(vendor => <option key={vendor.id} value={vendor.id}>{vendor.name}</option>)}
              </select>
              <select name="contract" required>
                <option value="">Select contract</option>
                {contracts.map(contract => <option key={contract.id} value={contract.id}>{contract.contract_number} - {contract.title}</option>)}
              </select>
              <input name="amount" type="number" step="0.01" min="0.01" placeholder="Invoice amount" required />
              <select name="status"><option>PENDING</option><option>APPROVED</option><option>PAID</option><option>DISPUTED</option></select>
              <input name="invoice_date" type="date" required />
              <input name="due_date" type="date" required />
            </>}
            <div className="form-actions"><button type="button" onClick={() => setShowForm(false)}>Cancel</button><button className="primary" type="submit">Save record</button></div>
          </form>
        </div>}
      </main>
    </div>
  )
}

export default App
