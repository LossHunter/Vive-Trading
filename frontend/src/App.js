import React, { useState } from 'react';
import logo from './logo.svg';
import './App.css';

function App() {
  const [message, setMessage] = useState('');
  const [testMessage, setTestMessage] = useState('');

  const fetchMessage = () => {
    fetch('/api/')
      .then(response => response.json())
      .then(data => setMessage(data.message))
      .catch(error => console.error('Error fetching data:', error));
  };

  const fetchTestMessage = () => {
    fetch('/api/test')
      .then(response => response.json())
      .then(data => setTestMessage(data.message))
      .catch(error => console.error('Error fetching data:', error));
  };

  return (
    <div className="App">
      <header className="App-header">
        <img src={logo} className="App-logo" alt="logo" />
        <p>
          Click the button to get a message from the backend.
        </p>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={fetchMessage} style={{ padding: '10px 20px', fontSize: '16px' }}>
            Get Message from Backend
          </button>
          <button onClick={fetchTestMessage} style={{ padding: '10px 20px', fontSize: '16px' }}>
            GitHub Action Test
          </button>
        </div>
        {message && <p style={{ marginTop: '20px' }}>Message from Backend: {message}</p>}
        {testMessage && <p style={{ marginTop: '20px' }}>GitHub Action Test: {testMessage}</p>}
        <a
          className="App-link"
          href="https://reactjs.org"
          target="_blank"
          rel="noopener noreferrer"
          style={{ marginTop: '20px' }}
        >
          Learn React
        </a>
      </header>
    </div>
  );
}

export default App;
