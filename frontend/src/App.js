import React, { useState } from 'react';
import logo from './logo.svg';
import './App.css';

function App() {
  const [message, setMessage] = useState('');

  const fetchMessage = () => {
    fetch('/api/')
      .then(response => response.json())
      .then(data => setMessage(data.message))
      .catch(error => console.error('Error fetching data:', error));
  };

  return (
    <div className="App">
      <header className="App-header">
        <img src={logo} className="App-logo" alt="logo" />
        <p>
          Click the button to get a message from the backend.
        </p>
        <button onClick={fetchMessage} style={{ padding: '10px 20px', fontSize: '16px' }}>
          Get Message from Backend
        </button>
        {message && <p style={{ marginTop: '20px' }}>Message from Backend: {message}</p>}
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
