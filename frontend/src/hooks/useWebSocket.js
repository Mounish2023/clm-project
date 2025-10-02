import { useState, useEffect, useCallback } from 'react';

class WebSocketManager {
  constructor() {
    this.connections = new Map();
    this.listeners = new Map();
  }

  connect(workflowId) {
    if (this.connections.has(workflowId)) {
      return this.connections.get(workflowId);
    }

    const ws = new WebSocket(`ws://127.0.0.1:8000/ws/${workflowId}`);
    this.connections.set(workflowId, ws);

    ws.onopen = () => {
      console.log(`WebSocket connected for workflow: ${workflowId}`);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.notifyListeners(workflowId, data);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      console.log(`WebSocket disconnected for workflow: ${workflowId}`);
      this.connections.delete(workflowId);
      this.listeners.delete(workflowId);
    };

    ws.onerror = (error) => {
      console.error(`WebSocket error for workflow ${workflowId}:`, error);
    };

    return ws;
  }

  disconnect(workflowId) {
    const ws = this.connections.get(workflowId);
    if (ws) {
      ws.close();
      this.connections.delete(workflowId);
      this.listeners.delete(workflowId);
    }
  }

  addListener(workflowId, callback) {
    if (!this.listeners.has(workflowId)) {
      this.listeners.set(workflowId, new Set());
    }
    this.listeners.get(workflowId).add(callback);
  }

  removeListener(workflowId, callback) {
    const listeners = this.listeners.get(workflowId);
    if (listeners) {
      listeners.delete(callback);
    }
  }

  notifyListeners(workflowId, data) {
    const listeners = this.listeners.get(workflowId);
    if (listeners) {
      listeners.forEach(callback => callback(data));
    }
  }
}

const wsManager = new WebSocketManager();

export const useWebSocket = (workflowId) => {
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    if (!workflowId) return;

    const ws = wsManager.connect(workflowId);
    setIsConnected(ws.readyState === WebSocket.OPEN);

    const handleMessage = (data) => {
      setMessages(prev => [...prev, data]);
    };

    wsManager.addListener(workflowId, handleMessage);

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);

    return () => {
      wsManager.removeListener(workflowId, handleMessage);
      if (ws.readyState === WebSocket.OPEN) {
        wsManager.disconnect(workflowId);
      }
    };
  }, [workflowId]);

  const sendMessage = useCallback((message) => {
    if (workflowId && isConnected) {
      const ws = wsManager.connections.get(workflowId);
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
      }
    }
  }, [workflowId, isConnected]);

  return {
    isConnected,
    messages,
    sendMessage,
    clearMessages: () => setMessages([])
  };
};

export default useWebSocket;
