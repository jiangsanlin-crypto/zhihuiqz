const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type User = {
  id: number;
  phone: string;
  role: string;
  display_name: string;
  is_active: boolean;
};

export type Employer = {
  id: number;
  owner_user_id: number;
  name: string;
  employer_type: string;
  verified: boolean;
  location: string;
  latitude: number | null;
  longitude: number | null;
};

export type JobResult = {
  id: number;
  employer_id: number;
  category: string;
  title_km: string;
  title_en: string;
  title_zh: string;
  location: string;
  latitude: number | null;
  longitude: number | null;
  salary_min: number | null;
  salary_max: number | null;
  currency: string;
  headcount: number;
  job_type: string;
  experience_required: boolean;
  requires_cv: boolean;
  benefits: string;
  description: string;
  status: string;
  distance_km: number | null;
  employer_verified: boolean;
};

const TOKEN_KEY = "khmerhire_access_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}, auth = false): Promise<T> {
  const headers = new Headers(init.headers || {});
  headers.set("Content-Type", "application/json");
  if (auth) {
    const token = getToken();
    if (!token) throw new Error("Please sign in first");
    headers.set("Authorization", "Bearer " + token);
  }
  const response = await fetch(API_URL + path, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Request failed (" + response.status + ")");
  }
  return response.json() as Promise<T>;
}

export async function registerAccount(input: {
  phone: string;
  password: string;
  role: "candidate" | "employer_admin";
  display_name: string;
}) {
  return request<User>("/auth/register", { method: "POST", body: JSON.stringify(input) });
}

export async function loginAccount(phone: string, password: string) {
  const data = await request<{ access_token: string; token_type: string }>(
    "/auth/login",
    { method: "POST", body: JSON.stringify({ phone, password }) }
  );
  setToken(data.access_token);
  return data;
}

export function getMe() {
  return request<User>("/me", {}, true);
}

export function getMyEmployers() {
  return request<Employer[]>("/me/employers", {}, true);
}

export function createEmployer(input: {
  name: string;
  employer_type: string;
  location: string;
  latitude: number | null;
  longitude: number | null;
}) {
  return request<Employer>("/employers", { method: "POST", body: JSON.stringify(input) }, true);
}

export function submitEmployerVerification(
  employerId: number,
  input: { legal_name: string; registration_number: string; document_url: string }
) {
  return request(
    "/employers/" + employerId + "/verification",
    { method: "POST", body: JSON.stringify(input) },
    true
  );
}

export async function getEmployerVerification(employerId: number) {
  return request<{
    id: number;
    employer_id: number;
    status: string;
    legal_name: string;
    registration_number: string;
    document_url: string;
    note: string;
  }>("/employers/" + employerId + "/verification", {}, true);
}

export function searchNearbyJobs(latitude: number, longitude: number, radiusKm = 25) {
  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    radius_km: String(radiusKm),
    limit: "50"
  });
  return request<JobResult[]>("/jobs?" + params.toString());
}
