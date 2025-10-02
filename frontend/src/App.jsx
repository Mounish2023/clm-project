import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import CreateAmendmentForm from './components/CreateAmendmentForm';
import ContractsList from './components/ContractsList';
import ContractDetails from './components/ContractDetails';
import AmendmentDetails from './components/AmendmentDetails';
import './App.css';

function AmendmentsList() {
  const [amendments, setAmendments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const location = useLocation();

  const fetchAmendments = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get('http://127.0.0.1:8000/api/v1/amendments');
      setAmendments(response.data.amendments || []);
    } catch (err) {
      setError('Failed to fetch amendments. Make sure your backend server is running and accessible.');
      console.error('Error fetching amendments:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Check for success message in URL state (after redirect from creation)
    if (location.state?.successMessage) {
      setSuccessMessage(location.state.successMessage);
      // Clear the state to avoid showing the message again on refresh
      window.history.replaceState({}, document.title);
      
      // Clear the message after 5 seconds
      const timer = setTimeout(() => setSuccessMessage(''), 5000);
      return () => clearTimeout(timer);
    }
    
    fetchAmendments();
  }, [location.state]);

  const handleAmendmentsRefresh = () => {
    fetchAmendments();
  };

  const handleCreateSuccess = (data) => {
    setShowCreateForm(false);
    setSuccessMessage('Amendment created successfully!');
    // Refresh the amendments list
    fetchAmendments();
    
    // Clear success message after 5 seconds
    setTimeout(() => setSuccessMessage(''), 5000);
  };

  return (
    <div className="amendments-container">
      <div className="section-header">
        <h2>Contract Amendments</h2>
        <div className="controls">
          <Link to="/contracts" className="nav-button">
            View Contracts
          </Link>
          <button 
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="toggle-form-button"
          >
            {showCreateForm ? 'Hide Form' : 'New Amendment'}
          </button>
          <button 
            onClick={handleAmendmentsRefresh}
            className="refresh-button"
            disabled={loading}
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {successMessage && <div className="success-message">{successMessage}</div>}
      {error && <div className="error-message">{error}</div>}

      {showCreateForm && (
        <CreateAmendmentForm 
          onSuccess={handleCreateSuccess} 
          onCancel={() => setShowCreateForm(false)}
        />
      )}

      <div className="amendments-list">
        <div className="list-header">
          <h3>Current Amendments</h3>
          {!loading && <span className="count-badge">{amendments.length} total</span>}
        </div>
        
        {loading ? (
          <div className="loading">Loading amendments...</div>
        ) : amendments.length > 0 ? (
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>Contract ID</th>
                  <th>Status</th>
                  <th>Parties</th>
                  <th>Created At</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {amendments.map((amendment) => (
                  <tr key={amendment.workflow_id} className={`status-${amendment.status?.toLowerCase() || 'unknown'}`}>
                    <td>{amendment.contract_id || 'N/A'}</td>
                    <td>
                      <span className={`status-badge status-${amendment.status?.toLowerCase() || 'unknown'}`}>
                        {amendment.status || 'Unknown'}
                      </span>
                    </td>
                    <td>{Array.isArray(amendment.parties) ? amendment.parties.join(', ') : 'N/A'}</td>
                    <td>{amendment.created_at ? new Date(amendment.created_at).toLocaleString() : 'N/A'}</td>
                    <td>
                      <Link 
                        to={`/amendments/${amendment.workflow_id}`}
                        className="view-details"
                      >
                        View Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="no-data">
            <p>No amendments found. Create one to get started!</p>
          </div>
        )}
      </div>
    </div>
  );
}

function App() {
  return (
    <Router>
      <div className="App">
        <header className="App-header">
          <h1>Contract Lifecycle Management</h1>
          <nav>
            <Link to="/" className={window.location.pathname === '/' ? 'active' : ''}>
              Home
            </Link>
            <Link to="/contracts" className={window.location.pathname === '/contracts' ? 'active' : ''}>
              Contracts
            </Link>
            <Link to="/amendments" className={window.location.pathname.startsWith('/amendments') ? 'active' : ''}>
              Amendments
            </Link>
          </nav>
        </header>
        
        <main>
          <Routes>
            <Route path="/" element={<ContractsList />} />
            <Route path="/contracts" element={<ContractsList />} />
            <Route path="/contracts/:id" element={<ContractDetails />} />
            <Route path="/amendments" element={<AmendmentsList />} />
            <Route path="/amendments/:workflowId" element={<AmendmentDetails />} />
            <Route path="/amendments/new" element={
              <CreateAmendmentForm 
                onSuccess={(data) => ({
                  pathname: "/amendments",
                  state: { successMessage: "Amendment created successfully!" }
                })} 
                onCancel={() => window.history.back()}
              />
            } />
          </Routes>
        </main>
        
        <footer className="App-footer">
          <p>© {new Date().getFullYear()} Contract Lifecycle Management System</p>
        </footer>
      </div>
    </Router>
  );
}

export default App;
