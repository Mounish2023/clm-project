import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useWebSocket } from '../hooks/useWebSocket';
import './AmendmentDetails.css';

function AmendmentDetails() {
  const { workflowId } = useParams();
  const navigate = useNavigate();
  const [amendment, setAmendment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  // WebSocket for real-time updates
  const { isConnected, messages } = useWebSocket(workflowId);

  useEffect(() => {
    const fetchAmendmentStatus = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await axios.get(`http://127.0.0.1:8000/api/v1/amendments/${workflowId}/status`);
        setAmendment(response.data);
      } catch (err) {
        setError(err.message);
        console.error('Error fetching amendment status:', err);
      } finally {
        setLoading(false);
      }
    };

    if (workflowId) {
      fetchAmendmentStatus();
    }
  }, [workflowId]);

  // Update amendment state when WebSocket messages arrive
  useEffect(() => {
    if (messages.length > 0) {
      const latestMessage = messages[messages.length - 1];
      if (latestMessage.type === 'status_update' && latestMessage.data) {
        setAmendment(latestMessage.data);
      }
    }
  }, [messages]);

  const handleCancelAmendment = async () => {
    if (!window.confirm('Are you sure you want to cancel this amendment?')) {
      return;
    }

    try {
      setActionLoading(true);
      await axios.delete(`http://127.0.0.1:8000/api/v1/amendments/${workflowId}`, {
        data: { reason: 'Cancelled by user' }
      });
      // Refresh the amendment status
      const updatedResponse = await axios.get(`http://127.0.0.1:8000/api/v1/amendments/${workflowId}/status`);
      setAmendment(updatedResponse.data);
    } catch (err) {
      setError(`Failed to cancel amendment: ${err.message}`);
      console.error('Error cancelling amendment:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleResumeAmendment = async () => {
    try {
      setActionLoading(true);
      await axios.post(`http://127.0.0.1:8000/api/v1/amendments/${workflowId}/resume`);
      // Refresh the amendment status
      const updatedResponse = await axios.get(`http://127.0.0.1:8000/api/v1/amendments/${workflowId}/status`);
      setAmendment(updatedResponse.data);
    } catch (err) {
      setError(`Failed to resume amendment: ${err.message}`);
      console.error('Error resuming amendment:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return 'status-completed';
      case 'in_progress':
      case 'initiated':
        return 'status-in-progress';
      case 'failed':
        return 'status-failed';
      case 'cancelled':
        return 'status-cancelled';
      case 'paused':
        return 'status-paused';
      default:
        return 'status-unknown';
    }
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="amendment-details-container">
        <div className="loading">Loading amendment details...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="amendment-details-container">
        <div className="error-message">
          <h3>Error Loading Amendment</h3>
          <p>{error}</p>
          <button onClick={() => navigate('/amendments')} className="back-button">
            Back to Amendments
          </button>
        </div>
      </div>
    );
  }

  if (!amendment) {
    return (
      <div className="amendment-details-container">
        <div className="not-found">
          <h3>Amendment Not Found</h3>
          <p>The amendment with workflow ID "{workflowId}" could not be found.</p>
          <button onClick={() => navigate('/amendments')} className="back-button">
            Back to Amendments
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="amendment-details-container">
      <div className="amendment-details-header">
        <div className="header-actions">
          <Link to="/amendments" className="back-link">
            ← Back to Amendments
          </Link>
          <div className="connection-status">
            <span className={`connection-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
              {isConnected ? '🟢' : '🔴'}
            </span>
            <span className="connection-text">
              {isConnected ? 'Live Updates' : 'Disconnected'}
            </span>
          </div>
        </div>

        <div className="amendment-title-section">
          <h1>Amendment Details</h1>
          <span className={`status-badge ${getStatusBadgeClass(amendment.status)}`}>
            {amendment.status || 'Unknown'}
          </span>
        </div>
        <div className="workflow-id">Workflow ID: {amendment.workflow_id}</div>
      </div>

      <div className="amendment-details-content">
        <div className="amendment-overview">
          <div className="overview-card">
            <h3>Overview</h3>
            <div className="overview-grid">
              <div className="overview-item">
                <label>Contract ID</label>
                <span>{amendment.contract_id || 'N/A'}</span>
              </div>
              <div className="overview-item">
                <label>Status</label>
                <span>{amendment.status || 'N/A'}</span>
              </div>
              <div className="overview-item">
                <label>Conflicts</label>
                <span>{amendment.conflicts || 0}</span>
              </div>
              <div className="overview-item">
                <label>Created</label>
                <span>{formatDateTime(amendment.created_at)}</span>
              </div>
              <div className="overview-item">
                <label>Last Updated</label>
                <span>{formatDateTime(amendment.updated_at)}</span>
              </div>
            </div>
          </div>

          <div className="overview-card">
            <h3>Party Status</h3>
            <div className="parties-status">
              {amendment.parties_status && Object.keys(amendment.parties_status).length > 0 ? (
                Object.entries(amendment.parties_status).map(([partyId, status]) => (
                  <div key={partyId} className="party-status-item">
                    <span className="party-id">{partyId}</span>
                    <span className={`party-status-badge status-${status?.toLowerCase() || 'unknown'}`}>
                      {status || 'Unknown'}
                    </span>
                  </div>
                ))
              ) : (
                <p className="no-party-status">No party status information available</p>
              )}
            </div>
          </div>
        </div>

        <div className="amendment-timeline">
          <div className="timeline-card">
            <h3>Activity Timeline</h3>
            <div className="timeline">
              {messages.length > 0 ? (
                messages.map((message, index) => (
                  <div key={index} className="timeline-item">
                    <div className="timeline-marker">
                      {message.type === 'status_update' ? '🔄' : '📨'}
                    </div>
                    <div className="timeline-content">
                      <div className="timeline-time">
                        {formatDateTime(new Date().toISOString())}
                      </div>
                      <div className="timeline-message">
                        {message.type === 'status_update'
                          ? `Status updated to: ${message.data?.status || 'Unknown'}`
                          : `Message: ${JSON.stringify(message.data)}`
                        }
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="no-timeline">
                  <p>No activity yet. Waiting for updates...</p>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="amendment-actions">
          {amendment.status !== 'completed' &&
           amendment.status !== 'cancelled' &&
           amendment.status !== 'failed' && (
            <>
              {amendment.status === 'paused' && (
                <button
                  onClick={handleResumeAmendment}
                  disabled={actionLoading}
                  className="resume-button"
                >
                  {actionLoading ? 'Resuming...' : 'Resume Workflow'}
                </button>
              )}
              <button
                onClick={handleCancelAmendment}
                disabled={actionLoading}
                className="cancel-button"
              >
                {actionLoading ? 'Cancelling...' : 'Cancel Amendment'}
              </button>
            </>
          )}
          <button
            onClick={() => navigate('/amendments')}
            className="back-button"
          >
            Back to Amendments
          </button>
        </div>
      </div>
    </div>
  );
}

export default AmendmentDetails;
