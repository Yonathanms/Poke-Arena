export interface ApiErrorDetail {
  field?: string;
  issue?: string;
  [key: string]: unknown;
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details: ApiErrorDetail[];
    correlation_id: string;
    timestamp: string;
  };
}

export interface HealthResponse {
  status: "healthy" | "degraded";
  environment: string;
  correlation_id: string;
  databases: {
    postgres_master?: string;
    postgres_replica?: string;
    mongodb?: string;
  };
}
