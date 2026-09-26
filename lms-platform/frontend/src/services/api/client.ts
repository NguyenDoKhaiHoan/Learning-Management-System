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

/**
 * Tokens are held in memory only.
 * Reloading the page requires a new login.
 */
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

  // =========================================================
  // RESPONSE PARSER
  // =========================================================

  private async parseJson<T>(response: Response): Promise<T> {
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

    if (!("data" in payload)) {
      throw new ApiRequestError(
        response.status,
        "INVALID_RESPONSE",
        "Phản hồi máy chủ không hợp lệ.",
      );
    }

    return payload.data;
  }

  // =========================================================
  // RAW REQUEST
  // Dùng cho binary upload + JSON
  // =========================================================

  private async sendRawJson<T>(
    path: string,
    method: string,
    body: BodyInit | undefined,
    headers: Record<string, string>,
    access?: string,
  ): Promise<T> {
    const requestHeaders: Record<string, string> = {
      Accept: "application/json",
      ...headers,
    };

    if (access) {
      requestHeaders.Authorization = `Bearer ${access}`;
    }

    let response: Response;

    try {
      response = await this.fetcher(this.base + path, {
        method,
        headers: requestHeaders,
        body,
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

    return this.parseJson<T>(response);
  }

  // =========================================================
  // JSON REQUEST
  // =========================================================

  private async send<T>(
    path: string,
    method: string,
    body?: unknown,
    access?: string,
  ): Promise<T> {
    return this.sendRawJson<T>(
      path,
      method,

      body === undefined ? undefined : JSON.stringify(body),

      body === undefined
        ? {}
        : {
            "Content-Type": "application/json",
          },

      access,
    );
  }

  // =========================================================
  // LOGIN
  // =========================================================

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
      if (error instanceof ApiRequestError && error.status === 401) {
        error.code = "LOGIN_FAILED";
      }

      throw error;
    }

    if (epoch !== this.epoch) {
      throw new ApiRequestError(401, "SESSION_CHANGED", "Phiên đã thay đổi.");
    }

    this.tokens = tokens;

    return this.request<CurrentUser>("/auth/me");
  }

  // =========================================================
  // CLEAR SESSION
  // =========================================================

  private clear() {
    this.tokens = null;

    this.refreshJob = null;

    ++this.epoch;

    this.onSessionLost();
  }

  // =========================================================
  // REFRESH TOKEN
  // =========================================================

  private async rotate(accessUsed: string, epoch: number) {
    if (epoch !== this.epoch || !this.tokens) {
      throw new ApiRequestError(401, "UNAUTHORIZED", "Hãy đăng nhập lại.");
    }

    // Nếu access token đã được request khác refresh
    // thì không refresh lần nữa.
    if (this.tokens.access_token !== accessUsed) {
      return;
    }

    if (!this.refreshJob) {
      const job = this.send<AccessToken>("/auth/refresh", "POST", {
        refresh_token: this.tokens.refresh_token,
      })
        .then((tokens) => {
          if (epoch === this.epoch) {
            this.tokens = tokens;
          }
        })
        .catch((error) => {
          if (epoch === this.epoch) {
            this.clear();
          }

          throw error;
        })
        .finally(() => {
          if (this.refreshJob === job) {
            this.refreshJob = null;
          }
        });

      this.refreshJob = job;
    }

    await this.refreshJob;
  }

  // =========================================================
  // AUTHORIZED EXECUTOR
  //
  // Dùng chung cho:
  // - JSON API
  // - upload binary
  // - download file
  //
  // Nếu access token hết hạn:
  // 401
  //   ↓
  // refresh token
  //   ↓
  // retry request
  // =========================================================

  private async authorized<T>(
    operation: (access: string) => Promise<T>,
  ): Promise<T> {
    const epoch = this.epoch;

    if (this.refreshJob) {
      await this.refreshJob;
    }

    const access = this.tokens?.access_token;

    if (!access || epoch !== this.epoch) {
      throw new ApiRequestError(401, "UNAUTHORIZED", "Hãy đăng nhập lại.");
    }

    try {
      const data = await operation(access);

      if (epoch !== this.epoch) {
        throw new ApiRequestError(401, "SESSION_CHANGED", "Phiên đã thay đổi.");
      }

      return data;
    } catch (error) {
      if (
        !(error instanceof ApiRequestError) ||
        error.status !== 401 ||
        epoch !== this.epoch
      ) {
        throw error;
      }

      // Token hết hạn
      // → refresh
      await this.rotate(access, epoch);

      if (epoch !== this.epoch || !this.tokens) {
        throw new ApiRequestError(401, "UNAUTHORIZED", "Hãy đăng nhập lại.");
      }

      try {
        const data = await operation(this.tokens.access_token);

        if (epoch !== this.epoch) {
          throw new ApiRequestError(
            401,
            "SESSION_CHANGED",
            "Phiên đã thay đổi.",
          );
        }

        return data;
      } catch (retryError) {
        if (
          retryError instanceof ApiRequestError &&
          retryError.status === 401 &&
          epoch === this.epoch
        ) {
          this.clear();
        }

        throw retryError;
      }
    }
  }

  // =========================================================
  // NORMAL JSON REQUEST
  // =========================================================

  async request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    return this.authorized((access) =>
      this.send<T>(path, method, body, access),
    );
  }

  // =========================================================
  // FILE UPLOAD
  //
  // Backend hiện yêu cầu:
  //
  // Content-Type: application/pdf ...
  // X-File-Name: report.pdf
  // BODY: raw binary
  //
  // KHÔNG phải multipart/form-data
  // =========================================================

  async upload<T>(path: string, file: File): Promise<T> {
    if (!file.type) {
      throw new ApiRequestError(
        422,
        "VALIDATION_ERROR",
        "Không xác định được MIME type của tệp.",
      );
    }

    return this.authorized((access) =>
      this.sendRawJson<T>(
        path,
        "POST",

        file,

        {
          "Content-Type": file.type,

          "X-File-Name": file.name,
        },

        access,
      ),
    );
  }

  // =========================================================
  // PRIVATE FILE DOWNLOAD
  // =========================================================

  async download(path: string, filename: string): Promise<void> {
    const blob = await this.authorized(async (access) => {
      let response: Response;

      try {
        response = await this.fetcher(this.base + path, {
          method: "GET",

          headers: {
            Authorization: `Bearer ${access}`,
          },

          signal: AbortSignal.timeout(30000),

          cache: "no-store",

          credentials: "omit",
        });
      } catch {
        throw new ApiRequestError(0, "NETWORK_ERROR", "Không tải được tệp.");
      }

      if (!response.ok) {
        // API lỗi của backend vẫn trả
        // JSON theo ApiError.
        return this.parseJson<Blob>(response);
      }

      return response.blob();
    });

    const url = URL.createObjectURL(blob);

    const anchor = document.createElement("a");

    anchor.href = url;

    anchor.download = filename;

    anchor.style.display = "none";

    document.body.appendChild(anchor);

    anchor.click();

    anchor.remove();

    // Không revoke ngay lập tức
    // để browser có thời gian bắt đầu download.
    window.setTimeout(() => {
      URL.revokeObjectURL(url);
    }, 1000);
  }

  // =========================================================
  // LOGOUT
  // =========================================================

  async logout() {
    const token = this.tokens?.refresh_token;

    this.clear();

    if (token) {
      await this.send("/auth/logout", "POST", {
        refresh_token: token,
      });
    }
  }
}

export const api = new ApiClient();
