import React from 'react';
import ReactDOM from 'react-dom/client';
import MainWorkspaceView from './components/Dashboard.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <MainWorkspaceView initialArchetype="A" />
  </React.StrictMode>
);
