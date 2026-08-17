type Values = Record<string, any>

function normaliseExpression(expression?: string) {
  return String(expression || '').trim()
}

function isEmpty(value: any) {
  return value === undefined ||
    value === null ||
    value === '' ||
    value === false ||
    value === 0
}

function isTruthy(value: any) {
  if (Array.isArray(value)) {
    return value.length > 0
  }

  if (typeof value === 'string') {
    return value.trim() !== ''
  }

  return Boolean(value)
}

function normaliseValue(value: any) {
  if (value === undefined || value === null) {
    return ''
  }

  return value
}

function getDocProxy(values: Values) {
  return new Proxy(values, {
    get(target, property) {
      if (typeof property !== 'string') {
        return undefined
      }

      return normaliseValue(target[property])
    },

    has() {
      return true
    },
  })
}

function evaluateSimpleFieldExpression(expression: string, values: Values) {
  const fieldname = expression
    .replace(/^doc\./, '')
    .trim()

  if (!fieldname) {
    return true
  }

  return isTruthy(values[fieldname])
}

function evaluateEvalExpression(expression: string, values: Values) {
  const rawExpression = expression.replace(/^eval:/, '').trim()

  if (!rawExpression) {
    return true
  }

  try {
    const doc = getDocProxy(values)

    const evaluator = new Function(
      'doc',
      'values',
      'is_empty',
      'is_not_empty',
      'in_list',
      `
        try {
          return Boolean(${rawExpression})
        } catch (error) {
          return false
        }
      `
    )

    return Boolean(
      evaluator(
        doc,
        values,
        isEmpty,
        (value: any) => !isEmpty(value),
        (items: any[], value: any) => Array.isArray(items) && items.includes(value)
      )
    )
  } catch {
    return false
  }
}

function evaluateNonEvalExpression(expression: string, values: Values) {
  const trimmed = expression.trim()

  if (!trimmed) {
    return true
  }

  if (/^[a-zA-Z0-9_]+$/.test(trimmed)) {
    return evaluateSimpleFieldExpression(trimmed, values)
  }

  if (/^doc\.[a-zA-Z0-9_]+$/.test(trimmed)) {
    return evaluateSimpleFieldExpression(trimmed, values)
  }

  const docComparison = trimmed.match(/^doc\.([a-zA-Z0-9_]+)\s*(===|==|!==|!=)\s*["'](.*)["']$/)
  const plainComparison = trimmed.match(/^([a-zA-Z0-9_]+)\s*(===|==|!==|!=)\s*["'](.*)["']$/)

  const match = docComparison || plainComparison

  if (match) {
    const fieldname = match[1]
    const operator = match[2]
    const expected = match[3]
    const actual = String(values[fieldname] ?? '')

    if (operator === '!=' || operator === '!==') {
      return actual !== expected
    }

    return actual === expected
  }

  return false
}

export function evaluateDependsOn(expression?: string, values: Values = {}) {
  const dependsOn = normaliseExpression(expression)

  if (!dependsOn) {
    return true
  }

  if (dependsOn.startsWith('eval:')) {
    return evaluateEvalExpression(dependsOn, values)
  }

  return evaluateNonEvalExpression(dependsOn, values)
}

export function evaluateMandatoryDependsOn(expression?: string, values: Values = {}) {
  const dependsOn = normaliseExpression(expression)

  if (!dependsOn) {
    return false
  }

  return evaluateDependsOn(dependsOn, values)
}

export function evaluateReadOnlyDependsOn(expression?: string, values: Values = {}) {
  const dependsOn = normaliseExpression(expression)

  if (!dependsOn) {
    return false
  }

  return evaluateDependsOn(dependsOn, values)
}

export function getDependencyFieldnames(expression?: string) {
  const dependsOn = normaliseExpression(expression)

  if (!dependsOn) {
    return []
  }

  const fieldnames = new Set<string>()

  const docFieldRegex = /doc\.([a-zA-Z0-9_]+)/g
  let match = docFieldRegex.exec(dependsOn)

  while (match) {
    fieldnames.add(match[1])
    match = docFieldRegex.exec(dependsOn)
  }

  if (!fieldnames.size && /^[a-zA-Z0-9_]+$/.test(dependsOn)) {
    fieldnames.add(dependsOn)
  }

  return Array.from(fieldnames)
}