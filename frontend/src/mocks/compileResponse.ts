import { gzipSync, gunzipSync, strToU8 } from 'fflate'
import { PDFDocument, StandardFonts, rgb } from 'pdf-lib'

export type CompileResponse = {
  source: string
  pdf: string
  synctex: string
}

export type SynctexPage = {
  page: number
  width: number
  height: number
}

export type SynctexMapping = {
  id: string
  line: number
  page: number
  x: number
  y: number
  width: number
  height: number
  label?: string
}

export type SynctexPayload = {
  version: number
  pages: SynctexPage[]
  mappings: SynctexMapping[]
}

type MockLine = {
  line: number
  text: string
  x: number
  y: number
  size: number
  label?: string
}

const PAGE_WIDTH = 612
const PAGE_HEIGHT = 792

const MOCK_SOURCE = [
  '% input',
  '\\documentclass{article}',
  '\\title{Local LaTeX Preview}',
  '\\author{Cheatsheet Maker}',
  '\\date{January 17, 2026}',
  '',
  '\\begin{document}',
  '\\maketitle',
  '',
  '\\section*{Purpose}',
  'This preview loads LaTeX from the mock compile response.',
  'Edit the source on the right to see synced highlights.',
  '',
  '\\section*{Math}',
  '\\[',
  'E = mc^2',
  '\\]',
  '',
  '\\section*{Checklist}',
  '\\begin{itemize}',
  '  \\item Write LaTeX on the right.',
  '  \\item Render PDF on the left.',
  '  \\item Sync highlights between both.',
  '\\end{itemize}',
  '\\end{document}',
].join('\n')

const MOCK_LINES: MockLine[] = [
  {
    line: 3,
    text: 'Local LaTeX Preview',
    x: 72,
    y: 720,
    size: 20,
    label: 'Title',
  },
  {
    line: 10,
    text: 'Purpose',
    x: 72,
    y: 680,
    size: 14,
  },
  {
    line: 11,
    text: 'This preview loads LaTeX from the mock compile response.',
    x: 72,
    y: 660,
    size: 12,
  },
  {
    line: 12,
    text: 'Edit the source on the right to see synced highlights.',
    x: 72,
    y: 642,
    size: 12,
  },
  {
    line: 16,
    text: 'E = mc^2',
    x: 72,
    y: 610,
    size: 12,
    label: 'Math',
  },
  {
    line: 19,
    text: 'Checklist',
    x: 72,
    y: 580,
    size: 14,
  },
  {
    line: 21,
    text: 'Write LaTeX on the right.',
    x: 90,
    y: 560,
    size: 12,
  },
  {
    line: 22,
    text: 'Render PDF on the left.',
    x: 90,
    y: 544,
    size: 12,
  },
  {
    line: 23,
    text: 'Sync highlights between both.',
    x: 90,
    y: 528,
    size: 12,
  },
]

const bytesToBase64 = (data: Uint8Array) => {
  let binary = ''
  const chunkSize = 0x8000
  for (let i = 0; i < data.length; i += chunkSize) {
    binary += String.fromCharCode(...data.subarray(i, i + chunkSize))
  }
  return window.btoa(binary)
}

const base64ToBytes = (base64: string) => {
  const binary = window.atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes
}

const buildMockPdf = async () => {
  const pdfDoc = await PDFDocument.create()
  const page = pdfDoc.addPage([PAGE_WIDTH, PAGE_HEIGHT])
  const font = await pdfDoc.embedFont(StandardFonts.Helvetica)

  MOCK_LINES.forEach((line) => {
    page.drawText(line.text, {
      x: line.x,
      y: line.y,
      size: line.size,
      font,
      color: rgb(0.1, 0.1, 0.1),
    })
  })

  const pdfBytes = await pdfDoc.save()
  const mappings: SynctexMapping[] = MOCK_LINES.map((line, index) => {
    const width = font.widthOfTextAtSize(line.text, line.size)
    return {
      id: `mock-${index}-${line.line}`,
      line: line.line,
      page: 1,
      x: line.x,
      y: line.y,
      width: width + 6,
      height: line.size * 1.25,
      label: line.label ?? line.text,
    }
  })

  return { pdfBase64: bytesToBase64(pdfBytes), mappings }
}

let cachedResponse: CompileResponse | null = null

export const createMockCompileResponse = async (): Promise<CompileResponse> => {
  if (cachedResponse) {
    return cachedResponse
  }

  const { pdfBase64, mappings } = await buildMockPdf()
  const payload: SynctexPayload = {
    version: 1,
    pages: [{ page: 1, width: PAGE_WIDTH, height: PAGE_HEIGHT }],
    mappings,
  }

  const synctexBase64 = bytesToBase64(
    gzipSync(strToU8(JSON.stringify(payload))),
  )

  cachedResponse = {
    source: MOCK_SOURCE,
    pdf: pdfBase64,
    synctex: synctexBase64,
  }

  return cachedResponse
}

export const parseSynctexPayload = (base64: string): SynctexPayload => {
  const payloadBytes = gunzipSync(base64ToBytes(base64))
  const payloadText = new TextDecoder().decode(payloadBytes)
  return JSON.parse(payloadText) as SynctexPayload
}
