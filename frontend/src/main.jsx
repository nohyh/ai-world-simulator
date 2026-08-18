import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './styles.css'

if (typeof window !== 'undefined') {
  document.body.dataset.viewStyle = window.localStorage.getItem('interactive-novel-style') || 'default'
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
