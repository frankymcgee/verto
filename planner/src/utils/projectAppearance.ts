import colors from 'tailwindcss/colors'

export function diagonalShading(background: string, stripe: string) {
  return `repeating-linear-gradient(135deg, ${background} 0px, ${background} 4px, ${stripe} 4px, ${stripe} 8px)`
}

export function isCancelledProject(status?: string | null) {
  return ['cancelled', 'canceled'].includes(String(status || '').trim().toLowerCase())
}

export function cancelledProjectStyle() {
  return {
    backgroundColor: colors.gray[700],
    backgroundImage: diagonalShading(colors.gray[700], colors.gray[600]),
    borderColor: colors.gray[800],
    color: colors.gray[50],
  }
}
