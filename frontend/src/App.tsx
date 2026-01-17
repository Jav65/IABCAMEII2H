import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import './App.css'
import {
  createMockCompileResponse,
  parseSynctexPayload,
  type CompileResponse,
  type SynctexMapping,
  type SynctexPayload,
} from './mocks/compileResponse'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

GlobalWorkerOptions.workerSrc = workerSrc

const STORAGE_KEY = 'local-preview-latex-source'
const LOAD_STATUS = {
  ready: 'PDF ready',
  loading: 'Loading mock PDF...',
  error: 'PDF error',
} as const
const SYNC_STATUS = {
  ready: 'Sync ready',
  loading: 'Sync loading',
  dirty: 'Source differs from mock compile',
} as const
const LINE_HEIGHT_PX = 20

type PageMetrics = {
  scale: number
  width: number
  height: number
  pageWidth: number
  pageHeight: number
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
  if (!compiledSource) {
    return SYNC_STATUS.loading
  }
  return source === compiledSource ? SYNC_STATUS.ready : SYNC_STATUS.dirty
}

function App() {
  const [latexSource, setLatexSource] = useState('')
  const [editorStatus, setEditorStatus] = useState('')
  const [previewStatus, setPreviewStatus] = useState(LOAD_STATUS.loading)
  const [syncStatus, setSyncStatus] = useState(SYNC_STATUS.loading)
  const [compileResponse, setCompileResponse] = useState<CompileResponse | null>(
    null,
  )
  const [synctexPayload, setSynctexPayload] = useState<SynctexPayload | null>(
    null,
  )
  const [pageMetrics, setPageMetrics] = useState<PageMetrics | null>(null)
  const [activeLine, setActiveLine] = useState<number | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const editorRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    let isMounted = true

    const loadMockCompile = async () => {
      setPreviewStatus(LOAD_STATUS.loading)
      setSyncStatus(SYNC_STATUS.loading)

      try {
        const response = await createMockCompileResponse()
        if (!isMounted) {
          return
        }
        setCompileResponse(response)
        setSynctexPayload(parseSynctexPayload(response.synctex))

        let nextSource = response.source
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

        if (isMounted) {
          setLatexSource(nextSource)
          setEditorStatus(nextStatus)
          setSyncStatus(getSyncStatus(nextSource, response.source))
        }
      } catch {
        if (isMounted) {
          setPreviewStatus(LOAD_STATUS.error)
          setEditorStatus('Mock load error')
        }
      }
    }

    void loadMockCompile()

    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    if (!compileResponse) {
      return
    }
    let isMounted = true

    const renderPdf = async () => {
      setPreviewStatus(LOAD_STATUS.loading)

      try {
        const data = base64ToBytes(compileResponse.pdf)
        const loadingTask = getDocument({ data })
        const pdf = await loadingTask.promise
        const page = await pdf.getPage(1)
        const scale = 1.25
        const viewport = page.getViewport({ scale })
        const canvas = canvasRef.current
        if (!canvas || !isMounted) {
          return
        }
        const context = canvas.getContext('2d')
        if (!context) {
          setPreviewStatus(LOAD_STATUS.error)
          return
        }
        canvas.width = viewport.width
        canvas.height = viewport.height
        const renderTask = page.render({ canvasContext: context, viewport })
        await renderTask.promise
        if (!isMounted) {
          return
        }
        const pageWidth = page.view[2] - page.view[0]
        const pageHeight = page.view[3] - page.view[1]
        setPageMetrics({
          scale,
          width: viewport.width,
          height: viewport.height,
          pageWidth,
          pageHeight,
        })
        setPreviewStatus(LOAD_STATUS.ready)
      } catch {
        if (isMounted) {
          setPreviewStatus(LOAD_STATUS.error)
        }
      }
    }

    void renderPdf()

    return () => {
      isMounted = false
    }
  }, [compileResponse])

  useEffect(() => {
    if (!synctexPayload?.mappings.length) {
      return
    }
    setActiveLine((current) => current ?? synctexPayload.mappings[0].line)
  }, [synctexPayload])

  const persistLatex = (source: string) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, source)
      setEditorStatus((currentStatus) =>
        currentStatus === 'Local storage unavailable'
          ? currentStatus
          : 'Local storage',
      )
    } catch {
      setEditorStatus('Local storage unavailable')
    }
  }

  const handleEditorChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    const { value } = event.target
    const selectionStart = event.target.selectionStart ?? 0
    setLatexSource(value)
    persistLatex(value)
    setSyncStatus(getSyncStatus(value, compileResponse?.source))
    setActiveLine(getLineNumber(value, selectionStart))
  }

  const updateActiveLineFromEditor = useCallback(() => {
    const editor = editorRef.current
    if (!editor) {
      return
    }
    const selectionStart = editor.selectionStart ?? 0
    setActiveLine(getLineNumber(editor.value, selectionStart))
  }, [])

  const focusEditorLine = useCallback(
    (lineNumber: number) => {
      const editor = editorRef.current
      if (!editor) {
        return
      }
      const { start, end } = getLineRange(latexSource, lineNumber)
      editor.focus()
      editor.setSelectionRange(start, end)
      const targetScroll = Math.max(
        0,
        (lineNumber - 1) * LINE_HEIGHT_PX - editor.clientHeight / 2,
      )
      editor.scrollTop = targetScroll
    },
    [latexSource],
  )

  const activeMappings = useMemo(() => {
    if (!synctexPayload || activeLine === null) {
      return []
    }
    return synctexPayload.mappings.filter(
      (mapping) => mapping.line === activeLine,
    )
  }, [synctexPayload, activeLine])

  const activeMappingIds = useMemo(
    () => new Set(activeMappings.map((mapping) => mapping.id)),
    [activeMappings],
  )

  const handleHighlightClick = useCallback(
    (mapping: SynctexMapping) => {
      setActiveLine(mapping.line)
      focusEditorLine(mapping.line)
    },
    [focusEditorLine],
  )

  const getHighlightStyle = useCallback(
    (mapping: SynctexMapping) => {
      if (!pageMetrics) {
        return undefined
      }
      const top =
        (pageMetrics.pageHeight - mapping.y - mapping.height) *
        pageMetrics.scale
      const left = mapping.x * pageMetrics.scale
      const width = mapping.width * pageMetrics.scale
      const height = mapping.height * pageMetrics.scale
      return { top, left, width, height }
    },
    [pageMetrics],
  )

  return (
    <main className="layout">
      <section className="panel explorer-panel">
        <div className="panel-header">
          <h1 className="panel-title">Latex</h1>
          <span className="panel-status">{editorStatus}</span>
        </div>
        <div className="panel-meta">
          <span>Mappings: {synctexPayload?.mappings.length ?? 0}</span>
          <span>
            Active region:{' '}
            {activeMappings.length
              ? activeMappings.map((mapping) => mapping.label).join(', ')
              : '—'}
          </span>
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
          <span>Active line: {activeLine ?? '—'}</span>
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
                  .filter((mapping) => mapping.page === 1)
                  .map((mapping) => (
                    <button
                      key={mapping.id}
                      type="button"
                      className={`pdf-highlight${
                        activeMappingIds.has(mapping.id)
                          ? ' pdf-highlight--active'
                          : ''
                      }`}
                      style={getHighlightStyle(mapping)}
                      onClick={() => handleHighlightClick(mapping)}
                      title={`Line ${mapping.line}: ${mapping.label ?? ''}`}
                      aria-label={`Highlight for line ${mapping.line}`}
                    />
                  ))}
              </div>
            )}
          </div>
        </div>

        <div className="panel-divider" />

        <div className="panel-header">
          <h2 className="panel-title">Chatbot</h2>
          <span className="panel-status">Not implemented</span>
        </div>
        <div className="chat-placeholder">Chatbot area</div>
      </section>
    </main>
  )
}

export default App
