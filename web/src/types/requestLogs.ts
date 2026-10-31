export interface RequestLogFilters {
  pool_id: string
  key_id: string
  status_code: string
  success: "" | "true" | "false"
  retried: "" | "true" | "false"
  request_id: string
  time_from: string
  time_to: string
  page: number
  page_size: number
}

export type RequestLogFilterField = Exclude<keyof RequestLogFilters, "page" | "page_size">

export interface RequestLogApiParams {
  page: number
  page_size: number
  pool_id?: string
  key_id?: string
  status_code?: number
  success?: boolean
  retried?: boolean
  request_id?: string
  time_from?: string
  time_to?: string
}
