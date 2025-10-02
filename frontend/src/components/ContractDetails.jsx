import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import './ContractDetails.css';

function ContractDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [contract, setContract] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchContract = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await axios.get('http://127.0.0.1:8000/api/v1/contracts');
        const contracts = response.data || [];
        const contractData = contracts.find(c => c.id === id);
        
        if (!contractData) {
          throw new Error('Contract not found');
        }
        
        setContract(contractData);
      } catch (err) {
        setError(err.message);
        console.error('Error fetching contract:', err);
      } finally {
        setLoading(false);
      }
    };

    if (id) {
      fetchContract();
    }
  }, [id]);

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

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatCurrency = (amount, currency = 'USD') => {
    if (!amount) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  };

  if (loading) {
    return (
      <div className="contract-details-container">
        <div className="loading">Loading contract details...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="contract-details-container">
        <div className="error-message">
          <h3>Error Loading Contract</h3>
          <p>{error}</p>
          <button onClick={() => navigate('/contracts')} className="back-button">
            Back to Contracts
          </button>
        </div>
      </div>
    );
  }

  if (!contract) {
    return (
      <div className="contract-details-container">
        <div className="not-found">
          <h3>Contract Not Found</h3>
          <p>The contract with ID "{id}" could not be found.</p>
          <button onClick={() => navigate('/contracts')} className="back-button">
            Back to Contracts
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="contract-details-container">
      <div className="contract-details-header">
        <div className="header-actions">
          <Link to="/contracts" className="back-link">
            ← Back to Contracts
          </Link>
          <Link
            to={`/amendments/new?contractId=${contract.id}`}
            className="create-amendment-button"
          >
            Create Amendment
          </Link>
        </div>
        <div className="contract-title-section">
          <h1>{contract.title || 'Untitled Contract'}</h1>
          <span className={`status-badge ${getStatusBadgeClass(contract.status)}`}>
            {contract.status || 'Unknown'}
          </span>
        </div>
        <div className="contract-id">Contract ID: {contract.id}</div>
      </div>

      <div className="contract-details-content">
        <div className="contract-overview">
          <div className="overview-card">
            <h3>Contract Overview</h3>
            <div className="overview-grid">
              <div className="overview-item">
                <label>Type</label>
                <span>{contract.contract_type || 'N/A'}</span>
              </div>
              <div className="overview-item">
                <label>Total Value</label>
                <span>{formatCurrency(contract.total_value, contract.currency)}</span>
              </div>
              <div className="overview-item">
                <label>Effective Date</label>
                <span>{formatDate(contract.effective_date)}</span>
              </div>
              <div className="overview-item">
                <label>Expiration Date</label>
                <span>{formatDate(contract.expiration_date)}</span>
              </div>
              <div className="overview-item">
                <label>Version</label>
                <span>{contract.version || 1}</span>
              </div>
              <div className="overview-item">
                <label>Latest Version</label>
                <span>{contract.latest_version?.version_number || 'N/A'}</span>
              </div>
            </div>
          </div>

          <div className="overview-card">
            <h3>Parties Involved</h3>
            <div className="parties-list">
              {Array.isArray(contract.parties) && contract.parties.length > 0 ? (
                contract.parties.map((party, index) => (
                  <div key={index} className="party-item">
                    <div className="party-info">
                      <strong>{party.name || party.organization || 'Unknown Party'}</strong>
                      {party.role && <span className="party-role">({party.role})</span>}
                    </div>
                    {party.email && (
                      <div className="party-contact">{party.email}</div>
                    )}
                  </div>
                ))
              ) : (
                <p className="no-parties">No parties information available</p>
              )}
            </div>
          </div>
        </div>

        <div className="contract-content-section">
          <div className="content-card">
            <h3>Contract Content</h3>
            <div className="contract-content">
              {contract.content ? (
                <div className="content-text">
                  {contract.content}
                </div>
              ) : (
                <p className="no-content">No contract content available</p>
              )}
            </div>
          </div>

          {contract.latest_version?.changes_summary && (
            <div className="content-card">
              <h3>Latest Changes Summary</h3>
              <div className="changes-summary">
                {contract.latest_version.changes_summary}
              </div>
            </div>
          )}
        </div>

        <div className="contract-actions">
          <Link
            to={`/amendments/new?contractId=${contract.id}`}
            className="primary-button"
          >
            Create Amendment
          </Link>
          <button
            onClick={() => navigate('/contracts')}
            className="secondary-button"
          >
            Back to Contracts
          </button>
        </div>
      </div>
    </div>
  );
}

export default ContractDetails;
