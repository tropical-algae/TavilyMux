export interface TimelineScale {
  minimum: number
  maximum: number
  ticks: number[]
}

const QUOTA_STEP = 50

export function buildTimelineScale(values: number[]): TimelineScale | null {
  if (values.length === 0) return null

  const minimumValue = Math.min(...values)
  const maximum = Math.max(...values)
  const minimum =
    Math.floor((minimumValue - Number.EPSILON * Math.max(1, minimumValue)) / QUOTA_STEP) *
    QUOTA_STEP
  const midpoint = minimum + (maximum - minimum) / 2

  return {
    minimum,
    maximum,
    ticks: [maximum, midpoint, minimum],
  }
}

export function scaleTimelineValue(
  value: number,
  scale: TimelineScale,
  top: number,
  bottom: number,
): number {
  const range = scale.maximum - scale.minimum
  if (range === 0) return top + (bottom - top) / 2
  return top + ((scale.maximum - value) / range) * (bottom - top)
}

export function sampleTimelineIndexes(length: number, maximumTicks = 4): number[] {
  if (length <= 0 || maximumTicks <= 0) return []
  if (length <= maximumTicks) return Array.from({ length }, (_, index) => index)

  return Array.from(
    new Set(
      Array.from({ length: maximumTicks }, (_, index) =>
        Math.round((index / (maximumTicks - 1)) * (length - 1)),
      ),
    ),
  )
}
