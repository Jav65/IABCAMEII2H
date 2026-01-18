import { useMemo, useState } from 'react'
import '../App.css'
import './FlashcardPage.css'

type Flashcard = {
  question: string
  answer: string
}

const SAMPLE_JSON = `[
  {
    "question": "What does HTML stand for?",
    "answer": "HyperText Markup Language"
  },
  {
    "question": "What hook stores local component state?",
    "answer": "useState"
  },
  {
    "question": "HTTP status code for a successful request?",
    "answer": "200 OK"
  }
]`

const parseCards = (source: string): Flashcard[] => {
  const parsed = JSON.parse(source) as unknown
  const list = Array.isArray(parsed)
    ? parsed
    : (parsed as { cards?: unknown }).cards

  if (!Array.isArray(list)) {
    throw new Error('JSON must be an array or { "cards": [...] }.')
  }

  const cards = list
    .map(card => {
      if (!card || typeof card !== 'object') return null
      const record = card as Record<string, unknown>
      const question =
        typeof record.question === 'string'
          ? record.question
          : typeof record.front === 'string'
            ? record.front
            : ''
      const answer =
        typeof record.answer === 'string'
          ? record.answer
          : typeof record.back === 'string'
            ? record.back
            : ''
      if (!question.trim() || !answer.trim()) return null
      return { question: question.trim(), answer: answer.trim() }
    })
    .filter(Boolean) as Flashcard[]

  if (!cards.length) {
    throw new Error('No valid cards found in JSON.')
  }

  return cards
}

const shuffleCards = (cards: Flashcard[]) => {
  const next = [...cards]
  for (let i = next.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[next[i], next[j]] = [next[j], next[i]]
  }
  return next
}

function FlashcardPage() {
  const [jsonSource, setJsonSource] = useState(SAMPLE_JSON)
  const [cards, setCards] = useState<Flashcard[]>(() => parseCards(SAMPLE_JSON))
  const [loadStatus, setLoadStatus] = useState('Sample deck')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isRevealed, setIsRevealed] = useState(false)
  const [correctCount, setCorrectCount] = useState(0)
  const [wrongCount, setWrongCount] = useState(0)

  const currentCard = useMemo(() => {
    if (!cards.length) return null
    return cards[Math.min(currentIndex, cards.length - 1)]
  }, [cards, currentIndex])

  const totalAnswered = correctCount + wrongCount
  const remainingCount = Math.max(cards.length - totalAnswered, 0)
  const isComplete = cards.length > 0 && totalAnswered >= cards.length

  const resetSession = () => {
    setCurrentIndex(0)
    setIsRevealed(false)
    setCorrectCount(0)
    setWrongCount(0)
  }

  const handleLoadCards = () => {
    try {
      const nextCards = parseCards(jsonSource)
      setCards(nextCards)
      resetSession()
      setLoadStatus(`Loaded ${nextCards.length} cards`)
      setLoadError(null)
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unable to parse JSON cards.'
      setLoadError(message)
      setLoadStatus('Load failed')
    }
  }

  const handleReveal = () => {
    if (!currentCard || isComplete) return
    setIsRevealed(value => !value)
  }

  const handleMark = (isCorrect: boolean) => {
    if (!currentCard || isComplete) return
    if (isCorrect) {
      setCorrectCount(value => value + 1)
    } else {
      setWrongCount(value => value + 1)
    }
    setCurrentIndex(index => Math.min(index + 1, Math.max(cards.length - 1, 0)))
    setIsRevealed(false)
  }

  const handleShuffle = () => {
    if (cards.length < 2) return
    setCards(shuffleCards(cards))
    resetSession()
    setLoadStatus('Shuffled deck')
    setLoadError(null)
  }

  const handleDownload = () => {
    const payload = jsonSource.trim()
      ? jsonSource.trim()
      : JSON.stringify(cards, null, 2)
    const blob = new Blob([payload], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'flashcards.json'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <main className="layout flashcard-layout">
      <section className="panel explorer-panel">
        <div className="panel-header">
          <h1 className="panel-title">Flashcards JSON</h1>
          <div className="panel-actions">
            <span className="panel-status">{loadStatus}</span>
            <button type="button" className="compile-button" onClick={handleLoadCards}>
              Load cards
            </button>
          </div>
        </div>
        <textarea
          className="editor flashcard-editor"
          spellCheck={false}
          value={jsonSource}
          onChange={event => setJsonSource(event.target.value)}
          aria-label="Flashcard JSON source"
        />
        {loadError && <span className="panel-error">JSON error: {loadError}</span>}
      </section>

      <section className="panel preview-panel">
        <div className="panel-header">
          <h2 className="panel-title">Study deck</h2>
          <span className="panel-status">
            {cards.length ? `${Math.min(currentIndex + 1, cards.length)} / ${cards.length}` : 'No cards'}
          </span>
        </div>
        <div className="panel-meta flashcard-meta">
          <span>Correct: {correctCount}</span>
          <span>Wrong: {wrongCount}</span>
          <span>Remaining: {remainingCount}</span>
        </div>
        <div className="flashcard-stage">
          {currentCard ? (
            <button
              type="button"
              className="flashcard-card"
              onClick={handleReveal}
              disabled={isComplete}
              aria-pressed={isRevealed}
            >
              <div
                className={`flashcard-inner${isRevealed ? ' flashcard-inner--flipped' : ''}`}
              >
                <div className="flashcard-face flashcard-face--front">
                  <span>{currentCard.question}</span>
                </div>
                <div className="flashcard-face flashcard-face--back">
                  <span>{currentCard.answer}</span>
                </div>
              </div>
            </button>
          ) : (
            <div className="flashcard-placeholder">Load a JSON deck to begin.</div>
          )}
          {isComplete && cards.length > 0 && (
            <div className="flashcard-placeholder flashcard-complete">
              Deck complete. Shuffle or reload to study again.
            </div>
          )}
        </div>
        <div className="flashcard-actions">
          <button
            type="button"
            className="flashcard-button"
            onClick={handleReveal}
            disabled={!currentCard || isComplete}
          >
            {isRevealed ? 'Hide answer' : 'Reveal answer'}
          </button>
          <button
            type="button"
            className="flashcard-button"
            onClick={() => handleMark(true)}
            disabled={!currentCard || isComplete || !isRevealed}
          >
            Correct
          </button>
          <button
            type="button"
            className="flashcard-button"
            onClick={() => handleMark(false)}
            disabled={!currentCard || isComplete || !isRevealed}
          >
            Wrong
          </button>
          <button
            type="button"
            className="flashcard-button"
            onClick={handleShuffle}
            disabled={cards.length < 2}
          >
            Shuffle
          </button>
          <button
            type="button"
            className="flashcard-button"
            onClick={handleDownload}
            disabled={!jsonSource.trim() && !cards.length}
          >
            Download
          </button>
        </div>
        <div className="flashcard-hint">Recommended extension: .json</div>
      </section>
    </main>
  )
}

export default FlashcardPage
