import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import App from './App'
import FlashcardPage from './pages/FlashcardPage'
import HomePage from './pages/HomePage'
import KeynotePage from './pages/KeynotePage'

function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/cheatsheet" element={<App />} />
        <Route path="/flashcards" element={<FlashcardPage />} />
        <Route path="/keynote" element={<KeynotePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default AppRouter
