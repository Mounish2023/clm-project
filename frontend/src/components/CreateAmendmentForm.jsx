import { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './CreateAmendmentForm.css';

function CreateAmendmentForm({ onSuccess, onCancel }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const contractId = searchParams.get('contractId');
  const [formData, setFormData] = useState({
    contract_id: contractId || '',
    proposed_changes: '',
    original_contract: '',
    priority: 'normal',
    deadline: '',
  });
  
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Fetch contracts if no contractId is provided
  useEffect(() => {
    if (!contractId) {
      const fetchContracts = async () => {
        try {
          const response = await axios.get('http://127.0.0.1:8000/api/v1/contracts');
          setContracts(response.data);
        } catch (err) {
          console.error('Error fetching contracts:', err);
        }
      };
      
      fetchContracts();
    }
  }, [contractId]);
  const [parties, setParties] = useState([
    { id: `party_${Date.now()}`, organization: '', contact_email: '', role: 'party' }
  ]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handlePartyChange = (index, field, value) => {
    const newParties = [...parties];
    newParties[index] = {
      ...newParties[index],
      [field]: value
    };
    setParties(newParties);
  };

  const addParty = () => {
    setParties([...parties, { id: `party_${Date.now() + parties.length}`, organization: '', contact_email: '', role: 'party' }]);
  };

  const removeParty = (index) => {
    if (parties.length === 1) return; // Keep at least one party
    const newParties = parties.filter((_, i) => i !== index);
    setParties(newParties);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post('http://127.0.0.1:8000/api/v1/amendments/initiate', {
        ...formData,
        parties: parties.map(party => ({
          ...party,
          policies: {},
          notification_preferences: { email: !!party.contact_email }
        })),
        proposed_changes: formData.proposed_changes.split('\n').filter(Boolean)
      });

      // If onSuccess is a function, call it with the response
      if (typeof onSuccess === 'function') {
        onSuccess(response.data);
      } 
      // If onSuccess is an object, assume it's a navigation object
      else if (onSuccess && onSuccess.pathname) {
        navigate(onSuccess.pathname, { state: onSuccess.state });
      }
      // Default navigation
      else {
        navigate('/amendments', { 
          state: { successMessage: 'Amendment created successfully!' } 
        });
      }
      
    } catch (err) {
      console.error('Error creating amendment:', err);
      setError(err.response?.data?.detail || 'Failed to create amendment. Please check the form and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    if (typeof onCancel === 'function') {
      onCancel();
    } else {
      navigate(-1); // Go back to previous page
    }
  };

  return (
    <div className="create-amendment-form card">
      <div className="form-header">
        <h2>Initiate New Contract Amendment</h2>
        <p className="form-subtitle">Fill in the details below to create a new amendment workflow</p>
      </div>
      
      {error && <div className="alert alert-error">{error}</div>}
      
      <form onSubmit={handleSubmit} className="amendment-form">
        <div className="form-section">
          <h3>Contract Information</h3>
          
          {contractId ? (
            <div className="form-group">
              <label>Contract ID</label>
              <input
                type="text"
                name="contract_id"
                value={formData.contract_id}
                onChange={handleChange}
                required
                disabled={!!contractId}
                className="form-control"
              />
            </div>
          ) : (
            <div className="form-group">
              <label>Select Contract</label>
              <select
                name="contract_id"
                value={formData.contract_id}
                onChange={handleChange}
                required
                className="form-control"
              >
                <option value="">Select a contract...</option>
                {contracts.map(contract => (
                  <option key={contract.id} value={contract.id}>
                    {contract.name || `Contract ${contract.id.substring(0, 8)}`}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="form-group">
            <label>Proposed Changes <span className="required">*</span></label>
            <p className="help-text">Enter each proposed change on a new line</p>
            <textarea
              name="proposed_changes"
              value={formData.proposed_changes}
              onChange={handleChange}
              required
              rows={4}
              className="form-control"
              placeholder="1. Change X to Y\n2. Add new clause about...\n3. Update section 4.2 to..."
            />
          </div>

          <div className="form-group">
            <label>Original Contract Text (Optional)</label>
            <p className="help-text">Paste the relevant section of the original contract that this amendment modifies</p>
            <textarea
              name="original_contract"
              value={formData.original_contract}
              onChange={handleChange}
              rows={6}
              className="form-control"
              placeholder="Paste the original contract text here..."
            />
          </div>

        <div className="form-row">
          <div className="form-group">
            <label>Priority:</label>
            <select
              name="priority"
              value={formData.priority}
              onChange={handleChange}
              className="form-control"
            >
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </div>

          <div className="form-group">
            <label>Deadline (optional):</label>
            <input
              type="datetime-local"
              name="deadline"
              value={formData.deadline}
              onChange={handleChange}
              className="form-control"
              min={new Date().toISOString().slice(0, 16)}
            />
          </div>
        </div>
      </div>  {/* Close form-section div */}

        <div className="parties-section">
          <h3>Parties Involved</h3>
          {parties.map((party, index) => (
            <div key={index} className="party-entry">
              <div className="form-group">
                <label>Party ID:</label>
                <input
                  type="text"
                  value={party.id}
                  onChange={(e) => handlePartyChange(index, 'id', e.target.value)}
                  placeholder="Enter party ID"
                  required={index === 0}
                />
              </div>
              <div className="form-group">
                <label>Organization:</label>
                <input
                  type="text"
                  value={party.organization}
                  onChange={(e) => handlePartyChange(index, 'organization', e.target.value)}
                  placeholder="Enter organization name"
                  required={index === 0}
                />
              </div>
              <div className="form-group">
                <label>Contact Email:</label>
                <input
                  type="email"
                  value={party.contact_email}
                  onChange={(e) => handlePartyChange(index, 'contact_email', e.target.value)}
                  placeholder="Enter contact email"
                />
              </div>
              {parties.length > 1 && (
                <button
                  type="button"
                  className="remove-party"
                  onClick={() => removeParty(index)}
                >
                  Remove
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            className="add-party"
            onClick={addParty}
          >
            + Add Another Party
          </button>
        </div>

        <div className="form-actions">
          <button
            type="button"
            onClick={handleCancel}
            className="button secondary"
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="button primary"
          >
            {loading ? 'Creating...' : 'Initiate Amendment'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default CreateAmendmentForm;
