import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type CSSProperties,
  type FormEvent,
} from 'react'
import './App.css'
import {
  type CompileResponse,
  type SynctexMapping,
  type SynctexPayload,
} from './synctex/compileResponse'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

GlobalWorkerOptions.workerSrc = workerSrc

const COMPILE_ENDPOINT = 'http://localhost:8000/compile'
const CHAT_ENDPOINT = 'http://localhost:8000/chat'
const STORAGE_KEY = 'local-preview-latex-source'
const LOAD_STATUS = {
  idle: 'Compile to preview',
  ready: 'PDF ready',
  loading: 'Compiling PDF...',
  error: 'PDF error',
} as const
const SYNC_STATUS = {
  pending: 'Sync pending',
  ready: 'Sync done',
  loading: 'Sync loading',
  dirty: 'Source differs from last compile',
} as const
const LINE_HEIGHT_PX = 20
const EDITOR_PADDING_PX = 12
const TYPE_ANIMATION_MAX_STEPS = 160
const BACKSPACE_ANIMATION_MAX_STEPS = 120
const TYPE_ANIMATION_DELAY_MS = 10
const BACKSPACE_ANIMATION_DELAY_MS = 8

type PageMetrics = {
  scale: number
  width: number
  height: number
  pageWidth: number
  pageHeight: number
  transform: number[]
}

type LineRange = {
  start: number
  end: number
}

type ChatSelectedLine = {
  line_number: number
  text: string
}

type ChatRequest = {
  prompt: string
  selected_line?: ChatSelectedLine       
  selected_lines?: ChatSelectedLine[]    
}

type ChatResponse = {
  reply: string
  selected_line?: ChatSelectedLine | null
  latex?: string | null
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  selectedLine?: ChatSelectedLine | null
}

const base64ToBytes = (base64: string) => {
  const binary = window.atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes
}

const getLineNumber = (source: string, index: number) =>
  source.slice(0, index).split('\n').length

const getLineRange = (source: string, lineNumber: number) => {
  const lines = source.split('\n')
  const clampedLine = Math.min(Math.max(lineNumber, 1), lines.length)
  let start = 0
  for (let i = 0; i < clampedLine - 1; i += 1) {
    start += lines[i].length + 1
  }
  const end = start + lines[clampedLine - 1].length
  return { start, end }
}

const normalizeLineRange = (startLine: number, endLine: number): LineRange => ({
  start: Math.min(startLine, endLine),
  end: Math.max(startLine, endLine),
})

const getSelectionLineRange = (
  source: string,
  selectionStart: number,
  selectionEnd: number,
) => {
  if (selectionStart === selectionEnd) return null
  const startIndex = Math.min(selectionStart, selectionEnd)
  const endIndex = Math.max(selectionStart, selectionEnd)
  const startLine = getLineNumber(source, startIndex)
  const endLine = getLineNumber(source, endIndex)
  if (startLine === endLine) return null
  return normalizeLineRange(startLine, endLine)
}

const getLineSpan = (source: string, range: LineRange) => {
  const lines = source.split('\n')
  const startLine = Math.min(Math.max(range.start, 1), lines.length)
  const endLine = Math.min(Math.max(range.end, 1), lines.length)
  let start = 0
  for (let i = 0; i < startLine - 1; i += 1) {
    start += lines[i].length + 1
  }
  let end = start
  for (let i = startLine - 1; i <= endLine - 1; i += 1) {
    end += lines[i].length + 1
  }
  if (endLine === lines.length) {
    end = Math.max(start, end - 1)
  }
  return { start, end }
}

const getLineTexts = (source: string, range: LineRange | null) => {
  if (!range) return []
  const lines = source.split('\n')
  const start = Math.max(1, range.start)
  const end = Math.min(lines.length, range.end)
  const result: ChatSelectedLine[] = []
  for (let i = start; i <= end; i += 1) {
    result.push({ line_number: i, text: lines[i - 1] })
  }
  return result
}

const getSyncStatus = (source: string, compiledSource?: string) => {
  if (!compiledSource) return SYNC_STATUS.pending
  return source === compiledSource ? SYNC_STATUS.ready : SYNC_STATUS.dirty
}

const createMessageId = () => {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const sleep = (ms: number) =>
  new Promise(resolve => {
    window.setTimeout(resolve, ms)
  })

const getStepSize = (length: number, maxSteps: number) =>
  Math.max(1, Math.ceil(length / maxSteps))

const normalizeLatex = (value: string) => value.replace(/\r\n/g, '\n')

function App() {
  const [latexSource, setLatexSource] = useState('')
  const [editorStatus, setEditorStatus] = useState('')
  const [previewStatus, setPreviewStatus] = useState(LOAD_STATUS.idle)
  const [syncStatus, setSyncStatus] = useState(SYNC_STATUS.pending)
  const [compileResponse, setCompileResponse] = useState<CompileResponse | null>(null)
  const [synctexPayload, setSynctexPayload] = useState<SynctexPayload | null>(null)
  const [pageMetrics, setPageMetrics] = useState<PageMetrics | null>(null)
  const [activeLine, setActiveLine] = useState<number | null>(null)
  const [selectedLineRange, setSelectedLineRange] = useState<LineRange | null>(null)
  const [isCompiling, setIsCompiling] = useState(false)
  const [compileError, setCompileError] = useState<string | null>(null)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatError, setChatError] = useState<string | null>(null)
  const [isSendingChat, setIsSendingChat] = useState(false)
  const [isApplyingLatex, setIsApplyingLatex] = useState(false)

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const editorRef = useRef<HTMLTextAreaElement | null>(null)
  const chatLogRef = useRef<HTMLDivElement | null>(null)
  const animationIdRef = useRef(0)
  const latexSourceRef = useRef(latexSource)

  const [chatHeight, setChatHeight] = useState(180) 
  const [isDragging, setIsDragging] = useState(false)
  

  // load initial source from local storage or sample file
  useEffect(() => {
    let isMounted = true
    const loadSource = async () => {
      let nextSource = ''
      let nextStatus = ''
      try {
        const stored = window.localStorage.getItem(STORAGE_KEY)
        if (stored) {
          nextSource = stored
          nextStatus = 'Local storage'
        }
      } catch {
        nextStatus = 'Local storage unavailable'
      }

      if (!nextSource) {
        try {
          const response = await fetch('/sample.tex')
          if (response.ok) {
            nextSource = await response.text()
            nextStatus = 'Sample file'
          }
        } catch {
          if (!nextStatus) nextStatus = 'Sample file unavailable'
        }
      }

      if (!nextSource && !nextStatus) nextStatus = 'No source loaded'

      if (isMounted) {
        setLatexSource(nextSource)
        setEditorStatus(nextStatus)
        setSyncStatus(getSyncStatus(nextSource))
      }
    }
    void loadSource()
    return () => {
      isMounted = false
    }
  }, [])

  // render pdf
  useEffect(() => {
    if (!compileResponse) return
    let isMounted = true

    const renderPdf = async () => {
      setPreviewStatus(LOAD_STATUS.loading)
      try {
        const data = base64ToBytes(compileResponse.pdf)
        const pdf = await getDocument({ data }).promise
        const page = await pdf.getPage(1)
        const scale = 1.25
        const viewport = page.getViewport({ scale })
        const canvas = canvasRef.current
        if (!canvas || !isMounted) return
        const ctx = canvas.getContext('2d')
        if (!ctx) {
          setPreviewStatus(LOAD_STATUS.error)
          return
        }
        canvas.width = viewport.width
        canvas.height = viewport.height
        await page.render({ canvasContext: ctx, viewport }).promise
        if (!isMounted) return
        setPageMetrics({
          scale,
          width: viewport.width,
          height: viewport.height,
          pageWidth: page.view[2] - page.view[0],
          pageHeight: page.view[3] - page.view[1],
          transform: Array.from((viewport as any).transform) as number[],
        })
        setPreviewStatus(LOAD_STATUS.ready)
      } catch {
        if (isMounted) setPreviewStatus(LOAD_STATUS.error)
      }
    }
    void renderPdf()
    return () => {
      isMounted = false
    }
  }, [compileResponse])

  useEffect(() => {
    if (!synctexPayload?.mappings.length) return
    setActiveLine(current => current ?? synctexPayload.mappings[0].line)
  }, [synctexPayload])

  useEffect(() => {
    latexSourceRef.current = latexSource
  }, [latexSource])

  const selectedLine = useMemo(() => {
    if (!activeLine) return null
    const text = getLineTexts(latexSource, activeLine)
    if (text === null) return null
    return { line_number: activeLine, text }
  }, [activeLine, latexSource])

  const highlightRange = useMemo<LineRange | null>(() => {
    if (selectedLineRange) return selectedLineRange
    if (activeLine) return { start: activeLine, end: activeLine }
    return null
  }, [activeLine, selectedLineRange])

  const editorHighlightStyle = useMemo<CSSProperties | undefined>(() => {
    if (!highlightRange) return undefined
    const startPx =
      EDITOR_PADDING_PX + (highlightRange.start - 1) * LINE_HEIGHT_PX
    const endPx = EDITOR_PADDING_PX + highlightRange.end * LINE_HEIGHT_PX
    const highlightColor = 'rgba(192, 158, 255, 0.18)'
    return {
      backgroundImage: `linear-gradient(to bottom, transparent 0, transparent ${startPx}px, ${highlightColor} ${startPx}px, ${highlightColor} ${endPx}px, transparent ${endPx}px, transparent 100%)`,
      backgroundRepeat: 'no-repeat',
      backgroundAttachment: 'local',
      backgroundSize: '100% 100%',
    }
  }, [highlightRange])

  useEffect(() => {
    const log = chatLogRef.current
    if (!log) return
    log.scrollTop = log.scrollHeight
  }, [chatMessages, isSendingChat])

  // editor utilities
  const persistLatex = (src: string) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, src)
      setEditorStatus('Local storage')
    } catch {
      setEditorStatus('Local storage unavailable')
    }
  }

  const applyLatexReplacement = useCallback(
    async (range: LineRange, latex: string) => {
      const normalizedLatex = normalizeLatex(latex)
      const source = latexSourceRef.current
      if (!source) return
      const span = getLineSpan(source, range)
      const prefix = source.slice(0, span.start)
      const suffix = source.slice(span.end)
      const removedText = source.slice(span.start, span.end)
      const animationId = animationIdRef.current + 1
      animationIdRef.current = animationId

      setIsApplyingLatex(true)
      try {
        if (removedText.length > 0) {
          const deleteStep = getStepSize(
            removedText.length,
            BACKSPACE_ANIMATION_MAX_STEPS,
          )
          for (let i = removedText.length; i >= 0; i -= deleteStep) {
            if (animationIdRef.current !== animationId) return
            setLatexSource(prefix + removedText.slice(0, i) + suffix)
            await sleep(BACKSPACE_ANIMATION_DELAY_MS)
          }
        }

        const typeStep = getStepSize(
          normalizedLatex.length || 1,
          TYPE_ANIMATION_MAX_STEPS,
        )
        for (let i = 0; i <= normalizedLatex.length; i += typeStep) {
          if (animationIdRef.current !== animationId) return
          setLatexSource(prefix + normalizedLatex.slice(0, i) + suffix)
          await sleep(TYPE_ANIMATION_DELAY_MS)
        }

        const finalSource = prefix + normalizedLatex + suffix
        if (animationIdRef.current !== animationId) return
        setLatexSource(finalSource)
        persistLatex(finalSource)
        setSyncStatus(getSyncStatus(finalSource, compileResponse?.source))

        const lineCount = normalizedLatex.length
          ? normalizedLatex.split('\n').length
          : 1
        const updatedRange = {
          start: range.start,
          end: range.start + Math.max(lineCount - 1, 0),
        }
        setSelectedLineRange(updatedRange)
        setActiveLine(updatedRange.end)
      } finally {
        if (animationIdRef.current === animationId) {
          setIsApplyingLatex(false)
        }
      }
    },
    [compileResponse?.source, persistLatex],
  )

  const handleEditorChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    const { value } = e.target
    const selectionStart = e.target.selectionStart ?? 0
    const selectionEnd = e.target.selectionEnd ?? selectionStart
    setLatexSource(value)
    persistLatex(value)
    setSyncStatus(getSyncStatus(value, compileResponse?.source))
    setActiveLine(getLineNumber(value, selectionStart))
    setSelectedLineRange(getSelectionLineRange(value, selectionStart, selectionEnd))
  }

  const handleCompile = useCallback(async () => {
    if (!latexSource.trim()) {
      setCompileError('Add LaTeX source before compiling.')
      setPreviewStatus(LOAD_STATUS.error)
      return
    }
    setIsCompiling(true)
    setCompileError(null)
    setPreviewStatus(LOAD_STATUS.loading)
    setSyncStatus(SYNC_STATUS.loading)

    try {
      const response = await fetch(COMPILE_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: latexSource }),
      })

      if (!response.ok) {
        const errorText = await response.text()
        let errorMessage = 'Compile failed'
        try {
          const parsed = JSON.parse(errorText) as { error?: string }
          errorMessage = parsed.error ?? errorText
        } catch {
          if (errorText) errorMessage = errorText
        }
        throw new Error(errorMessage)
      }

      const data = (await response.json()) as CompileResponse
      const synctexPayload: SynctexPayload = {
        version: 1,
        pages: [{ page: 1, width: 612, height: 792 }],
        mappings: data.mappings ?? [],
      }

      setCompileResponse(data)
      setSynctexPayload(synctexPayload)
      setSyncStatus(getSyncStatus(latexSource, data.source))
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Compile failed'
      setCompileError(message)
      setPreviewStatus(LOAD_STATUS.error)
      setSyncStatus(getSyncStatus(latexSource, compileResponse?.source))
    } finally {
      setIsCompiling(false)
    }
  }, [latexSource, compileResponse])

  const handleChatInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setChatInput(e.target.value)
  }

  const handleChatSubmit = useCallback(
    async (event?: FormEvent<HTMLFormElement>) => {
      event?.preventDefault()
      if (isSendingChat || isApplyingLatex) return
      const prompt = chatInput.trim()
      if (!prompt) return

      const rangeForRequest =
        selectedLineRange ?? (activeLine ? { start: activeLine, end: activeLine } : null)

      setIsSendingChat(true)
      setChatError(null)

      const userMessage: ChatMessage = {
        id: createMessageId(),
        role: 'user',
        content: prompt,
        selectedLine: selectedLine ?? null,
      }
      setChatMessages(current => [...current, userMessage])
      setChatInput('')

      try {
        const payload: ChatRequest = { prompt }

        if (selectedLineRange) {
          payload.selected_lines = getLineTexts(latexSource, selectedLineRange)
        } else if (selectedLine) {
          payload.selected_line = selectedLine
        }

        const response = await fetch(CHAT_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })

        if (!response.ok) {
          const errorText = await response.text()
          let errorMessage = 'Chat request failed'
          try {
            const parsed = JSON.parse(errorText) as { detail?: string; error?: string }
            errorMessage = parsed.detail ?? parsed.error ?? errorText
          } catch {
            if (errorText) errorMessage = errorText
          }
          throw new Error(errorMessage)
        }

        const data = (await response.json()) as ChatResponse
        const replyText = data.reply?.trim()
        if (!replyText) {
          throw new Error('Chatbot returned an empty response.')
        }

        const assistantMessage: ChatMessage = {
          id: createMessageId(),
          role: 'assistant',
          content: replyText,
          selectedLine: data.selected_line ?? null,
        }
        setChatMessages(current => [...current, assistantMessage])

        if (typeof data.latex === 'string' && rangeForRequest) {
          await applyLatexReplacement(rangeForRequest, data.latex)
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Chat request failed'
        setChatError(message)
      } finally {
        setIsSendingChat(false)
      }
    },
    [
      activeLine,
      applyLatexReplacement,
      chatInput,
      isApplyingLatex,
      isSendingChat,
      selectedLine,
      selectedLineRange,
    ],
  )

  const updateActiveLineFromEditor = useCallback(() => {
  const editor = editorRef.current
  if (!editor) return
  if (document.activeElement !== editor) {
    return
  }
  const selectionStart = editor.selectionStart ?? 0
  const selectionEnd = editor.selectionEnd ?? selectionStart
  setActiveLine(getLineNumber(editor.value, selectionStart))
  const range = getSelectionLineRange(editor.value, selectionStart, selectionEnd)
  if (range) {
    setSelectedLineRange(range)
  }
}, [])

  const focusEditorRange = useCallback(
    (startLine: number, endLine: number) => {
      const editor = editorRef.current
      if (!editor) return
      const range = normalizeLineRange(startLine, endLine)
      const start = getLineRange(latexSource, range.start).start
      const end = getLineRange(latexSource, range.end).end
      editor.focus()
      editor.setSelectionRange(start, end)
      const targetScroll = Math.max(
        0,
        (range.start - 1) * LINE_HEIGHT_PX - editor.clientHeight / 2,
      )
      editor.scrollTop = targetScroll
    },
    [latexSource],
  )

  const focusEditorLine = useCallback(
    (line: number) => {
      const editor = editorRef.current
      if (!editor) return
      const { start, end } = getLineRange(latexSource, line)
      editor.focus()
      editor.setSelectionRange(start, end)
      const targetScroll = Math.max(
        0,
        (line - 1) * LINE_HEIGHT_PX - editor.clientHeight / 2,
      )
      editor.scrollTop = targetScroll
    },
    [latexSource],
  )

  const handleHighlightClick = useCallback(
    (m: SynctexMapping, event?: React.MouseEvent<HTMLButtonElement>) => {
      const anchorLine = selectedLineRange?.start ?? activeLine
      if (event?.shiftKey && anchorLine) {
        const range = normalizeLineRange(anchorLine, m.line)
        setSelectedLineRange(range)
        setActiveLine(m.line)
        focusEditorRange(range.start, range.end)
        return
      }
      setSelectedLineRange(null)
      setActiveLine(m.line)
      focusEditorLine(m.line)
    },
    [activeLine, focusEditorLine, focusEditorRange, selectedLineRange],
  )

  const isLineHighlighted = useCallback(
    (line: number) => {
      if (selectedLineRange) {
        return line >= selectedLineRange.start && line <= selectedLineRange.end
      }
      return line === activeLine
    },
    [activeLine, selectedLineRange],
  )

  const getHighlightStyle = useCallback(
  (m: SynctexMapping) => {
    if (!pageMetrics) return undefined
    const [a, b, c, d, e, f] = pageMetrics.transform
    const toViewport = (x: number, y: number) => [
      a * x + c * y + e,
      b * x + d * y + f,
    ] as const

    const [x1, y1] = toViewport(m.x, m.y)
    const [x2, y2] = toViewport(m.x + m.width, m.y + m.height)

    return {
      left: Math.min(x1, x2),
      top: Math.min(y1, y2),
      width: Math.abs(x2 - x1),
      height: Math.abs(y2 - y1),
    }
  },
  [pageMetrics],
)

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const parent = document.querySelector('.preview-panel') as HTMLElement | null
      if (!parent) return
      const rect = parent.getBoundingClientRect()
      // distance from bottom of panel
      const newHeight = Math.max(50, rect.bottom - e.clientY)
      setChatHeight(newHeight)
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])


  return (
    <main className="layout">
      <section className="panel explorer-panel">
        <div className="panel-header">
          <h1 className="panel-title">LaTeX</h1>
          <div className="panel-actions">
            <span className="panel-status">{editorStatus}</span>
            <button
              type="button"
              className={`compile-button${isCompiling ? ' compile-button--loading' : ''}`}
              onClick={handleCompile}
              disabled={isCompiling || !latexSource.trim()}
              aria-busy={isCompiling}
            >
              {isCompiling ? 'Compiling...' : 'Compile'}
            </button>
          </div>
        </div>
        <textarea
          className="editor"
          ref={editorRef}
          spellCheck={false}
          value={latexSource}
          readOnly={isApplyingLatex}
          onChange={handleEditorChange}
          onFocus={() => setIsEditorFocused(true)}
          onBlur={() => setIsEditorFocused(false)}
          onClick={updateActiveLineFromEditor}
          onKeyUp={updateActiveLineFromEditor}
          onMouseUp={updateActiveLineFromEditor}
          aria-label="LaTeX source file"
          aria-busy={isApplyingLatex}
        />
      </section>

      <section className="panel preview-panel">
        <div className="panel-header">
          <h2 className="panel-title">Rendered PDF</h2>
          <span className="panel-status">{previewStatus}</span>
        </div>
        <div className="panel-meta">
          <span>Sync: {syncStatus}</span>
          <span>
            Line:{' '}
            {selectedLineRange
              ? `${selectedLineRange.start}-${selectedLineRange.end}`
              : activeLine ?? '—'}
          </span>
          <span>Tip: Shift-click a highlight to select a range.</span>
          {compileError && <span className="panel-error">Compile error: {compileError}</span>}
        </div>
        <div className="preview-frame">
          <div className="pdf-stage">
            {previewStatus !== LOAD_STATUS.ready && (
              <div className="preview-placeholder">{previewStatus}</div>
            )}
            <canvas ref={canvasRef} className="pdf-canvas" />
            {pageMetrics && synctexPayload && (
              <div
                className="pdf-overlay"
                style={{ width: pageMetrics.width, height: pageMetrics.height }}
              >
                {synctexPayload.mappings
                  .filter(m => m.page === 1)
                  .map((m, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className={`pdf-highlight${isLineHighlighted(m.line) ? ' pdf-highlight--active' : ''}`}
                      style={getHighlightStyle(m)}
                      onClick={event => handleHighlightClick(m, event)}
                      title={`Line ${m.line}`}
                      aria-label={`Highlight for line ${m.line}`}
                    />
                  ))}
              </div>
            )}
          </div>
        </div>

        <div
          className="panel-divider draggable-divider"
          onMouseDown={handleMouseDown}
        />

        <div
          className="chatbot-panel"
          style={{ height: `${chatHeight}px` }}
        >
          <div className="panel-header">
            <h2 className="panel-title">LaTexBot</h2>
            <span className="panel-status">
              {isSendingChat ? 'Sending...' : 'Ready'}
            </span>
          </div>
          <div className="chat-body" ref={chatLogRef} role="log" aria-live="polite">
            {chatMessages.length === 0 ? (
              <div className="chat-empty">Ask a question about your cheatsheet.</div>
            ) : (
              chatMessages.map(message => (
                <div
                  key={message.id}
                  className={`chat-message chat-message--${message.role}`}
                >
                  <span className="chat-message-role">
                    {message.role === 'user' ? 'You' : 'Assistant'}
                  </span>
                  <p className="chat-message-content">{message.content}</p>
                  {/* {message.selectedLine && (
                    <div className="chat-message-line">
                      <span>Line {message.selectedLine.line_number}</span>
                      <code>
                        {message.selectedLine.text.trim()
                          ? message.selectedLine.text
                          : 'Empty line selected.'}
                      </code>
                    </div>
                  )} */}
                </div>
              ))
            )}
          </div>
          {/* <div className="chat-context">
            <div className="chat-context-header">
              <span className="chat-context-label">Selected line</span>
              <span className="chat-context-value">
                {selectedLine ? `Line ${selectedLine.line_number}` : '—'}
              </span>
            </div>
            <div className="chat-context-text">
              {selectedLine
                ? selectedLine.text.trim()
                  ? selectedLine.text
                  : 'Empty line selected.'
                : 'Click a line in the editor to include context.'}
            </div>
          </div> */}
          <form className="chat-form" onSubmit={handleChatSubmit}>
            <textarea
              className="chat-input"
              value={chatInput}
              onChange={handleChatInputChange}
              placeholder="Ask anything about the cheatsheet..."
              rows={3}
              aria-label="Chat prompt"
            />
            <div className="chat-actions">
              <span className="chat-hint">
                {isSendingChat ? 'Waiting for response...' : ''}
              </span>
              <button
                type="submit"
                className="chat-send"
                disabled={isSendingChat || isApplyingLatex || !chatInput.trim()}
              >
                Send
              </button>
            </div>
          </form>
          {chatError && <div className="chat-error">Chat error: {chatError}</div>}
        </div>
      </section>
    </main>
  )
}

export default App