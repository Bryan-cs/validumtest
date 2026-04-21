import './globals.css';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

window.addEventListener('vite:preloadError', () => { window.location.reload(); });

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<React.StrictMode><App /></React.StrictMode>);
