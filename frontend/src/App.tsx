import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import './App.css'
import {
  type CompileResponse,
  type SynctexMapping,
  type SynctexPayload,
} from './synctex/compileResponse'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

GlobalWorkerOptions.workerSrc = workerSrc

const COMPILE_ENDPOINT = 'http://localhost:5000/compile'
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

type PageMetrics = {
  scale: number
  width: number
  height: number
  pageWidth: number
  pageHeight: number
  transform: number[]
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

const getSyncStatus = (source: string, compiledSource?: string) => {
  if (!compiledSource) return SYNC_STATUS.pending
  return source === compiledSource ? SYNC_STATUS.ready : SYNC_STATUS.dirty
}

function App() {
  const [latexSource, setLatexSource] = useState('')
  const [editorStatus, setEditorStatus] = useState('')
  const [previewStatus, setPreviewStatus] = useState(LOAD_STATUS.idle)
  const [syncStatus, setSyncStatus] = useState(SYNC_STATUS.pending)
  const [compileResponse, setCompileResponse] = useState<CompileResponse | null>(null)
  const [synctexPayload, setSynctexPayload] = useState<SynctexPayload | null>(null)
  const [pageMetrics, setPageMetrics] = useState<PageMetrics | null>(null)
  const [activeLine, setActiveLine] = useState<number | null>(null)
  const [isCompiling, setIsCompiling] = useState(false)
  const [compileError, setCompileError] = useState<string | null>(null)

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const editorRef = useRef<HTMLTextAreaElement | null>(null)

  const [chatHeight, setChatHeight] = useState(150) 
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

  // editor utilities
  const persistLatex = (src: string) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, src)
      setEditorStatus('Local storage')
    } catch {
      setEditorStatus('Local storage unavailable')
    }
  }

  const handleEditorChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    const { value } = e.target
    const pos = e.target.selectionStart ?? 0
    setLatexSource(value)
    persistLatex(value)
    setSyncStatus(getSyncStatus(value, compileResponse?.source))
    setActiveLine(getLineNumber(value, pos))
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

  const updateActiveLineFromEditor = useCallback(() => {
    const editor = editorRef.current
    if (!editor) return
    const pos = editor.selectionStart ?? 0
    setActiveLine(getLineNumber(editor.value, pos))
  }, [])

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
    (m: SynctexMapping) => {
      setActiveLine(m.line)
      focusEditorLine(m.line)
    },
    [focusEditorLine],
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
          onChange={handleEditorChange}
          onClick={updateActiveLineFromEditor}
          onKeyUp={updateActiveLineFromEditor}
          onSelect={updateActiveLineFromEditor}
          aria-label="LaTeX source file"
        />
      </section>

      <section className="panel preview-panel">
        <div className="panel-header">
          <h2 className="panel-title">Rendered PDF</h2>
          <span className="panel-status">{previewStatus}</span>
        </div>
        <div className="panel-meta">
          <span>Sync: {syncStatus}</span>
          <span>Line: {activeLine ?? '—'}</span>
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
                      className={`pdf-highlight${m.line === activeLine ? ' pdf-highlight--active' : ''}`}
                      style={getHighlightStyle(m)}
                      onClick={() => handleHighlightClick(m)}
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
            <h2 className="panel-title">Chatbot</h2>
          </div>
          <div className="chat-placeholder">

          </div>
        </div>
      </section>
    </main>
  )
}

export default App