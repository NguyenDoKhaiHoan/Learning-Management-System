/** API v1 transport types. BIGINT IDs are strings; roles always come from the server. */
export interface ErrorDetail {
  location: (string | number)[];
  type: string;
  message: string;
}
export interface ApiError {
  code: string;
  message: string;
  details: ErrorDetail[];
  trace_id: string;
}
export interface ApiSuccess<T> {
  code: string;
  message: string;
  data: T;
  trace_id: string;
}
export interface CurrentUser {
  id: string;
  email: string;
  username: string;
  roles: string[];
}
