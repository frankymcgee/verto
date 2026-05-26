export type FormValues = Record<string, any>

function normaliseValue(value: any) {
  if (value === undefined || value === null) return ''
  return value
}

function isTruthy(value: any) {
  if (value === true) return true
  if (value === 1) return true
  if (value === '1') return true
  if (value === 'true') return true
  if (value === 'Yes') return true
  if (value === 'yes') return true

  return Boolean(value)
}

function getDocValue(fieldname: string, values: FormValues) {
  return normaliseValue(values[fieldname])
}

function parseLiteral(value: string) {
  const trimmed = value.trim()

  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1)
  }

  if (trimmed === 'true') return true
  if (trimmed === 'false') return false
  if (trimmed === 'null') return null
  if (trimmed === 'undefined') return undefined

  const numberValue = Number(trimmed)

  if (!Number.isNaN(numberValue) && trimmed !== '') {
    return numberValue
  }

  return trimmed
}

function compareValues(left: any, operator: string, right: any) {
  const normalisedLeft = normaliseValue(left)
  const normalisedRight = normaliseValue(right)

  switch (operator) {
    case '==':
      // eslint-disable-next-line eqeqeq
      return normalisedLeft == normalisedRight

    case '!=':
      // eslint-disable-next-line eqeqeq
      return normalisedLeft != normalisedRight

    case '===':
      return normalisedLeft === normalisedRight

    case '!==':
      return normalisedLeft !== normalisedRight

    case '>':
      return Number(normalisedLeft) > Number(normalisedRight)

    case '>=':
      return Number(normalisedLeft) >= Number(normalisedRight)

    case '<':
      return Number(normalisedLeft) < Number(normalisedRight)

    case '<=':
      return Number(normalisedLeft) <= Number(normalisedRight)

    default:
      return false
  }
}

function evaluateSimpleExpression(expression: string, values: FormValues) {
  const cleaned = expression.trim()

  // Supports: doc.fieldname
  const docFieldOnlyMatch = cleaned.match(/^doc\.([a-zA-Z0-9_]+)$/)

  if (docFieldOnlyMatch) {
    return isTruthy(getDocValue(docFieldOnlyMatch[1], values))
  }

  // Supports: !doc.fieldname
  const notDocFieldOnlyMatch = cleaned.match(/^!doc\.([a-zA-Z0-9_]+)$/)

  if (notDocFieldOnlyMatch) {
    return !isTruthy(getDocValue(notDocFieldOnlyMatch[1], values))
  }

  // Supports:
  // doc.fieldname == "Yes"
  // doc.fieldname != "No"
  // doc.score >= 5
  const comparisonMatch = cleaned.match(
    /^doc\.([a-zA-Z0-9_]+)\s*(===|!==|==|!=|>=|<=|>|<)\s*(.+)$/
  )

  if (comparisonMatch) {
    const fieldname = comparisonMatch[1]
    const operator = comparisonMatch[2]
    const rightValue = parseLiteral(comparisonMatch[3])

    return compareValues(getDocValue(fieldname, values), operator, rightValue)
  }

  // Supports: fieldname
  const bareFieldMatch = cleaned.match(/^([a-zA-Z0-9_]+)$/)

  if (bareFieldMatch) {
    return isTruthy(getDocValue(bareFieldMatch[1], values))
  }

  return false
}

export function evaluateDependsOn(dependsOn: string | undefined | null, values: FormValues) {
  if (!dependsOn) {
    return true
  }

  const expression = dependsOn.trim()

  if (!expression) {
    return true
  }

  if (expression.startsWith('eval:')) {
    const evalExpression = expression.replace(/^eval:/, '').trim()

    // Basic AND support:
    // eval:doc.a == "Yes" && doc.b == "No"
    if (evalExpression.includes('&&')) {
      return evalExpression
        .split('&&')
        .map((part) => part.trim())
        .every((part) => evaluateSimpleExpression(part, values))
    }

    // Basic OR support:
    // eval:doc.a == "Yes" || doc.b == "Yes"
    if (evalExpression.includes('||')) {
      return evalExpression
        .split('||')
        .map((part) => part.trim())
        .some((part) => evaluateSimpleExpression(part, values))
    }

    return evaluateSimpleExpression(evalExpression, values)
  }

  // Supports non-eval depends_on value like:
  // fieldname
  return evaluateSimpleExpression(expression, values)
}

export function evaluateMandatoryDependsOn(dependsOn: string | undefined | null, values: FormValues) {
  if (!dependsOn) {
    return false
  }

  return evaluateDependsOn(dependsOn, values)
}

export function evaluateReadOnlyDependsOn(dependsOn: string | undefined | null, values: FormValues) {
  if (!dependsOn) {
    return false
  }

  return evaluateDependsOn(dependsOn, values)
}