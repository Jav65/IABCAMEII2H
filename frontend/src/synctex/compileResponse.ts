import { gunzipSync } from 'fflate'

export type CompileResponse = {
  source: string
  pdf: string
  synctex: string
  mappings?: SynctexMapping[]
}

export type SynctexPage = {
  page: number
  width: number
  height: number
}

export type SynctexMapping = {
  line: number
  page: number
  x: number
  y: number
  width: number
  height: number
}

export type SynctexPayload = {
  version: number
  pages: SynctexPage[]
  mappings: SynctexMapping[]
}

/** utility: base64 → Uint8Array */
const base64ToBytes = (base64: string) => {
  const binary = window.atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}

/** turn backend's base64‑gzipped synctex JSON into an object */
export const parseSynctexPayload = (base64: string): SynctexPayload => {
  const payloadBytes = gunzipSync(base64ToBytes(base64))
  const payloadText = new TextDecoder().decode(payloadBytes)
  console.log('Decoded Synctex text:', payloadText)
  return JSON.parse(payloadText) as SynctexPayload
}