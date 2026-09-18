import type {
  AccessToken,
  ApiError,
  ApiSuccess,
  CurrentUser,
} from "../../../../shared/contracts/api";

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public traceId = "",
  ) {
    super(message);
  }
}

/** Tokens are held in memory only. Reloading the page requires a new login. */
export class ApiClient {
  private tokens: AccessToken | null = null;
  private refreshJob: Promise<void> | null = null;
  private epoch = 0;
  onSessionLost: () => void = () => {};

  constructor(
    private fetcher: typeof fetch = (...args) => fetch(...args),
    private base = "/api/v1",
  ) {}
  get authenticated() {
    return this.tokens !== null;
  }

  private async send<T>(
    path: string,
    method: string,
    body?: unknown,
    access?: string,
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (access) headers.Authorization = `Bearer ${access}`;
    let response: Response;
    try {
      response = await this.fetcher(this.base + path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(15000),
        cache: "no-store",
        credentials: "omit",
      });
    } catch {
      throw new ApiRequestError(
        0,
        "NETWORK_ERROR",
        "Không kết nối được máy chủ. Vui lòng thử lại.",
      );
    }
    let payload: ApiSuccess<T> & Partial<ApiError>;
    try {
      payload = await response.json();
    } catch {
      throw new ApiRequestError(
        response.status,
        "INVALID_RESPONSE",
        "Phản hồi máy chủ không hợp lệ.",
      );
    }
    if (
      !payload ||
      typeof payload !== "object" ||
      typeof payload.code !== "string"
    ) {
      throw new ApiRequestError(
        response.status,
        "INVALID_RESPONSE",
        "Phản hồi máy chủ không hợp lệ.",
      );
    }
    if (!response.ok) {
      throw new ApiRequestError(
        response.status,
        payload.code,
        payload.message,
        payload.trace_id,
      );
    }
    if (!payload || !("data" in payload)) {
      throw new ApiRequestError(
        response.status,
        "INVALID_RESPONSE",
        "Phản hồi máy chủ không hợp lệ.",
      );
    }
    return payload.data;
  }

  async login(login: string, password: string): Promise<CurrentUser> {
    const epoch = ++this.epoch;
    this.tokens = null;
    this.refreshJob = null;
    let tokens: AccessToken;
    try {
      tokens = await this.send<AccessToken>("/auth/login", "POST", {
        login,
        password,
      });
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 401)
        error.code = "LOGIN_FAILED";
      throw error;
    }
    if (epoch !== this.epoch)
      throw new ApiRequestError(401, "SESSION_CHANGED", "Phiên đã thay đổi.");
    this.tokens = tokens;
    return this.request<CurrentUser>("/auth/me");
  }

  private clear() {
    this.tokens = null;
    this.refreshJob = null;
    ++this.epoch;
    this.onSessionLost();
  }

  private async rotate(accessUsed: string, epoch: number) {
    if (epoch !== this.epoch || !this.tokens)
      throw new ApiRequestError(401, "UNAUTHORIZED", "Hãy đăng nhập lại.");
    if (this.tokens.access_token !== accessUsed) return;
    if (!this.refreshJob) {
      const job = this.send<AccessToken>("/auth/refresh", "POST", {
        refresh_token: this.tokens.refresh_token,
      })
        .then((tokens) => {
          if (epoch === this.epoch) this.tokens = tokens;
        })
        .catch((error) => {
          if (epoch === this.epoch) this.clear();
          throw error;
        })
        .finally(() => {
          if (this.refreshJob === job) this.refreshJob = null;
        });
      this.refreshJob = job;
    }
    await this.refreshJob;
  }

  async request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    const epoch = this.epoch;
    if (this.refreshJob) await this.refreshJob;
    const access = this.tokens?.access_token;
    if (!access || epoch !== this.epoch)
      throw new ApiRequestError(401, "UNAUTHORIZED", "Hãy đăng nhập lại.");
    try {
      const data = await this.send<T>(path, method, body, access);
      if (epoch !== this.epoch)
        throw new ApiRequestError(401, "SESSION_CHANGED", "Phiên đã thay đổi.");
      return data;
    } catch (error) {
      if (
        !(error instanceof ApiRequestError) ||
        error.status !== 401 ||
        epoch !== this.epoch
      )
        throw error;
      await this.rotate(access, epoch);
      if (epoch !== this.epoch || !this.tokens)
        throw new ApiRequestError(401, "UNAUTHORIZED", "Hãy đăng nhập lại.");
      try {
        const data = await this.send<T>(
          path,
          method,
          body,
          this.tokens.access_token,
        );
        if (epoch !== this.epoch)
          throw new ApiRequestError(
            401,
            "SESSION_CHANGED",
            "Phiên đã thay đổi.",
          );
        return data;
      } catch (retryError) {
        if (
          retryError instanceof ApiRequestError &&
          retryError.status === 401 &&
          epoch === this.epoch
        )
          this.clear();
        throw retryError;
      }
    }
  }

  async logout() {
    const token = this.tokens?.refresh_token;
    this.clear();
    if (token)
      await this.send("/auth/logout", "POST", { refresh_token: token });
  }
}

export const api = new ApiClient();
