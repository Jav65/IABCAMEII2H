import { useState, type ChangeEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { API_URL } from "../constants"
import './HomePage.css'

const ROUTE_MAP: Record<string, string> = {
  cheatsheet: '/cheatsheet',
  flashcard: '/flashcards',
  keynote: '/keynote',
}

const ACCEPTED_TYPES = '.zip'

function HomePage() {
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState('')
  const [destination, setDestination] = useState('')
  const [fileName, setFileName] = useState('')

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const route = ROUTE_MAP[destination];
    if (!route) return;

    const formData = new FormData();
    formData.append("name", prompt);
    formData.append("format", destination);

    // single file
    const fileInputRef = document.querySelector('input[type="file"]') as HTMLInputElement;
    if (fileInputRef.files && fileInputRef.files.length > 0) {
        formData.append("files", fileInputRef.files[0]);
    }

    fetch(`${API_URL}/session`, {
        method: 'POST',
        body: formData,
    })
        .then((resp) => resp.json())
        .then((data) => {
            navigate(route, { state: data });
        })
        .catch((error) => {
            console.error('Error:', error);
        });
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
          {fileName ? `Selected: ${fileName}` : 'Upload a ZIP file'}
        </div>
      </form>
    </main>
  )
}

export default HomePage
