import { useState, type ChangeEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import './HomePage.css'

const ROUTE_MAP: Record<string, string> = {
  cheatsheet: '/cheatsheet',
  flashcard: '/flashcards',
  keynote: '/keynote',
}

const ACCEPTED_TYPES = '.jpg,.jpeg,.txt,.pdf'

function HomePage() {
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState('')
  const [destination, setDestination] = useState('')
  const [fileName, setFileName] = useState('')

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const route = ROUTE_MAP[destination]
    if (!route) return
    navigate(route, { state: { prompt, fileName } })
  }

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    setFileName(file?.name ?? '')
  }

  return (
    <main className="home-page">
      <form className="home-input" onSubmit={handleSubmit}>
        <textarea
          className="home-textarea"
          placeholder="Paste your content or describe what you want to build..."
          value={prompt}
          onChange={event => setPrompt(event.target.value)}
          rows={5}
        />
        <div className="home-controls">
          <label className="home-upload">
            Upload
            <input type="file" accept={ACCEPTED_TYPES} onChange={handleFileChange} />
          </label>
          <select
            className="home-select"
            value={destination}
            onChange={event => setDestination(event.target.value)}
            required
          >
            <option value="" disabled>
              Choose output
            </option>
            <option value="cheatsheet">Cheatsheet</option>
            <option value="flashcard">Flashcard</option>
            <option value="keynote">Keynote</option>
          </select>
          <button className="home-submit" type="submit" disabled={!destination}>
            Continue
          </button>
        </div>
        <div className="home-file">
          {fileName ? `Selected: ${fileName}` : 'Upload JPG, TXT, or PDF'}
        </div>
      </form>
    </main>
  )
}

export default HomePage
