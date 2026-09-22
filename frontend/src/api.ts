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

export type PipelineCounts = {
  applied: number;
  contacted: number;
  interview: number;
  offered: number;
  joined: number;
  rejected: number;
};

export type EmployerApplication = {
  id: number;
  job_id: number;
  job_title_km: string;
  job_title_en: string;
  job_title_zh: string;
  candidate_user_id: number | null;
  candidate_name: string;
  phone: string;
  location: string;
  available_date: string;
  cv_url: string | null;
  status: string;
};

export type PipelineSummary = {
  employer_id: number;
  total_jobs: number;
  target_headcount: number;
  counts: PipelineCounts;
  by_job: Array<{
    job_id: number;
    title_km: string;
    title_en: string;
    title_zh: string;
    headcount: number;
    counts: PipelineCounts;
  }>;
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
  benefit_codes: string;
  shift: string;
  languages_required: string;
  experience_level: string;
  province_code: string;
  district_code: string;
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
  return request<{ id: number; employer_id: number; status: string; legal_name: string; registration_number: string; document_url: string; note: string }>(
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


export function createJob(input: {
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
  benefit_codes: string;
  shift: string;
  languages_required: string;
  experience_level: string;
  province_code: string;
  district_code: string;
  description: string;
}) {
  return request<JobResult>("/jobs", { method: "POST", body: JSON.stringify(input) }, true);
}

export function getEmployerJobs(employerId: number) {
  return request<JobResult[]>("/employers/" + employerId + "/jobs", {}, true);
}

export function getEmployerApplications(employerId: number, status?: string) {
  const suffix = status ? "?status=" + encodeURIComponent(status) : "";
  return request<EmployerApplication[]>(
    "/employers/" + employerId + "/applications" + suffix,
    {},
    true
  );
}

export function getEmployerPipeline(employerId: number) {
  return request<PipelineSummary>("/employers/" + employerId + "/pipeline", {}, true);
}

export function updateApplicationStatus(applicationId: number, status: string, note = "") {
  return request(
    "/applications/" + applicationId + "/status",
    { method: "PATCH", body: JSON.stringify({ status, note }) },
    true
  );
}


export type EmployerTeamMember = {
  id: number;
  employer_id: number;
  user_id: number;
  role: string;
  status: string;
  display_name: string;
  phone: string;
};

export type CandidateApplication = {
  id: number;
  job_id: number;
  job_title_km: string;
  job_title_en: string;
  job_title_zh: string;
  employer_name: string;
  employer_verified: boolean;
  status: string;
  location: string;
  available_date: string;
  latest_interview_at: string | null;
};

export type Interview = {
  id: number;
  application_id: number;
  scheduled_by_user_id: number;
  starts_at: string;
  location: string;
  meeting_url: string;
  note: string;
  status: string;
};

export type ApplicationMessage = {
  id: number;
  application_id: number;
  sender_user_id: number;
  sender_name: string;
  body: string;
  created_at: string;
};

export type CandidateMatch = {
  candidate_user_id: number;
  candidate_name: string;
  score: number;
  factors: Array<{ name: string; score: number; detail: string }>;
};

export function inviteEmployerTeamMember(employerId: number, phone: string, role = "hr") {
  return request<{ id: number; employer_id: number; phone: string; role: string; token: string; status: string }>(
    "/employers/" + employerId + "/invitations",
    { method: "POST", body: JSON.stringify({ phone, role }) },
    true
  );
}

export function acceptEmployerInvitation(token: string) {
  return request<EmployerTeamMember>(
    "/employer-invitations/" + encodeURIComponent(token) + "/accept",
    { method: "POST" },
    true
  );
}

export function getEmployerTeam(employerId: number) {
  return request<EmployerTeamMember[]>("/employers/" + employerId + "/team", {}, true);
}

export function getMyApplications() {
  return request<CandidateApplication[]>("/me/applications", {}, true);
}

export function scheduleInterview(
  applicationId: number,
  input: { starts_at: string; location: string; meeting_url: string; note: string }
) {
  return request<Interview>(
    "/applications/" + applicationId + "/interviews",
    { method: "POST", body: JSON.stringify(input) },
    true
  );
}

export function getApplicationInterviews(applicationId: number) {
  return request<Interview[]>("/applications/" + applicationId + "/interviews", {}, true);
}

export function getApplicationMessages(applicationId: number) {
  return request<ApplicationMessage[]>("/applications/" + applicationId + "/messages", {}, true);
}

export function sendApplicationMessage(applicationId: number, body: string) {
  return request<ApplicationMessage>(
    "/applications/" + applicationId + "/messages",
    { method: "POST", body: JSON.stringify({ body }) },
    true
  );
}

export function getJobMatches(jobId: number) {
  return request<CandidateMatch[]>("/jobs/" + jobId + "/matches", {}, true);
}

export function getProvinces() {
  return request<Array<{ code: string; km: string; en: string; zh: string }>>("/locations/provinces");
}

export function getDistricts(provinceCode: string) {
  return request<Array<{ code: string; en: string; zh: string }>>(
    "/locations/districts?province_code=" + encodeURIComponent(provinceCode)
  );
}
