import { describe, expect, it } from 'vitest'
import { parseQrLink } from '../src/lib/qrLinks'
import jsQR from 'jsqr'

const origin = 'https://verto.test'
// A real QR symbol generated independently, including its quiet zone.
const symbol = `
00000000000000000000000000000000000000000
00000000000000000000000000000000000000000
00000000000000000000000000000000000000000
00000000000000000000000000000000000000000
00001111111010001100110111011011111110000
00001000001010100100101000111010000010000
00001011101001010000110110111010111010000
00001011101011011010100001110010111010000
00001011101001100110010011011010111010000
00001000001001100110010111001010000010000
00001111111010101010101010101011111110000
00000000000011001010010010001000000000000
00001011011101111010111101010010010110000
00000010100110100000100111110011011010000
00001011101001111010010010010011110110000
00000001110110111111101010001001010000000
00001101101110111001001011101101110100000
00000010110011010100111110000001000100000
00001000001000001101101100001010100000000
00000100110000001000101001000110011000000
00000110011111111001001001111110111000000
00000000100010110001010011111010110110000
00001011111111110001110010001011101100000
00000010010010010011100100100100100100000
00000101111100101111001010001001011010000
00001101110010110101011101011010000010000
00000001111110100110101010111111100110000
00000111110111001000101100001111010100000
00001011111000100001011000111111110100000
00000000000010010111110110101000110000000
00001111111010000110000100011010100100000
00001000001010110101100011111000111100000
00001011101000111001010001011111101110000
00001011101011111100011000110001010010000
00001011101011100110000010011011001000000
00001000001000011001111000111111110010000
00001111111011000011111011000000101000000
00000000000000000000000000000000000000000
00000000000000000000000000000000000000000
00000000000000000000000000000000000000000
00000000000000000000000000000000000000000`.trim().split('\n')
describe('document QR destinations', () => {
  it('reads a real document QR image without browser barcode APIs', () => {
    const size = symbol.length * 5
    const data = new Uint8ClampedArray(size * size * 4)
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
      const offset = (y * size + x) * 4, shade = symbol[Math.floor(y / 5)][Math.floor(x / 5)] === '1' ? 0 : 255
      data.set([shade, shade, shade, 255], offset)
    }
    const decoded = jsQR(data, size, size)
    expect(decoded?.data).toBe(`${origin}/verto-mobile/edit/take-5/TAKE-001`)
    expect(parseQrLink(decoded.data, origin)).toEqual({ kind: 'mobile', url: '/edit/take-5/TAKE-001' })
  })
  it('keeps printed JHA revisions inside the mobile app', () => {
    expect(parseQrLink(`${origin}/verto-mobile/jha/JHA-1?revision=2`, origin)).toEqual({ kind: 'mobile', url: '/jha/JHA-1?revision=2' })
  })
  it('opens other mobile documents and preserves new-form prefills', () => {
    expect(parseQrLink('/verto-mobile/edit/take-5/TAKE%2F001', origin)).toEqual({ kind: 'mobile', url: '/edit/take-5/TAKE%2F001' })
    expect(parseQrLink('/verto-mobile/new/field-interaction?project=PROJ-1', origin)).toEqual({ kind: 'mobile', url: '/new/field-interaction?project=PROJ-1' })
  })
  it('resolves standard Desk and print links as documents, never executes a print action', () => {
    expect(parseQrLink('/app/field-interaction/FI%2F001', origin)).toEqual({ kind: 'desk', doctype: 'field-interaction', name: 'FI/001' })
    expect(parseQrLink('/printview?doctype=Take+5&name=T-1&trigger_print=1', origin)).toEqual({ kind: 'desk', doctype: 'Take 5', name: 'T-1', revision: undefined })
  })
  it('keeps same-site private PDF links in the document drawer', () => {
    expect(parseQrLink('/private/files/permit.pdf?fid=FILE-1', origin)).toEqual({ kind: 'file', url: '/private/files/permit.pdf?fid=FILE-1' })
  })
  it.each(['https://other.test/app/task/T-1', '//other.test/app/task/T-1', 'javascript:alert(1)', 'data:text/html,test',
    'https://user:pass@verto.test/app/task/T-1', '/api/method/logout', '/login?redirect-to=/app/task/T-1',
    '/files/untrusted.html', '/verto-mobile/logout', '/verto-mobile/edit%2Ftake-5/T-1', '/app/task/%0aBAD', 'hello', '/app/task/'])('rejects unsafe or unsupported payload %s', value => {
    expect(() => parseQrLink(value, origin)).toThrow()
  })
})
