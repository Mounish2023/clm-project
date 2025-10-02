import { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import './ContractsList.css';

function ContractsList() {
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  const fetchContracts = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get('http://127.0.0.1:8000/api/v1/contracts');
      setContracts(response.data || []);
    } catch (err) {
      setError('Failed to fetch contracts. Make sure your backend server is running and accessible.');
      console.error('Error fetching contracts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContracts();
  }, []);

  const filteredContracts = contracts.filter(contract => {
    if (!contract) return false;

    const searchLower = searchTerm.toLowerCase();
    const title = contract.title || '';
    const content = contract.content || '';
    const id = contract.id || '';

    return (
      title.toLowerCase().includes(searchLower) ||
      id.toLowerCase().includes(searchLower) ||
      (content && content.toLowerCase().includes(searchLower))
    );
  });

  const getStatusBadgeClass = (status) => {
    switch (status?.toLowerCase()) {
      case 'active':
        return 'status-active';
      case 'draft':
        return 'status-draft';
      case 'expired':
        return 'status-expired';
      case 'terminated':
        return 'status-terminated';
      default:
        return 'status-unknown';
    }
  };

  return (
    <div className="contracts-container">
      <div className="contracts-header">
        <h2>Contracts</h2>
        <div className="controls">
          <div className="search-box">
            <input
              type="text"
              placeholder="Search contracts..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            <span className="search-icon">🔍</span>
          </div>
          <button 
            onClick={fetchContracts}
            className="refresh-button"
            disabled={loading}
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading ? (
        <div className="loading">Loading contracts...</div>
      ) : filteredContracts.length > 0 ? (
        <div className="contracts-grid">
          {filteredContracts.map((contract) => (
            <div key={contract.id} className="contract-card">
              <div className="contract-card-header">
                <h3>
                  <Link to={`/contracts/${contract.id}`} className="contract-link">
                    {contract.title || 'Untitled Contract'}
                  </Link>
                </h3>
                <span className={`status-badge ${getStatusBadgeClass(contract.status)}`}>
                  {contract.status || 'Unknown'}
                </span>
              </div>
              
              <div className="contract-id">ID: {contract.id}</div>
              
              {contract.content && (
                <p className="contract-content">
                  {contract.content.length > 150 
                    ? `${contract.content.substring(0, 150)}...` 
                    : contract.content}
                </p>
              )}
              
              <div className="contract-meta">
                <div className="contract-parties">
                  <span className="meta-label">Parties:</span>
                  <span>{
                    Array.isArray(contract.parties) && contract.parties.length > 0
                      ? contract.parties
                          .map(p => {
                            if (typeof p === 'string') return p;
                            if (typeof p === 'object') {
                              return p.name || p.organization || p.id || 'Unknown';
                            }
                            return 'Unknown';
                          })
                          .filter(Boolean)
                          .join(', ')
                      : 'No parties'
                  }</span>
                </div>
                <div className="contract-version">
                  <span className="meta-label">Latest Version:</span>
                  <span>{contract.latest_version?.version_number || 'N/A'}</span>
                </div>
                <div className="contract-date">
                  <span className="meta-label">Last Updated:</span>
                  <span>
                    {contract.updated_at 
                      ? new Date(contract.updated_at).toLocaleDateString(undefined, { 
                          year: 'numeric', 
                          month: 'short', 
                          day: 'numeric' 
                        }) 
                      : 'N/A'}
                  </span>
                </div>
                {contract.latest_version?.changes_summary && (
                  <div className="contract-changes">
                    <span className="meta-label">Last Changes:</span>
                    <span className="changes-summary">
                      {contract.latest_version.changes_summary}
                    </span>
                  </div>
                )}
              </div>
              
              <div className="contract-actions">
                <Link 
                  to={`/contracts/${contract.id}`} 
                  className="view-details"
                >
                  View Details
                </Link>
                <Link 
                  to={`/amendments/new?contractId=${contract.id}`}
                  className="create-amendment"
                >
                  Create Amendment
                </Link>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="no-results">
          {searchTerm ? (
            <p>No contracts match your search. Try a different term.</p>
          ) : (
            <p>No contracts found. Create one to get started!</p>
          )}
        </div>
      )}
    </div>
  );
}

export default ContractsList;
